from django.contrib import admin

from .models import (
    DeliveryRecord,
    ElectronicPolicy,
    InsuranceApplication,
    ManualUnderwritingReview,
    PaymentOrder,
    Policy,
    PremiumQuote,
    UnderwritingCase,
)


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
