from decimal import Decimal

from rest_framework import serializers

from .models import Policy, PremiumQuote, UnderwritingCase


class PersonSerializer(serializers.Serializer):
    """前端传参：投保人/被保人基础身份信息。"""

    # 姓名：用于投保人、被保人实名信息展示和保单落库。
    name = serializers.CharField(max_length=64)
    # 证件类型：C 端常见为身份证，兼容护照。
    id_type = serializers.ChoiceField(choices=['IDENTITY_CARD', 'PASSPORT'])
    # 证件号码：身份证会用于反推出生日期和年龄。
    id_no = serializers.CharField(max_length=32)
    # 手机号：用于短信通知、电子保单送达。
    mobile = serializers.CharField(max_length=20, required=False, allow_blank=True)
    # 邮箱：用于电子保单发送。
    email = serializers.EmailField(required=False, allow_blank=True)
    # 出生日期：非身份证证件时前端需要传；身份证可不传。
    date_of_birth = serializers.DateField(required=False)
    # 性别：可选字段，预留给后续差异化费率或核保规则。
    gender = serializers.ChoiceField(choices=['M', 'F'], required=False)


class PremiumTrialRequestSerializer(serializers.Serializer):
    """前端传参：保费试算接口 POST /api/insurance/premium-trials/。"""

    # 产品代码：当前示例产品为 PA_C_ACCIDENT。
    product_code = serializers.CharField(max_length=32)
    # 计划代码：基础版、标准版、尊享版。
    plan_code = serializers.ChoiceField(choices=['BASIC', 'STANDARD', 'PREMIUM'])
    # 保险起期：前端选择的保单生效日期。
    effective_date = serializers.DateField()
    # 保障期限（月）：当前限制 1-12 个月。
    insurance_period_months = serializers.IntegerField(min_value=1, max_value=12, default=12)
    # 投保人信息：谁买这张保单。
    applicant = PersonSerializer()
    # 被保人信息：保障对象。
    insured = PersonSerializer()
    # 职业代码：前端从职业字典选择后传入。
    occupation_code = serializers.CharField(max_length=16)
    # 职业类别：1-6 类，影响保费和核保结论。
    occupation_category = serializers.IntegerField(min_value=1, max_value=6)
    # 是否有社保：影响优惠折扣。
    has_social_security = serializers.BooleanField(default=True)
    # 渠道代码：例如 C_APP、C_H5、C_WECHAT。
    channel_code = serializers.CharField(max_length=32, default='C_APP')


class PremiumQuoteSerializer(serializers.ModelSerializer):
    """后端返回：保费试算结果，前端需要保存 quote_no 进入核保。"""

    class Meta:
        model = PremiumQuote
        fields = [
            'quote_no',        # 试算单号：下一步核保必须传这个字段。
            'product_code',    # 产品代码。
            'product_name',    # 产品名称。
            'plan_code',       # 计划代码。
            'plan_name',       # 计划名称。
            'applicant',       # 投保人信息。
            'insured',         # 被保人信息。
            'coverages',       # 保障责任列表。
            'premium_detail',  # 保费明细：标准保费、优惠金额、应缴保费。
            'effective_date',  # 保险起期。
            'expiry_date',     # 保险止期。
            'status',          # 试算单状态。
            'valid_until',     # 试算单有效期。
            'created_at',      # 创建时间。
        ]


class UnderwritingRequestSerializer(serializers.Serializer):
    """前端传参：核保接口 POST /api/insurance/underwriting/。"""

    # 试算单号：必须来自第一步保费试算返回的 quote_no。
    quote_no = serializers.CharField(max_length=32)
    # 核保告知：健康告知、职业告知、历史理赔、如实告知确认等。
    disclosures = serializers.DictField(
        child=serializers.JSONField(),
        help_text='健康告知、职业告知、既往理赔等核保告知项',
    )
    # 受益人类型：LEGAL 法定受益人，DESIGNATED 指定受益人。
    beneficiary_type = serializers.ChoiceField(choices=['LEGAL', 'DESIGNATED'], default='LEGAL')
    # 指定受益人列表：当 beneficiary_type=DESIGNATED 时传入。
    beneficiaries = serializers.ListField(child=serializers.DictField(), required=False, default=list)


class UnderwritingCaseSerializer(serializers.ModelSerializer):
    """后端返回：核保结果，前端根据 decision 判断能否进入出单。"""

    # 关联的试算单号，方便前端串联流程。
    quote_no = serializers.CharField(source='quote.quote_no', read_only=True)

    class Meta:
        model = UnderwritingCase
        fields = [
            'uw_no',                  # 核保单号：第三步承保出单必须传这个字段。
            'quote_no',               # 关联试算单号。
            'decision',               # 核保结论：APPROVED 通过，REFERRED 转人工，DECLINED 拒保。
            'risk_level',             # 风险等级：LOW、MEDIUM、HIGH、REJECT。
            'reasons',                # 核保原因说明。
            'manual_review_required', # 是否需要人工核保。
            'valid_until',            # 核保结果有效期。
            'created_at',             # 核保时间。
        ]


class IssuePolicyRequestSerializer(serializers.Serializer):
    """前端传参：承保出单接口 POST /api/insurance/policies/。"""

    # 核保单号：必须来自第二步核保返回的 uw_no，且核保结论必须 APPROVED。
    underwriting_no = serializers.CharField(max_length=32)
    # 支付信息：必须支付成功，且支付金额必须等于试算返回的 payable_premium。
    payment = serializers.DictField()
    # 电子保单送达信息：邮箱、短信手机号等。
    delivery = serializers.DictField(required=False, default=dict)
    # 投保声明确认：前端必须确认条款、免责说明、电子保单协议。
    consent_confirmed = serializers.BooleanField()

    def validate_payment(self, value):
        """校验前端支付参数，避免未支付或少支付直接出单。"""
        required = ['pay_order_no', 'pay_status', 'paid_amount']
        missing = [field for field in required if field not in value]
        if missing:
            raise serializers.ValidationError(f'支付信息缺少字段: {", ".join(missing)}')
        if value.get('pay_status') != 'SUCCESS':
            raise serializers.ValidationError('仅支付成功后允许承保出单')
        try:
            Decimal(str(value['paid_amount']))
        except Exception as exc:
            raise serializers.ValidationError('paid_amount 必须是有效金额') from exc
        return value

    def validate_consent_confirmed(self, value):
        """校验投保声明确认状态。"""
        if not value:
            raise serializers.ValidationError('必须确认投保声明、免责条款和电子保单协议')
        return value


class PolicySerializer(serializers.ModelSerializer):
    """后端返回：承保出单结果，前端拿到 policy_no 即完成出单流程。"""

    # 关联试算单号。
    quote_no = serializers.CharField(source='quote.quote_no', read_only=True)
    # 关联核保单号。
    underwriting_no = serializers.CharField(source='underwriting.uw_no', read_only=True)

    class Meta:
        model = Policy
        fields = [
            'policy_no',       # 保单号：最终承保成功后生成。
            'quote_no',        # 关联试算单号。
            'underwriting_no', # 关联核保单号。
            'status',          # 保单状态：ISSUED 已承保。
            'applicant',       # 投保人信息。
            'insured',         # 被保人信息。
            'coverages',       # 保障责任。
            'premium_detail',  # 保费明细。
            'payment',         # 支付信息。
            'effective_date',  # 保险起期。
            'expiry_date',     # 保险止期。
            'issued_at',       # 出单时间。
        ]
