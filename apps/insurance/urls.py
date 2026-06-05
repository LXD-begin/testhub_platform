from django.urls import path

from .views import (
    IssuePolicyView,
    PolicyDetailView,
    PremiumQuoteDetailView,
    PremiumTrialView,
    UnderwritingDetailView,
    UnderwritingView,
)

urlpatterns = [
    path('premium-trials/', PremiumTrialView.as_view(), name='premium-trial'),
    path('premium-trials/<str:quote_no>/', PremiumQuoteDetailView.as_view(), name='premium-quote-detail'),
    path('underwriting/', UnderwritingView.as_view(), name='underwriting'),
    path('underwriting/<str:underwriting_no>/', UnderwritingDetailView.as_view(), name='underwriting-detail'),
    path('policies/', IssuePolicyView.as_view(), name='issue-policy'),
    path('policies/<str:policy_no>/', PolicyDetailView.as_view(), name='policy-detail'),
]
