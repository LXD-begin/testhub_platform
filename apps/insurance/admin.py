from django.contrib import admin

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
    ProductCoverage,
    ProductPlan,
    UnderwritingCase,
)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('product_code', 'product_name', 'status', 'min_age', 'max_age', 'min_period_months', 'max_period_months')
    search_fields = ('product_code', 'product_name')
    list_filter = ('status',)


@admin.register(ProductPlan)
class ProductPlanAdmin(admin.ModelAdmin):
    list_display = ('product', 'plan_code', 'plan_name', 'base_premium', 'is_enabled', 'sort_order')
    search_fields = ('product__product_code', 'plan_code', 'plan_name')
    list_filter = ('is_enabled',)


@admin.register(ProductCoverage)
class ProductCoverageAdmin(admin.ModelAdmin):
    list_display = ('plan', 'coverage_code', 'coverage_name', 'insured_amount', 'sort_order')
    search_fields = ('plan__product__product_code', 'plan__plan_code', 'coverage_code', 'coverage_name')


@admin.register(AgeRateFactor)
class AgeRateFactorAdmin(admin.ModelAdmin):
    list_display = ('product', 'min_age', 'max_age', 'factor', 'is_enabled')
    search_fields = ('product__product_code',)
    list_filter = ('is_enabled',)


@admin.register(OccupationRateFactor)
class OccupationRateFactorAdmin(admin.ModelAdmin):
    list_display = ('product', 'occupation_category', 'factor', 'is_enabled')
    search_fields = ('product__product_code',)
    list_filter = ('is_enabled',)


@admin.register(PremiumQuote)
class PremiumQuoteAdmin(admin.ModelAdmin):
    list_display = ('quote_no', 'product_code', 'plan_code', 'status', 'effective_date', 'valid_until', 'created_at')
    search_fields = ('quote_no', 'product_code')
    list_filter = ('status', 'plan_code')


@admin.register(UnderwritingCase)
class UnderwritingCaseAdmin(admin.ModelAdmin):
    list_display = ('uw_no', 'quote', 'application', 'decision', 'risk_level', 'manual_review_required', 'created_at')
    search_fields = ('uw_no', 'quote__quote_no', 'application__application_no')
    list_filter = ('decision', 'risk_level')


@admin.register(InsuranceApplication)
class InsuranceApplicationAdmin(admin.ModelAdmin):
    list_display = ('application_no', 'quote', 'status', 'channel_code', 'submitted_at', 'created_at')
    search_fields = ('application_no', 'quote__quote_no')
    list_filter = ('status', 'channel_code')


@admin.register(ManualUnderwritingReview)
class ManualUnderwritingReviewAdmin(admin.ModelAdmin):
    list_display = ('review_no', 'underwriting', 'decision', 'risk_level', 'reviewer', 'reviewed_at')
    search_fields = ('review_no', 'underwriting__uw_no', 'reviewer')
    list_filter = ('decision', 'risk_level')


@admin.register(PaymentOrder)
class PaymentOrderAdmin(admin.ModelAdmin):
    list_display = ('pay_order_no', 'application', 'amount', 'status', 'pay_channel', 'paid_at', 'created_at')
    search_fields = ('pay_order_no', 'application__application_no', 'external_trade_no')
    list_filter = ('status', 'pay_channel')


@admin.register(Policy)
class PolicyAdmin(admin.ModelAdmin):
    list_display = ('policy_no', 'application', 'quote', 'underwriting', 'payment_order', 'status', 'issued_at')
    search_fields = ('policy_no', 'application__application_no', 'quote__quote_no', 'underwriting__uw_no')
    list_filter = ('status',)


@admin.register(ElectronicPolicy)
class ElectronicPolicyAdmin(admin.ModelAdmin):
    list_display = ('document_no', 'policy', 'verify_code', 'generated_at')
    search_fields = ('document_no', 'policy__policy_no', 'verify_code')


@admin.register(DeliveryRecord)
class DeliveryRecordAdmin(admin.ModelAdmin):
    list_display = ('delivery_no', 'policy', 'channel', 'recipient', 'status', 'sent_at')
    search_fields = ('delivery_no', 'policy__policy_no', 'recipient')
    list_filter = ('channel', 'status')
