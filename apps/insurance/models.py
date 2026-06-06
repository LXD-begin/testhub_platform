from django.db import models


class Product(models.Model):
    """保险产品主数据。

    真实保险公司里，产品代码、产品名称、投保年龄、保障期限、上下架状态一般都来自产品中心配置。
    """

    class Status(models.TextChoices):
        ACTIVE = 'ACTIVE', '在售'
        INACTIVE = 'INACTIVE', '停售'

    product_code = models.CharField('产品代码', max_length=32, unique=True, db_index=True, db_comment='产品代码')
    product_name = models.CharField('产品名称', max_length=128, db_comment='产品名称')
    description = models.TextField('产品详情', blank=True, db_comment='产品详情')
    status = models.CharField('产品状态', max_length=16, choices=Status.choices, default=Status.ACTIVE, db_comment='产品状态')
    min_age = models.PositiveSmallIntegerField('最小承保年龄', default=0, db_comment='最小承保年龄')
    max_age = models.PositiveSmallIntegerField('最大承保年龄', default=65, db_comment='最大承保年龄')
    min_period_months = models.PositiveSmallIntegerField('最短保障期限（月）', default=1, db_comment='最短保障期限（月）')
    max_period_months = models.PositiveSmallIntegerField('最长保障期限（月）', default=12, db_comment='最长保障期限（月）')
    effective_start = models.DateField('销售起期', null=True, blank=True, db_comment='销售起期')
    effective_end = models.DateField('销售止期', null=True, blank=True, db_comment='销售止期')
    created_at = models.DateTimeField('创建时间', auto_now_add=True, db_comment='创建时间')
    updated_at = models.DateTimeField('更新时间', auto_now=True, db_comment='更新时间')

    class Meta:
        ordering = ['product_code']
        verbose_name = '保险产品'
        verbose_name_plural = '保险产品'
        db_table_comment = '保险产品配置表'

    def __str__(self):
        return self.product_code


class ProductPlan(models.Model):
    """保险计划配置。一个产品下可以有基础版、标准版、尊享版等多个计划。"""

    product = models.ForeignKey(
        Product,
        verbose_name='所属产品',
        related_name='plans',
        on_delete=models.PROTECT,
        db_comment='所属产品',
    )
    plan_code = models.CharField('计划代码', max_length=32, db_comment='计划代码')
    plan_name = models.CharField('计划名称', max_length=128, db_comment='计划名称')
    base_premium = models.DecimalField('基础保费', max_digits=10, decimal_places=2, db_comment='基础保费')
    is_enabled = models.BooleanField('是否启用', default=True, db_comment='是否启用')
    sort_order = models.PositiveSmallIntegerField('排序', default=0, db_comment='排序')
    created_at = models.DateTimeField('创建时间', auto_now_add=True, db_comment='创建时间')
    updated_at = models.DateTimeField('更新时间', auto_now=True, db_comment='更新时间')

    class Meta:
        ordering = ['product__product_code', 'sort_order', 'plan_code']
        unique_together = [('product', 'plan_code')]
        verbose_name = '保险计划'
        verbose_name_plural = '保险计划'
        db_table_comment = '保险计划配置表'

    def __str__(self):
        return f'{self.product.product_code}-{self.plan_code}'


class ProductCoverage(models.Model):
    """保障责任配置。试算返回的责任列表来自这里。"""

    plan = models.ForeignKey(
        ProductPlan,
        verbose_name='所属计划',
        related_name='coverages',
        on_delete=models.PROTECT,
        db_comment='所属计划',
    )
    coverage_code = models.CharField('责任代码', max_length=32, db_comment='责任代码')
    coverage_name = models.CharField('责任名称', max_length=128, db_comment='责任名称')
    insured_amount = models.DecimalField('保额', max_digits=12, decimal_places=2, db_comment='保额')
    description = models.CharField('责任说明', max_length=256, blank=True, db_comment='责任说明')
    sort_order = models.PositiveSmallIntegerField('排序', default=0, db_comment='排序')

    class Meta:
        ordering = ['plan', 'sort_order', 'coverage_code']
        unique_together = [('plan', 'coverage_code')]
        verbose_name = '保障责任'
        verbose_name_plural = '保障责任'
        db_table_comment = '保障责任配置表'

    def __str__(self):
        return f'{self.plan}-{self.coverage_code}'


