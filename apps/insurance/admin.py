from django.contrib import admin

from .models import Policy, PremiumQuote, UnderwritingCase


@admin.register(PremiumQuote)
class PremiumQuoteAdmin(admin.ModelAdmin):
    list_display = ('quote_no', 'product_code', 'plan_code', 'status', 'effective_date', 'valid_until', 'created_at')
    search_fields = ('quote_no', 'product_code')
    list_filter = ('status', 'plan_code')


@admin.register(UnderwritingCase)
class UnderwritingCaseAdmin(admin.ModelAdmin):
    list_display = ('uw_no', 'quote', 'decision', 'risk_level', 'manual_review_required', 'created_at')
    search_fields = ('uw_no', 'quote__quote_no')
    list_filter = ('decision', 'risk_level')


@admin.register(Policy)
class PolicyAdmin(admin.ModelAdmin):
    list_display = ('policy_no', 'quote', 'underwriting', 'status', 'effective_date', 'expiry_date', 'issued_at')
    search_fields = ('policy_no', 'quote__quote_no', 'underwriting__uw_no')
    list_filter = ('status',)
