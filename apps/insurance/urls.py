from django.urls import path

from .views import (
    ApplicationUnderwritingView,
    InsuranceApplicationDetailView,
    InsuranceApplicationView,
    IssueApplicationPolicyView,
    IssuePolicyView,
    ManualUnderwritingReviewView,
    PaymentOrderConfirmView,
    PaymentOrderDetailView,
    PaymentOrderView,
    PolicyDetailView,
    PremiumQuoteDetailView,
    PremiumTrialView,
    UnderwritingDetailView,
    UnderwritingView,
)

urlpatterns = [
    path('premium-trials/', PremiumTrialView.as_view(), name='premium-trial'),
    path('premium-trials/<str:quote_no>/', PremiumQuoteDetailView.as_view(), name='premium-quote-detail'),
    path('applications/', InsuranceApplicationView.as_view(), name='insurance-application'),
    path('applications/<str:application_no>/', InsuranceApplicationDetailView.as_view(), name='insurance-application-detail'),
    path(
        'applications/<str:application_no>/underwriting/',
        ApplicationUnderwritingView.as_view(),
        name='application-underwriting',
    ),
    path('underwriting/', UnderwritingView.as_view(), name='underwriting'),
    path('underwriting/<str:underwriting_no>/', UnderwritingDetailView.as_view(), name='underwriting-detail'),
    path(
        'underwriting/<str:underwriting_no>/manual-review/',
        ManualUnderwritingReviewView.as_view(),
        name='manual-underwriting-review',
    ),
    path('payment-orders/', PaymentOrderView.as_view(), name='payment-order'),
    path('payment-orders/<str:pay_order_no>/', PaymentOrderDetailView.as_view(), name='payment-order-detail'),
    path(
        'payment-orders/<str:pay_order_no>/confirm/',
        PaymentOrderConfirmView.as_view(),
        name='payment-order-confirm',
    ),
    path('policies/', IssuePolicyView.as_view(), name='issue-policy'),
    path('application-policies/', IssueApplicationPolicyView.as_view(), name='issue-application-policy'),
    path('policies/<str:policy_no>/', PolicyDetailView.as_view(), name='policy-detail'),
]