class AgeRateFactor(models.Model):
    """年龄费率因子。试算按被保人年龄命中区间后乘以该系数。"""

    product = models.ForeignKey(
        Product,
        verbose_name='所属产品',
        related_name='age_rate_factors',
        on_delete=models.PROTECT,
        db_comment='所属产品',
    )
    min_age = models.PositiveSmallIntegerField('最小年龄', db_comment='最小年龄')
    max_age = models.PositiveSmallIntegerField('最大年龄', db_comment='最大年龄')
    factor = models.DecimalField('费率系数', max_digits=8, decimal_places=4, db_comment='费率系数')
    is_enabled = models.BooleanField('是否启用', default=True, db_comment='是否启用')

    class Meta:
        ordering = ['product__product_code', 'min_age']
        verbose_name = '年龄费率因子'
        verbose_name_plural = '年龄费率因子'
        db_table_comment = '年龄费率因子表'

    def __str__(self):
        return f'{self.product.product_code}:{self.min_age}-{self.max_age}'


class OccupationRateFactor(models.Model):
    """职业类别费率因子。职业类别越高，通常风险越高，保费系数越高。"""

    product = models.ForeignKey(
        Product,
        verbose_name='所属产品',
        related_name='occupation_rate_factors',
        on_delete=models.PROTECT,
        db_comment='所属产品',
    )
    occupation_category = models.PositiveSmallIntegerField('职业类别', db_comment='职业类别')
    factor = models.DecimalField('费率系数', max_digits=8, decimal_places=4, db_comment='费率系数')
    is_enabled = models.BooleanField('是否启用', default=True, db_comment='是否启用')

    class Meta:
        ordering = ['product__product_code', 'occupation_category']
        unique_together = [('product', 'occupation_category')]
        verbose_name = '职业费率因子'
        verbose_name_plural = '职业费率因子'
        db_table_comment = '职业费率因子表'

    def __str__(self):
        return f'{self.product.product_code}:{self.occupation_category}'


class PremiumQuote(models.Model):
    """保费试算单。"""

    class Status(models.TextChoices):
        QUOTED = 'QUOTED', '已试算'
        UNDERWRITTEN = 'UNDERWRITTEN', '已核保'
        ISSUED = 'ISSUED', '已出单'
        EXPIRED = 'EXPIRED', '已失效'

    quote_no = models.CharField('试算单号', max_length=32, unique=True, db_index=True, db_comment='试算单号')
    product_code = models.CharField('产品代码', max_length=32, db_comment='产品代码')
    product_name = models.CharField('产品名称', max_length=128, db_comment='产品名称')
    plan_code = models.CharField('计划代码', max_length=32, db_comment='计划代码')
    plan_name = models.CharField('计划名称', max_length=128, db_comment='计划名称')
    applicant = models.JSONField('投保人信息', db_comment='投保人信息')
    insured = models.JSONField('被保人信息', db_comment='被保人信息')
    coverages = models.JSONField('保障责任', db_comment='保障责任')
    premium_detail = models.JSONField('保费明细', db_comment='保费明细')
    effective_date = models.DateField('保险起期', db_comment='保险起期')
    expiry_date = models.DateField('保险止期', db_comment='保险止期')
    status = models.CharField('试算状态', max_length=20, choices=Status.choices, default=Status.QUOTED, db_comment='试算状态')
    valid_until = models.DateTimeField('有效截止时间', db_comment='有效截止时间')
    created_at = models.DateTimeField('创建时间', auto_now_add=True, db_comment='创建时间')
    updated_at = models.DateTimeField('更新时间', auto_now=True, db_comment='更新时间')

    class Meta:
        ordering = ['-created_at']
        verbose_name = '保费试算单'
        verbose_name_plural = '保费试算单'
        db_table_comment = '保费试算单表'

    def __str__(self):
        return self.quote_no


