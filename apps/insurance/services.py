from datetime import timedelta
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.utils import timezone

from .models import Policy, PremiumQuote, UnderwritingCase


PRODUCTS = {
    'PA_C_ACCIDENT': {
        'name': '平安个人综合意外险',
        'plans': {
            'BASIC': {
                'name': '基础版',
                'base_premium': Decimal('99.00'),
                'coverages': [
                    {'code': 'ACCIDENT_DEATH', 'name': '意外身故/伤残', 'insured_amount': Decimal('100000')},
                    {'code': 'ACCIDENT_MEDICAL', 'name': '意外医疗', 'insured_amount': Decimal('10000')},
                ],
            },
            'STANDARD': {
                'name': '标准版',
                'base_premium': Decimal('199.00'),
                'coverages': [
                    {'code': 'ACCIDENT_DEATH', 'name': '意外身故/伤残', 'insured_amount': Decimal('300000')},
                    {'code': 'ACCIDENT_MEDICAL', 'name': '意外医疗', 'insured_amount': Decimal('30000')},
                    {'code': 'HOSPITAL_ALLOWANCE', 'name': '意外住院津贴', 'insured_amount': Decimal('100')},
                ],
            },
            'PREMIUM': {
                'name': '尊享版',
                'base_premium': Decimal('399.00'),
                'coverages': [
                    {'code': 'ACCIDENT_DEATH', 'name': '意外身故/伤残', 'insured_amount': Decimal('800000')},
                    {'code': 'ACCIDENT_MEDICAL', 'name': '意外医疗', 'insured_amount': Decimal('80000')},
                    {'code': 'HOSPITAL_ALLOWANCE', 'name': '意外住院津贴', 'insured_amount': Decimal('200')},
                ],
            },
        },
    }
}


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


def age_factor(age):
    if age < 18:
        return Decimal('0.80')
    if age <= 45:
        return Decimal('1.00')
    if age <= 60:
        return Decimal('1.35')
    return Decimal('1.80')


def occupation_factor(category):
    return {
        1: Decimal('0.90'),
        2: Decimal('1.00'),
        3: Decimal('1.20'),
        4: Decimal('1.60'),
        5: Decimal('2.50'),
        6: Decimal('3.50'),
    }[category]


def serialize_coverages(coverages):
    return [
        {
            **item,
            'insured_amount': money(item['insured_amount']),
        }
        for item in coverages
    ]


def generate_no(prefix, model, field_name):
    today = timezone.localdate().strftime('%Y%m%d')
    sequence = model.objects.filter(**{f'{field_name}__startswith': f'{prefix}{today}'}).count() + 1
    return f'{prefix}{today}{sequence:06d}'


@transaction.atomic
def create_premium_quote(validated_data):
    """后端处理逻辑：保费试算。

    真实业务含义：
    - 前端提交产品、计划、投保人、被保人、职业类别等信息。
    - 后端按产品计划基础费率、年龄系数、职业风险系数、社保优惠计算保费。
    - 生成 quote_no，保存试算单。
    - 后续核保必须引用这个 quote_no，保证流程串联。
    """
    product = PRODUCTS.get(validated_data['product_code'])
    if not product:
        raise ValueError('产品不存在或已下架')

    plan = product['plans'][validated_data['plan_code']]
    effective_date = validated_data['effective_date']
    period_months = validated_data['insurance_period_months']
    expiry_date = effective_date + timedelta(days=period_months * 30 - 1)
    insured_birth = date_from_id_no(validated_data['insured'])
    insured_age = age_on(insured_birth, effective_date)

    # 基础保费来自产品计划；真实企业中通常来自产品中心/费率表。
    base = plan['base_premium']
    # 应缴保费 = 基础保费 * 年龄系数 * 职业系数 * 保障期间系数 * 优惠折扣。
    calculated = (
        base
        * age_factor(insured_age)
        * occupation_factor(validated_data['occupation_category'])
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
            'age_factor': str(age_factor(insured_age)),
            'occupation_category': validated_data['occupation_category'],
            'occupation_factor': str(occupation_factor(validated_data['occupation_category'])),
            'social_security_discount': str(social_security_discount),
            'period_months': period_months,
        },
    }

    return PremiumQuote.objects.create(
        quote_no=generate_no('QT', PremiumQuote, 'quote_no'),
        product_code=validated_data['product_code'],
        product_name=product['name'],
        plan_code=validated_data['plan_code'],
        plan_name=plan['name'],
        applicant=json_safe(validated_data['applicant']),
        insured=json_safe(validated_data['insured']),
        coverages=serialize_coverages(plan['coverages']),
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
    return uw_case


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
    return policy
