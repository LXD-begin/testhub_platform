from datetime import timedelta
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.utils import timezone

from .cache import (
    delete_application_cache,
    delete_caches_for_payment_order,
    delete_caches_for_policy,
    delete_caches_for_underwriting,
    delete_quote_cache,
    delete_underwriting_cache,
)
from .models import (
    AgeRateFactor,
    DeliveryRecord,
    ElectronicPolicy,
    InsuranceApplication,
    ManualUnderwritingReview,
    OccupationRateFactor,
    PaymentOrder,
    Policy,
    PremiumQuote,
    Product,
    UnderwritingCase,
)


def money(value):
    return str(Decimal(value).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


def json_safe(value):
    if isinstance(value, Decimal):
        return money(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    return value


def format_datetime(value):
    if not value:
        return None
    return timezone.localtime(value).strftime('%Y-%m-%d %H:%M:%S')


def date_from_id_no(person):
    id_no = person.get('id_no', '')
    if person.get('id_type') == 'IDENTITY_CARD' and len(id_no) == 18:
        birth = id_no[6:14]
        return timezone.datetime.strptime(birth, '%Y%m%d').date()
    return person.get('date_of_birth')


def age_on(date_of_birth, target_date):
    if not date_of_birth:
        return 30
    return target_date.year - date_of_birth.year - (
        (target_date.month, target_date.day) < (date_of_birth.month, date_of_birth.day)
    )


def age_factor(age, product):
    rate = AgeRateFactor.objects.filter(
        product=product,
        min_age__lte=age,
        max_age__gte=age,
        is_enabled=True,
    ).order_by('min_age').first()
    if not rate:
        raise ValueError('未配置匹配的年龄费率')
    return Decimal(str(rate.factor))


def occupation_factor(category, product):
    rate = OccupationRateFactor.objects.filter(
        product=product,
        occupation_category=category,
        is_enabled=True,
    ).first()
    if not rate:
        raise ValueError('未配置匹配的职业类别费率')
    return Decimal(str(rate.factor))


def serialize_coverages(coverages):
    return [
        {
            'code': item.coverage_code,
            'name': item.coverage_name,
            'insured_amount': money(item.insured_amount),
        }
        for item in coverages
    ]


def load_product_plan(product_code, plan_code, effective_date):
    """读取产品、计划和责任配置。

    真实系统通常来自产品中心、费率中心；这里先落在本项目数据库中，方便后台维护和测试。
    """
    try:
        product = Product.objects.get(product_code=product_code)
    except Product.DoesNotExist as exc:
        raise ValueError('产品不存在或已下架') from exc

    if product.status != Product.Status.ACTIVE:
        raise ValueError('产品不存在或已下架')
    if product.effective_start and effective_date < product.effective_start:
        raise ValueError('产品尚未到销售起期')
    if product.effective_end and effective_date > product.effective_end:
        raise ValueError('产品已过销售止期')

    plan = product.plans.filter(plan_code=plan_code, is_enabled=True).prefetch_related('coverages').first()
    if not plan:
        raise ValueError('产品计划不存在或未启用')
    coverages = list(plan.coverages.all())
    if not coverages:
        raise ValueError('产品计划未配置保障责任')
    return product, plan, coverages


def generate_no(prefix, model, field_name):
    today = timezone.localdate().strftime('%Y%m%d')
    sequence = model.objects.filter(**{f'{field_name}__startswith': f'{prefix}{today}'}).count() + 1
    return f'{prefix}{today}{sequence:06d}'


def latest_underwriting_for_application(application):
    """取投保单最近一次核保记录。

    真实系统通常会记录每次核保调用；出单时只允许使用最近且仍有效的通过结论。
    """
    return application.underwriting_cases.order_by('-created_at').first()


def update_application_after_underwriting(application, uw_case):
    """按核保结论同步投保单状态，避免前端自行推断状态。"""
    if uw_case.decision == UnderwritingCase.Decision.APPROVED:
        application.status = InsuranceApplication.Status.UNDERWRITING_APPROVED
    elif uw_case.decision == UnderwritingCase.Decision.REFERRED:
        application.status = InsuranceApplication.Status.UNDERWRITING_REFERRED
    else:
        application.status = InsuranceApplication.Status.UNDERWRITING_DECLINED
    application.save(update_fields=['status', 'updated_at'])
    delete_application_cache(application.application_no)
    delete_underwriting_cache(uw_case.uw_no)


def build_delivery_from_application(application):
    """从投保单里提取默认电子保单送达信息。"""
    delivery = {}
    applicant = application.applicant or {}
    if applicant.get('email'):
        delivery['email'] = applicant['email']
    if applicant.get('mobile'):
        delivery['sms_mobile'] = applicant['mobile']
    return delivery


def create_electronic_policy_and_delivery(policy, delivery):
    """生成电子保单索引并模拟邮件/短信送达。

    当前项目不引入文件服务和消息队列，所以这里用可预测 URL 和送达记录模拟真实系统产物。
    """
    document = ElectronicPolicy.objects.create(
        document_no=generate_no('EP', ElectronicPolicy, 'document_no'),
        policy=policy,
        download_url=f'/api/insurance/e-policies/{policy.policy_no}/download/',
        verify_code=generate_no('VC', ElectronicPolicy, 'verify_code'),
    )
    if delivery.get('email'):
        DeliveryRecord.objects.create(
            delivery_no=generate_no('DL', DeliveryRecord, 'delivery_no'),
            policy=policy,
            channel=DeliveryRecord.Channel.EMAIL,
            recipient=delivery['email'],
            payload={'document_no': document.document_no, 'download_url': document.download_url},
        )
    if delivery.get('sms_mobile'):
        DeliveryRecord.objects.create(
            delivery_no=generate_no('DL', DeliveryRecord, 'delivery_no'),
            policy=policy,
            channel=DeliveryRecord.Channel.SMS,
            recipient=delivery['sms_mobile'],
            payload={'policy_no': policy.policy_no, 'verify_code': document.verify_code},
        )
    return document


@transaction.atomic
def create_premium_quote(validated_data):
    """后端处理逻辑：保费试算。

    真实业务含义：
    - 前端提交产品、计划、投保人、被保人、职业类别等信息。
    - 后端按产品计划基础费率、年龄系数、职业风险系数、社保优惠计算保费。
    - 生成 quote_no，保存试算单。
    - 后续核保必须引用这个 quote_no，保证流程串联。
    """
    effective_date = validated_data['effective_date']
    period_months = validated_data['insurance_period_months']
    product, plan, coverages = load_product_plan(
        validated_data['product_code'],
        validated_data['plan_code'],
        effective_date,
    )
    if not product.min_period_months <= period_months <= product.max_period_months:
        raise ValueError('保障期限不在产品允许范围内')

    expiry_date = effective_date + timedelta(days=period_months * 30 - 1)
    insured_birth = date_from_id_no(validated_data['insured'])
    insured_age = age_on(insured_birth, effective_date)
    if not product.min_age <= insured_age <= product.max_age:
        raise ValueError('被保人年龄不在产品承保范围内')

    # 基础保费来自产品计划；真实企业中通常来自产品中心/费率表。
    base = plan.base_premium
    age_rate = age_factor(insured_age, product)
    occupation_rate = occupation_factor(validated_data['occupation_category'], product)
    # 应缴保费 = 基础保费 * 年龄系数 * 职业系数 * 保障期间系数 * 优惠折扣。
    calculated = (
        base
        * age_rate
        * occupation_rate
        * (Decimal(period_months) / Decimal('12'))
    )
    social_security_discount = Decimal('0.95') if validated_data['has_social_security'] else Decimal('1.00')
    standard_premium = calculated
    payable_premium = max(Decimal('30.00'), calculated * social_security_discount)
    discount_amount = standard_premium - payable_premium

    premium_detail = {
        'currency': 'CNY',
        'standard_premium': money(standard_premium),
        'discount_amount': money(discount_amount),
        'payable_premium': money(payable_premium),
        'pricing_factors': {
            'insured_age': insured_age,
            'age_factor': str(age_rate),
            'occupation_category': validated_data['occupation_category'],
            'occupation_factor': str(occupation_rate),
            'social_security_discount': str(social_security_discount),
            'period_months': period_months,
        },
    }

    return PremiumQuote.objects.create(
        quote_no=generate_no('QT', PremiumQuote, 'quote_no'),
        product_code=validated_data['product_code'],
        product_name=product.product_name,
        plan_code=validated_data['plan_code'],
        plan_name=plan.plan_name,
        applicant=json_safe(validated_data['applicant']),
        insured=json_safe(validated_data['insured']),
        coverages=serialize_coverages(coverages),
        premium_detail=premium_detail,
        effective_date=effective_date,
        expiry_date=expiry_date,
        valid_until=timezone.now() + timedelta(minutes=30),
    )


@transaction.atomic
def underwrite(validated_data):
    """后端处理逻辑：自动核保。

    真实业务含义：
    - 核保必须基于有效 quote_no，不能跳过试算。
    - 根据年龄、职业类别、健康告知、如实告知确认等规则给出核保结论。
    - APPROVED 允许继续线上出单。
    - REFERRED 需要人工核保。
    - DECLINED 直接拒保，不能出单。
    """
    quote = PremiumQuote.objects.select_for_update().get(quote_no=validated_data['quote_no'])
    if quote.valid_until < timezone.now():
        quote.status = PremiumQuote.Status.EXPIRED
        quote.save(update_fields=['status', 'updated_at'])
        delete_quote_cache(quote.quote_no)
        raise ValueError('试算单已过期，请重新试算')
    if hasattr(quote, 'policy'):
        raise ValueError('该试算单已出单，不能重复核保')

    disclosures = validated_data['disclosures']
    factors = quote.premium_detail['pricing_factors']
    age = int(factors['insured_age'])
    occupation_category = int(factors['occupation_category'])

    reasons = []
    decision = UnderwritingCase.Decision.APPROVED
    risk_level = 'LOW'

    # 职业类别规则：高危职业不允许直接线上承保。
    if occupation_category >= 6:
        decision = UnderwritingCase.Decision.DECLINED
        risk_level = 'REJECT'
        reasons.append('职业类别为 6 类，超出 C 端线上承保范围')
    elif occupation_category == 5:
        decision = UnderwritingCase.Decision.REFERRED
        risk_level = 'HIGH'
        reasons.append('职业类别为 5 类，需要人工复核')

    # 年龄规则：超过线上产品承保年龄上限则拒保。
    if age > 65:
        decision = UnderwritingCase.Decision.DECLINED
        risk_level = 'REJECT'
        reasons.append('被保人年龄超过 65 周岁')
    elif age > 60 and decision == UnderwritingCase.Decision.APPROVED:
        decision = UnderwritingCase.Decision.REFERRED
        risk_level = 'MEDIUM'
        reasons.append('被保人年龄超过 60 周岁，需要人工复核')

    # 健康告知规则：任一异常告知进入人工核保。
    health_answers = disclosures.get('health_answers', {})
    if any(bool(value) for value in health_answers.values()) and decision != UnderwritingCase.Decision.DECLINED:
        decision = UnderwritingCase.Decision.REFERRED
        risk_level = 'MEDIUM'
        reasons.append('健康告知存在异常，需要人工复核')

    if not disclosures.get('truth_declaration_confirmed'):
        decision = UnderwritingCase.Decision.DECLINED
        risk_level = 'REJECT'
        reasons.append('未确认如实告知声明')

    if not reasons:
        reasons.append('自动核保规则通过')

    uw_case = UnderwritingCase.objects.create(
        uw_no=generate_no('UW', UnderwritingCase, 'uw_no'),
        quote=quote,
        decision=decision,
        risk_level=risk_level,
        reasons=reasons,
        disclosures={
            **json_safe(disclosures),
            'beneficiary_type': validated_data['beneficiary_type'],
            'beneficiaries': validated_data.get('beneficiaries', []),
        },
        manual_review_required=decision == UnderwritingCase.Decision.REFERRED,
        valid_until=timezone.now() + timedelta(hours=24),
    )
    quote.status = PremiumQuote.Status.UNDERWRITTEN
    quote.save(update_fields=['status', 'updated_at'])
    delete_quote_cache(quote.quote_no)
    return uw_case


@transaction.atomic
def create_application(validated_data):
    """后端处理逻辑：创建投保单。

    真实业务含义：
    - 试算单只是价格快照，投保单才是正式投保申请。
    - 投保单沉淀投保确认、受益人、健康告知等合规留痕。
    - 同一个试算单只能创建一个有效投保单，避免多张申请争用同一价格快照。
    """
    quote = PremiumQuote.objects.select_for_update().get(quote_no=validated_data['quote_no'])
    if quote.valid_until < timezone.now():
        quote.status = PremiumQuote.Status.EXPIRED
        quote.save(update_fields=['status', 'updated_at'])
        delete_quote_cache(quote.quote_no)
        raise ValueError('试算单已过期，请重新试算')
    if hasattr(quote, 'application'):
        raise ValueError('该试算单已创建投保单，不能重复创建')

    consents = validated_data['consents']
    required_consents = ['terms_confirmed', 'exclusions_confirmed', 'electronic_policy_confirmed']
    missing = [field for field in required_consents if not consents.get(field)]
    if missing:
        raise ValueError(f'投保确认未完成: {", ".join(missing)}')

    return InsuranceApplication.objects.create(
        application_no=generate_no('APP', InsuranceApplication, 'application_no'),
        quote=quote,
        applicant=quote.applicant,
        insured=quote.insured,
        disclosures=json_safe(validated_data.get('disclosures', {})),
        beneficiary_type=validated_data.get('beneficiary_type', 'LEGAL'),
        beneficiaries=json_safe(validated_data.get('beneficiaries', [])),
        consents=json_safe(consents),
        channel_code=validated_data.get('channel_code', quote.premium_detail.get('channel_code', 'C_APP')),
    )


@transaction.atomic
def submit_application_underwriting(validated_data):
    """后端处理逻辑：投保单提交核保。

    真实业务含义：
    - 核保以投保单为主实体，同时继续绑定原试算单价格快照。
    - 核保结果会反写投保单状态，后续支付、出单都以投保单状态判断。
    """
    application = InsuranceApplication.objects.select_for_update().select_related('quote').get(
        application_no=validated_data['application_no']
    )
    if application.status in {
        InsuranceApplication.Status.ISSUED,
        InsuranceApplication.Status.UNDERWRITING_DECLINED,
        InsuranceApplication.Status.PAYMENT_PENDING,
        InsuranceApplication.Status.PAID,
        InsuranceApplication.Status.CLOSED,
    }:
        raise ValueError('当前投保单状态不允许重新提交核保')

    application.disclosures = json_safe(validated_data.get('disclosures', application.disclosures))
    application.beneficiary_type = validated_data.get('beneficiary_type', application.beneficiary_type)
    application.beneficiaries = json_safe(validated_data.get('beneficiaries', application.beneficiaries))
    application.status = InsuranceApplication.Status.SUBMITTED
    application.submitted_at = timezone.now()
    application.save(
        update_fields=['disclosures', 'beneficiary_type', 'beneficiaries', 'status', 'submitted_at', 'updated_at']
    )

    uw_case = underwrite({
        'quote_no': application.quote.quote_no,
        'disclosures': application.disclosures,
        'beneficiary_type': application.beneficiary_type,
        'beneficiaries': application.beneficiaries,
    })
    uw_case.application = application
    uw_case.save(update_fields=['application'])
    update_application_after_underwriting(application, uw_case)
    delete_caches_for_underwriting(uw_case)
    return uw_case


@transaction.atomic
def review_manual_underwriting(validated_data):
    """后端处理逻辑：人工核保复核。

    真实业务含义：
    - 自动核保转人工后，由核保员给出最终承保意见。
    - 复核结论会覆盖当前核保记录的 decision，便于后续支付和出单复用同一核保单号。
    """
    uw_case = UnderwritingCase.objects.select_for_update().select_related('application').get(
        uw_no=validated_data['underwriting_no']
    )
    if not uw_case.manual_review_required and uw_case.decision != UnderwritingCase.Decision.REFERRED:
        raise ValueError('该核保记录不需要人工复核')
    if hasattr(uw_case, 'manual_review'):
        raise ValueError('该核保记录已完成人工复核')
    if not uw_case.application:
        raise ValueError('旧版核保记录未关联投保单，不能走人工复核接口')

    review = ManualUnderwritingReview.objects.create(
        review_no=generate_no('MR', ManualUnderwritingReview, 'review_no'),
        underwriting=uw_case,
        decision=validated_data['decision'],
        risk_level=validated_data['risk_level'],
        reasons=json_safe(validated_data.get('reasons', [])),
        review_notes=validated_data.get('review_notes', ''),
        reviewer=validated_data['reviewer'],
    )
    uw_case.decision = review.decision
    uw_case.risk_level = review.risk_level
    uw_case.reasons = review.reasons or [f'人工核保员 {review.reviewer} 复核通过']
    uw_case.manual_review_required = review.decision == UnderwritingCase.Decision.REFERRED
    uw_case.valid_until = timezone.now() + timedelta(hours=24)
    uw_case.save(update_fields=['decision', 'risk_level', 'reasons', 'manual_review_required', 'valid_until'])
    update_application_after_underwriting(uw_case.application, uw_case)
    delete_caches_for_underwriting(uw_case)
    return review


@transaction.atomic
def create_payment_order(validated_data):
    """后端处理逻辑：创建支付订单。

    真实业务含义：
    - 支付订单必须由服务端基于投保单、核保单和应缴保费生成。
    - 后续出单只认服务端支付订单状态，不认前端自报支付成功。
    """
    application = InsuranceApplication.objects.select_for_update().select_related('quote').get(
        application_no=validated_data['application_no']
    )
    if application.status not in {
        InsuranceApplication.Status.UNDERWRITING_APPROVED,
        InsuranceApplication.Status.PAYMENT_PENDING,
    }:
        raise ValueError('投保单未核保通过，不能创建支付订单')
    if hasattr(application, 'policy'):
        raise ValueError('该投保单已出单，不能重复支付')

    uw_case = latest_underwriting_for_application(application)
    if not uw_case or uw_case.decision != UnderwritingCase.Decision.APPROVED:
        raise ValueError('未找到有效的核保通过记录')
    if uw_case.valid_until < timezone.now():
        raise ValueError('核保结果已过期，请重新核保')

    payable = Decimal(str(application.quote.premium_detail['payable_premium']))
    existing = application.payment_orders.filter(status=PaymentOrder.Status.SUCCESS).first()
    if existing:
        raise ValueError('该投保单已有成功支付订单，不能重复创建')
    pending_order = application.payment_orders.filter(status=PaymentOrder.Status.CREATED).first()
    if pending_order:
        return pending_order

    order = PaymentOrder.objects.create(
        pay_order_no=generate_no('PAY', PaymentOrder, 'pay_order_no'),
        application=application,
        quote=application.quote,
        underwriting=uw_case,
        amount=payable,
        pay_channel=validated_data.get('pay_channel', 'MOCK'),
    )
    application.status = InsuranceApplication.Status.PAYMENT_PENDING
    application.save(update_fields=['status', 'updated_at'])
    delete_caches_for_payment_order(order)
    return order


@transaction.atomic
def confirm_payment_order(validated_data):
    """后端处理逻辑：模拟支付中心回调。

    真实业务含义：
    - 生产系统应验签并核对支付中心流水；这里用接口模拟回调结果。
    - 回调幂等：已经成功的支付订单再次收到成功通知时直接返回原订单。
    """
    order = PaymentOrder.objects.select_for_update().select_related('application').get(
        pay_order_no=validated_data['pay_order_no']
    )
    paid_amount = Decimal(str(validated_data['paid_amount']))
    if paid_amount != order.amount:
        raise ValueError('支付回调金额与支付订单金额不一致')
    if order.status == PaymentOrder.Status.SUCCESS:
        return order
    if validated_data['pay_status'] != PaymentOrder.Status.SUCCESS:
        order.status = PaymentOrder.Status.FAILED
        order.notify_payload = json_safe(validated_data)
        order.save(update_fields=['status', 'notify_payload', 'updated_at'])
        delete_caches_for_payment_order(order)
        raise ValueError('支付未成功，不能继续出单')

    order.status = PaymentOrder.Status.SUCCESS
    order.external_trade_no = validated_data.get('external_trade_no', '')
    order.notify_payload = json_safe(validated_data)
    order.paid_at = timezone.now()
    order.save(update_fields=['status', 'external_trade_no', 'notify_payload', 'paid_at', 'updated_at'])

    application = order.application
    application.status = InsuranceApplication.Status.PAID
    application.save(update_fields=['status', 'updated_at'])
    delete_caches_for_payment_order(order)
    return order


@transaction.atomic
def issue_policy(validated_data):
    """后端处理逻辑：承保出单。

    真实业务含义：
    - 出单必须基于核保通过的 underwriting_no，不能跳过核保。
    - 支付必须成功，且实付金额必须等于试算应缴保费。
    - 生成 policy_no 并保存正式保单。
    - 同一个核保记录只能出一次保单，避免重复承保。
    """
    uw_case = UnderwritingCase.objects.select_for_update().select_related('quote').get(
        uw_no=validated_data['underwriting_no']
    )
    if uw_case.decision != UnderwritingCase.Decision.APPROVED:
        raise ValueError('仅自动核保通过的记录允许线上承保出单')
    if uw_case.valid_until < timezone.now():
        raise ValueError('核保结果已过期，请重新核保')
    if hasattr(uw_case, 'policy'):
        raise ValueError('该核保记录已出单，不能重复出单')

    quote = uw_case.quote
    # 支付校验：真实出单前必须和支付中心结果核对，这里用前端传入结果模拟。
    paid_amount = Decimal(str(validated_data['payment']['paid_amount']))
    payable = Decimal(str(quote.premium_detail['payable_premium']))
    if paid_amount != payable:
        raise ValueError('支付金额与应缴保费不一致')

    policy = Policy.objects.create(
        policy_no=generate_no('PAIC', Policy, 'policy_no'),
        quote=quote,
        underwriting=uw_case,
        applicant=quote.applicant,
        insured=quote.insured,
        coverages=quote.coverages,
        premium_detail=quote.premium_detail,
        payment={
            **validated_data['payment'],
            'delivery': validated_data.get('delivery', {}),
        },
        effective_date=quote.effective_date,
        expiry_date=quote.expiry_date,
    )
    quote.status = PremiumQuote.Status.ISSUED
    quote.save(update_fields=['status', 'updated_at'])
    delete_caches_for_policy(policy)
    return policy


@transaction.atomic
def issue_policy_from_application(validated_data):
    """后端处理逻辑：按真实投保单流程承保出单。

    真实业务含义：
    - 投保单必须核保通过且支付成功。
    - 使用服务端成功支付订单承保，生成保单、电子保单和送达记录。
    - 同一投保单、同一核保记录、同一支付订单都只能出一张正式保单。
    """
    application = InsuranceApplication.objects.select_for_update().select_related('quote').get(
        application_no=validated_data['application_no']
    )
    if application.status != InsuranceApplication.Status.PAID:
        raise ValueError('投保单未完成支付，不能承保出单')
    if hasattr(application, 'policy'):
        raise ValueError('该投保单已出单，不能重复出单')

    payment_order = application.payment_orders.select_for_update().filter(status=PaymentOrder.Status.SUCCESS).first()
    if not payment_order:
        raise ValueError('未找到成功支付订单')
    uw_case = payment_order.underwriting
    if uw_case.decision != UnderwritingCase.Decision.APPROVED:
        raise ValueError('核保未通过，不能承保出单')
    if uw_case.valid_until < timezone.now():
        raise ValueError('核保结果已过期，请重新核保')
    if hasattr(uw_case, 'policy'):
        raise ValueError('该核保记录已出单，不能重复出单')
    if hasattr(payment_order, 'policy'):
        raise ValueError('该支付订单已出单，不能重复出单')

    delivery = validated_data.get('delivery') or build_delivery_from_application(application)
    payment = {
        'pay_order_no': payment_order.pay_order_no,
        'pay_status': payment_order.status,
        'paid_amount': money(payment_order.amount),
        'paid_time': format_datetime(payment_order.paid_at),
        'pay_channel': payment_order.pay_channel,
        'external_trade_no': payment_order.external_trade_no,
        'delivery': delivery,
    }
    policy = Policy.objects.create(
        policy_no=generate_no('PAIC', Policy, 'policy_no'),
        application=application,
        quote=application.quote,
        underwriting=uw_case,
        payment_order=payment_order,
        applicant=application.applicant,
        insured=application.insured,
        coverages=application.quote.coverages,
        premium_detail=application.quote.premium_detail,
        payment=payment,
        effective_date=application.quote.effective_date,
        expiry_date=application.quote.expiry_date,
    )
    create_electronic_policy_and_delivery(policy, delivery)

    application.status = InsuranceApplication.Status.ISSUED
    application.save(update_fields=['status', 'updated_at'])
    application.quote.status = PremiumQuote.Status.ISSUED
    application.quote.save(update_fields=['status', 'updated_at'])
    delete_caches_for_policy(policy)
    return policy