class UnderwritingCase(models.Model):
    """核保记录。"""

    class Decision(models.TextChoices):
        APPROVED = 'APPROVED', '通过'
        REFERRED = 'REFERRED', '转人工'
        DECLINED = 'DECLINED', '拒保'

    uw_no = models.CharField('核保单号', max_length=32, unique=True, db_index=True, db_comment='核保单号')
    quote = models.ForeignKey(
        PremiumQuote,
        verbose_name='关联试算单',
        related_name='underwriting_cases',
        on_delete=models.PROTECT,
        db_comment='关联试算单',
    )
    application = models.ForeignKey(
        'InsuranceApplication',
        verbose_name='关联投保单',
        related_name='underwriting_cases',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_comment='关联投保单；兼容旧试算核保接口时允许为空',
    )
    decision = models.CharField('核保结论', max_length=20, choices=Decision.choices, db_comment='核保结论')
    risk_level = models.CharField('风险等级', max_length=16, db_comment='风险等级')
    reasons = models.JSONField('核保原因', default=list, db_comment='核保原因')
    disclosures = models.JSONField('告知信息', db_comment='告知信息')
    manual_review_required = models.BooleanField('是否人工核保', default=False, db_comment='是否人工核保')
    valid_until = models.DateTimeField('有效截止时间', db_comment='有效截止时间')
    created_at = models.DateTimeField('创建时间', auto_now_add=True, db_comment='创建时间')

    class Meta:
        ordering = ['-created_at']
        verbose_name = '核保记录'
        verbose_name_plural = '核保记录'
        db_table_comment = '核保记录表'

    def __str__(self):
        return self.uw_no


class InsuranceApplication(models.Model):
    """投保单。

    真实保险公司一般不会直接用试算单出单，而是先形成投保申请。
    投保单负责沉淀客户告知、受益人、条款确认、核保、支付和出单状态。
    """

    class Status(models.TextChoices):
        CREATED = 'CREATED', '已创建'
        SUBMITTED = 'SUBMITTED', '已提交'
        UNDERWRITING_APPROVED = 'UNDERWRITING_APPROVED', '核保通过'
        UNDERWRITING_REFERRED = 'UNDERWRITING_REFERRED', '待人工核保'
        UNDERWRITING_DECLINED = 'UNDERWRITING_DECLINED', '核保拒保'
        PAYMENT_PENDING = 'PAYMENT_PENDING', '待支付'
        PAID = 'PAID', '已支付'
        ISSUED = 'ISSUED', '已出单'
        CLOSED = 'CLOSED', '已关闭'

    application_no = models.CharField('投保单号', max_length=32, unique=True, db_index=True, db_comment='投保单号')
    quote = models.OneToOneField(
        PremiumQuote,
        verbose_name='关联试算单',
        related_name='application',
        on_delete=models.PROTECT,
        db_comment='关联试算单',
    )
    status = models.CharField('投保单状态', max_length=32, choices=Status.choices, default=Status.CREATED, db_comment='投保单状态')
    applicant = models.JSONField('投保人信息', db_comment='投保人信息')
    insured = models.JSONField('被保人信息', db_comment='被保人信息')
    disclosures = models.JSONField('核保告知信息', default=dict, db_comment='核保告知信息')
    beneficiary_type = models.CharField('受益人类型', max_length=16, default='LEGAL', db_comment='LEGAL 法定；DESIGNATED 指定')
    beneficiaries = models.JSONField('指定受益人列表', default=list, db_comment='指定受益人列表')
    consents = models.JSONField('投保确认信息', default=dict, db_comment='条款、免责、电子保单等确认留痕')
    channel_code = models.CharField('渠道代码', max_length=32, db_comment='渠道代码')
    submitted_at = models.DateTimeField('提交时间', null=True, blank=True, db_comment='提交核保时间')
    created_at = models.DateTimeField('创建时间', auto_now_add=True, db_comment='创建时间')
    updated_at = models.DateTimeField('更新时间', auto_now=True, db_comment='更新时间')

    class Meta:
        ordering = ['-created_at']
        verbose_name = '投保单'
        verbose_name_plural = '投保单'
        db_table_comment = '投保单表'

    def __str__(self):
        return self.application_no


