from django.db import models


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


class Policy(models.Model):
    """保单。"""

    class Status(models.TextChoices):
        ISSUED = 'ISSUED', '已承保'
        CANCELLED = 'CANCELLED', '已撤单'

    policy_no = models.CharField('保单号', max_length=32, unique=True, db_index=True, db_comment='保单号')
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