class PaymentOrder(models.Model):
    """支付订单。

    真实出单前必须以服务端支付订单和支付回调为准，不能只相信前端传入的支付成功标识。
    """

    class Status(models.TextChoices):
        CREATED = 'CREATED', '已创建'
        SUCCESS = 'SUCCESS', '支付成功'
        FAILED = 'FAILED', '支付失败'
        CLOSED = 'CLOSED', '已关闭'

    pay_order_no = models.CharField('支付订单号', max_length=32, unique=True, db_index=True, db_comment='支付订单号')
    application = models.ForeignKey(
        InsuranceApplication,
        verbose_name='关联投保单',
        related_name='payment_orders',
        on_delete=models.PROTECT,
        db_comment='关联投保单',
    )
    quote = models.ForeignKey(
        PremiumQuote,
        verbose_name='关联试算单',
        related_name='payment_orders',
        on_delete=models.PROTECT,
        db_comment='关联试算单',
    )
    underwriting = models.ForeignKey(
        UnderwritingCase,
        verbose_name='关联核保记录',
        related_name='payment_orders',
        on_delete=models.PROTECT,
        db_comment='关联核保记录',
    )
    amount = models.DecimalField('应付金额', max_digits=10, decimal_places=2, db_comment='应付金额')
    status = models.CharField('支付状态', max_length=20, choices=Status.choices, default=Status.CREATED, db_comment='支付状态')
    pay_channel = models.CharField('支付渠道', max_length=32, default='MOCK', db_comment='支付渠道')
    external_trade_no = models.CharField('外部交易流水号', max_length=64, blank=True, db_comment='外部交易流水号')
    notify_payload = models.JSONField('支付通知原文', default=dict, db_comment='支付通知原文')
    paid_at = models.DateTimeField('支付成功时间', null=True, blank=True, db_comment='支付成功时间')
    created_at = models.DateTimeField('创建时间', auto_now_add=True, db_comment='创建时间')
    updated_at = models.DateTimeField('更新时间', auto_now=True, db_comment='更新时间')

    class Meta:
        ordering = ['-created_at']
        verbose_name = '支付订单'
        verbose_name_plural = '支付订单'
        db_table_comment = '支付订单表'

    def __str__(self):
        return self.pay_order_no


class ManualUnderwritingReview(models.Model):
    """人工核保复核记录。

    当自动核保返回 REFERRED 时，人工核保员可给出最终通过、拒保或继续转人工的结论。
    """

    review_no = models.CharField('人工核保单号', max_length=32, unique=True, db_index=True, db_comment='人工核保单号')
    underwriting = models.OneToOneField(
        UnderwritingCase,
        verbose_name='关联核保记录',
        related_name='manual_review',
        on_delete=models.PROTECT,
        db_comment='关联核保记录',
    )
    decision = models.CharField('人工核保结论', max_length=20, choices=UnderwritingCase.Decision.choices, db_comment='人工核保结论')
    risk_level = models.CharField('人工评定风险等级', max_length=16, db_comment='人工评定风险等级')
    reasons = models.JSONField('人工核保原因', default=list, db_comment='人工核保原因')
    review_notes = models.TextField('复核备注', blank=True, db_comment='复核备注')
    reviewer = models.CharField('复核人员', max_length=64, db_comment='复核人员')
    reviewed_at = models.DateTimeField('复核时间', auto_now_add=True, db_comment='复核时间')

    class Meta:
        ordering = ['-reviewed_at']
        verbose_name = '人工核保复核记录'
        verbose_name_plural = '人工核保复核记录'
        db_table_comment = '人工核保复核记录表'

    def __str__(self):
        return self.review_no


class Policy(models.Model):
    """保单。"""

    class Status(models.TextChoices):
        ISSUED = 'ISSUED', '已承保'
        CANCELLED = 'CANCELLED', '已撤单'

    policy_no = models.CharField('保单号', max_length=32, unique=True, db_index=True, db_comment='保单号')
    application = models.OneToOneField(
        InsuranceApplication,
        verbose_name='关联投保单',
        related_name='policy',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_comment='关联投保单；兼容旧出单接口时允许为空',
    )
    quote = models.OneToOneField(
        PremiumQuote,
        verbose_name='关联试算单',
        related_name='policy',
        on_delete=models.PROTECT,
        db_comment='关联试算单',
    )
    underwriting = models.OneToOneField(
        UnderwritingCase,
        verbose_name='关联核保记录',
        related_name='policy',
        on_delete=models.PROTECT,
        db_comment='关联核保记录',
    )
    payment_order = models.OneToOneField(
        PaymentOrder,
        verbose_name='关联支付订单',
        related_name='policy',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_comment='关联支付订单；兼容旧出单接口时允许为空',
    )
    status = models.CharField('保单状态', max_length=20, choices=Status.choices, default=Status.ISSUED, db_comment='保单状态')
    applicant = models.JSONField('投保人信息', db_comment='投保人信息')
    insured = models.JSONField('被保人信息', db_comment='被保人信息')
    coverages = models.JSONField('保障责任', db_comment='保障责任')
    premium_detail = models.JSONField('保费明细', db_comment='保费明细')
    payment = models.JSONField('支付信息', db_comment='支付信息')
    effective_date = models.DateField('保险起期', db_comment='保险起期')
    expiry_date = models.DateField('保险止期', db_comment='保险止期')
    issued_at = models.DateTimeField('出单时间', auto_now_add=True, db_comment='出单时间')

    class Meta:
        ordering = ['-issued_at']
        verbose_name = '保单'
        verbose_name_plural = '保单'
        db_table_comment = '保单表'

    def __str__(self):
        return self.policy_no


class ElectronicPolicy(models.Model):
    """电子保单文件索引。"""

    document_no = models.CharField('电子保单文档号', max_length=32, unique=True, db_index=True, db_comment='电子保单文档号')
    policy = models.OneToOneField(
        Policy,
        verbose_name='关联保单',
        related_name='electronic_policy',
        on_delete=models.PROTECT,
        db_comment='关联保单',
    )
    download_url = models.CharField('下载地址', max_length=256, db_comment='电子保单下载地址')
    verify_code = models.CharField('验真码', max_length=32, db_comment='电子保单验真码')
    generated_at = models.DateTimeField('生成时间', auto_now_add=True, db_comment='生成时间')

    class Meta:
        ordering = ['-generated_at']
        verbose_name = '电子保单'
        verbose_name_plural = '电子保单'
        db_table_comment = '电子保单表'

    def __str__(self):
        return self.document_no


class DeliveryRecord(models.Model):
    """电子保单送达记录。"""

    class Channel(models.TextChoices):
        EMAIL = 'EMAIL', '邮件'
        SMS = 'SMS', '短信'

    class Status(models.TextChoices):
        SENT = 'SENT', '已发送'
        FAILED = 'FAILED', '发送失败'

    delivery_no = models.CharField('送达流水号', max_length=32, unique=True, db_index=True, db_comment='送达流水号')
    policy = models.ForeignKey(
        Policy,
        verbose_name='关联保单',
        related_name='delivery_records',
        on_delete=models.PROTECT,
        db_comment='关联保单',
    )
    channel = models.CharField('送达渠道', max_length=16, choices=Channel.choices, db_comment='送达渠道')
    recipient = models.CharField('收件人', max_length=128, db_comment='邮箱或手机号')
    status = models.CharField('送达状态', max_length=16, choices=Status.choices, default=Status.SENT, db_comment='送达状态')
    payload = models.JSONField('送达内容', default=dict, db_comment='送达内容')
    sent_at = models.DateTimeField('发送时间', auto_now_add=True, db_comment='发送时间')

    class Meta:
        ordering = ['-sent_at']
        verbose_name = '电子保单送达记录'
        verbose_name_plural = '电子保单送达记录'
        db_table_comment = '电子保单送达记录表'

    def __str__(self):
        return self.delivery_no
