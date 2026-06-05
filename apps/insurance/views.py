from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .crypto import (
    InsuranceCryptoError,
    decrypt_payload,
    encrypt_payload,
    is_encrypted_envelope,
)
from .models import Policy, PremiumQuote, UnderwritingCase
from .serializers import (
    ApplicationUnderwritingRequestSerializer,
    InsuranceApplicationCreateSerializer,
    InsuranceApplicationSerializer,
    IssuePolicyRequestSerializer,
    IssuePolicyFromApplicationRequestSerializer,
    ManualUnderwritingReviewRequestSerializer,
    ManualUnderwritingReviewSerializer,
    PaymentOrderConfirmSerializer,
    PaymentOrderCreateSerializer,
    PaymentOrderSerializer,
    PolicySerializer,
    PremiumQuoteSerializer,
    PremiumTrialRequestSerializer,
    UnderwritingCaseSerializer,
    UnderwritingRequestSerializer,
)
from .services import (
    confirm_payment_order,
    create_application,
    create_payment_order,
    create_premium_quote,
    issue_policy,
    issue_policy_from_application,
    review_manual_underwriting,
    submit_application_underwriting,
    underwrite,
)


TRUE_VALUES = {'1', 'true', 'yes', 'on'}


class EncryptedInsuranceAPIView(APIView):
    encrypted_request_attr = '_insurance_request_encrypted'

    def request_payload(self, request):
        if is_encrypted_envelope(request.data):
            setattr(request, self.encrypted_request_attr, True)
            return decrypt_payload(request.data)

        encrypted_header = request.headers.get('X-Insurance-Encrypted', '').lower()
        if encrypted_header in TRUE_VALUES:
            setattr(request, self.encrypted_request_attr, True)
            return decrypt_payload(request.data)

        setattr(request, self.encrypted_request_attr, False)
        return request.data

    def should_encrypt_response(self, request):
        if getattr(request, self.encrypted_request_attr, False):
            return True
        encrypted_header = request.headers.get('X-Insurance-Response-Encrypted', '').lower()
        encrypted_query = request.query_params.get('encrypted', '').lower()
        return encrypted_header in TRUE_VALUES or encrypted_query in TRUE_VALUES

    def insurance_response(self, request, data, response_status=status.HTTP_200_OK):
        if self.should_encrypt_response(request):
            response = Response(encrypt_payload(data), status=response_status)
            response['X-Insurance-Encrypted'] = 'true'
            return response
        return Response(data, status=response_status)

    def crypto_error_response(self, request, exc):
        setattr(request, self.encrypted_request_attr, True)
        return self.insurance_response(
            request,
            {'code': 'CRYPTO_ERROR', 'message': str(exc)},
            response_status=status.HTTP_400_BAD_REQUEST,
        )

    def handle_exception(self, exc):
        response = super().handle_exception(exc)
        if response is not None and self.should_encrypt_response(self.request):
            response.data = encrypt_payload(response.data)
            response['X-Insurance-Encrypted'] = 'true'
        return response


class PremiumTrialView(EncryptedInsuranceAPIView):
    def post(self, request):
        try:
            payload = self.request_payload(request)
        except InsuranceCryptoError as exc:
            return self.crypto_error_response(request, exc)

        serializer = PremiumTrialRequestSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        try:
            quote = create_premium_quote(serializer.validated_data)
        except ValueError as exc:
            return self.insurance_response(
                request,
                {'code': 'BUSINESS_ERROR', 'message': str(exc)},
                response_status=status.HTTP_400_BAD_REQUEST,
            )
        return self.insurance_response(
            request,
            PremiumQuoteSerializer(quote).data,
            response_status=status.HTTP_201_CREATED,
        )


class PremiumQuoteDetailView(EncryptedInsuranceAPIView):
    def get(self, request, quote_no):
        quote = get_object_or_404(PremiumQuote, quote_no=quote_no)
        return self.insurance_response(request, PremiumQuoteSerializer(quote).data)


class UnderwritingView(EncryptedInsuranceAPIView):
    def post(self, request):
        try:
            payload = self.request_payload(request)
        except InsuranceCryptoError as exc:
            return self.crypto_error_response(request, exc)

        serializer = UnderwritingRequestSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        try:
            uw_case = underwrite(serializer.validated_data)
        except PremiumQuote.DoesNotExist:
            return self.insurance_response(
                request,
                {'code': 'NOT_FOUND', 'message': '试算单不存在'},
                response_status=status.HTTP_404_NOT_FOUND,
            )
        except ValueError as exc:
            return self.insurance_response(
                request,
                {'code': 'BUSINESS_ERROR', 'message': str(exc)},
                response_status=status.HTTP_400_BAD_REQUEST,
            )
        return self.insurance_response(
            request,
            UnderwritingCaseSerializer(uw_case).data,
            response_status=status.HTTP_201_CREATED,
        )


class UnderwritingDetailView(EncryptedInsuranceAPIView):
    def get(self, request, underwriting_no):
        uw_case = get_object_or_404(UnderwritingCase, uw_no=underwriting_no)
        return self.insurance_response(request, UnderwritingCaseSerializer(uw_case).data)


class InsuranceApplicationView(EncryptedInsuranceAPIView):
    def post(self, request):
        try:
            payload = self.request_payload(request)
        except InsuranceCryptoError as exc:
            return self.crypto_error_response(request, exc)

        serializer = InsuranceApplicationCreateSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        try:
            application = create_application(serializer.validated_data)
        except PremiumQuote.DoesNotExist:
            return self.insurance_response(
                request,
                {'code': 'NOT_FOUND', 'message': '试算单不存在'},
                response_status=status.HTTP_404_NOT_FOUND,
            )
        except ValueError as exc:
            return self.insurance_response(
                request,
                {'code': 'BUSINESS_ERROR', 'message': str(exc)},
                response_status=status.HTTP_400_BAD_REQUEST,
            )
        return self.insurance_response(
            request,
            InsuranceApplicationSerializer(application).data,
            response_status=status.HTTP_201_CREATED,
        )


class InsuranceApplicationDetailView(EncryptedInsuranceAPIView):
    def get(self, request, application_no):
        from .models import InsuranceApplication

        application = get_object_or_404(InsuranceApplication, application_no=application_no)
        return self.insurance_response(request, InsuranceApplicationSerializer(application).data)


class ApplicationUnderwritingView(EncryptedInsuranceAPIView):
    def post(self, request, application_no):
        try:
            payload = self.request_payload(request)
        except InsuranceCryptoError as exc:
            return self.crypto_error_response(request, exc)

        payload = {**payload, 'application_no': application_no}
        serializer = ApplicationUnderwritingRequestSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        try:
            uw_case = submit_application_underwriting(serializer.validated_data)
        except Exception as exc:
            from .models import InsuranceApplication

            if isinstance(exc, InsuranceApplication.DoesNotExist):
                return self.insurance_response(
                    request,
                    {'code': 'NOT_FOUND', 'message': '投保单不存在'},
                    response_status=status.HTTP_404_NOT_FOUND,
                )
            if isinstance(exc, ValueError):
                return self.insurance_response(
                    request,
                    {'code': 'BUSINESS_ERROR', 'message': str(exc)},
                    response_status=status.HTTP_400_BAD_REQUEST,
                )
            raise
        return self.insurance_response(
            request,
            UnderwritingCaseSerializer(uw_case).data,
            response_status=status.HTTP_201_CREATED,
        )


class ManualUnderwritingReviewView(EncryptedInsuranceAPIView):
    def post(self, request, underwriting_no):
        try:
            payload = self.request_payload(request)
        except InsuranceCryptoError as exc:
            return self.crypto_error_response(request, exc)

        payload = {**payload, 'underwriting_no': underwriting_no}
        serializer = ManualUnderwritingReviewRequestSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        try:
            review = review_manual_underwriting(serializer.validated_data)
        except UnderwritingCase.DoesNotExist:
            return self.insurance_response(
                request,
                {'code': 'NOT_FOUND', 'message': '核保记录不存在'},
                response_status=status.HTTP_404_NOT_FOUND,
            )
        except ValueError as exc:
            return self.insurance_response(
                request,
                {'code': 'BUSINESS_ERROR', 'message': str(exc)},
                response_status=status.HTTP_400_BAD_REQUEST,
            )
        return self.insurance_response(
            request,
            ManualUnderwritingReviewSerializer(review).data,
            response_status=status.HTTP_201_CREATED,
        )


class PaymentOrderView(EncryptedInsuranceAPIView):
    def post(self, request):
        try:
            payload = self.request_payload(request)
        except InsuranceCryptoError as exc:
            return self.crypto_error_response(request, exc)

        serializer = PaymentOrderCreateSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        try:
            payment_order = create_payment_order(serializer.validated_data)
        except Exception as exc:
            from .models import InsuranceApplication

            if isinstance(exc, InsuranceApplication.DoesNotExist):
                return self.insurance_response(
                    request,
                    {'code': 'NOT_FOUND', 'message': '投保单不存在'},
                    response_status=status.HTTP_404_NOT_FOUND,
                )
            if isinstance(exc, ValueError):
                return self.insurance_response(
                    request,
                    {'code': 'BUSINESS_ERROR', 'message': str(exc)},
                    response_status=status.HTTP_400_BAD_REQUEST,
                )
            raise
        return self.insurance_response(
            request,
            PaymentOrderSerializer(payment_order).data,
            response_status=status.HTTP_201_CREATED,
        )


class PaymentOrderDetailView(EncryptedInsuranceAPIView):
    def get(self, request, pay_order_no):
        from .models import PaymentOrder

        payment_order = get_object_or_404(PaymentOrder, pay_order_no=pay_order_no)
        return self.insurance_response(request, PaymentOrderSerializer(payment_order).data)


class PaymentOrderConfirmView(EncryptedInsuranceAPIView):
    def post(self, request, pay_order_no):
        try:
            payload = self.request_payload(request)
        except InsuranceCryptoError as exc:
            return self.crypto_error_response(request, exc)

        payload = {**payload, 'pay_order_no': pay_order_no}
        serializer = PaymentOrderConfirmSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        try:
            payment_order = confirm_payment_order(serializer.validated_data)
        except Exception as exc:
            from .models import PaymentOrder

            if isinstance(exc, PaymentOrder.DoesNotExist):
                return self.insurance_response(
                    request,
                    {'code': 'NOT_FOUND', 'message': '支付订单不存在'},
                    response_status=status.HTTP_404_NOT_FOUND,
                )
            if isinstance(exc, ValueError):
                return self.insurance_response(
                    request,
                    {'code': 'BUSINESS_ERROR', 'message': str(exc)},
                    response_status=status.HTTP_400_BAD_REQUEST,
                )
            raise
        return self.insurance_response(request, PaymentOrderSerializer(payment_order).data)


class IssuePolicyView(EncryptedInsuranceAPIView):
    def post(self, request):
        try:
            payload = self.request_payload(request)
        except InsuranceCryptoError as exc:
            return self.crypto_error_response(request, exc)

        serializer = IssuePolicyRequestSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        try:
            policy = issue_policy(serializer.validated_data)
        except UnderwritingCase.DoesNotExist:
            return self.insurance_response(
                request,
                {'code': 'NOT_FOUND', 'message': '核保记录不存在'},
                response_status=status.HTTP_404_NOT_FOUND,
            )
        except ValueError as exc:
            return self.insurance_response(
                request,
                {'code': 'BUSINESS_ERROR', 'message': str(exc)},
                response_status=status.HTTP_400_BAD_REQUEST,
            )
        return self.insurance_response(
            request,
            PolicySerializer(policy).data,
            response_status=status.HTTP_201_CREATED,
        )


class IssueApplicationPolicyView(EncryptedInsuranceAPIView):
    def post(self, request):
        try:
            payload = self.request_payload(request)
        except InsuranceCryptoError as exc:
            return self.crypto_error_response(request, exc)

        serializer = IssuePolicyFromApplicationRequestSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        try:
            policy = issue_policy_from_application(serializer.validated_data)
        except Exception as exc:
            from .models import InsuranceApplication

            if isinstance(exc, InsuranceApplication.DoesNotExist):
                return self.insurance_response(
                    request,
                    {'code': 'NOT_FOUND', 'message': '投保单不存在'},
                    response_status=status.HTTP_404_NOT_FOUND,
                )
            if isinstance(exc, ValueError):
                return self.insurance_response(
                    request,
                    {'code': 'BUSINESS_ERROR', 'message': str(exc)},
                    response_status=status.HTTP_400_BAD_REQUEST,
                )
            raise
        return self.insurance_response(
            request,
            PolicySerializer(policy).data,
            response_status=status.HTTP_201_CREATED,
        )


class PolicyDetailView(EncryptedInsuranceAPIView):
    def get(self, request, policy_no):
        policy = get_object_or_404(Policy, policy_no=policy_no)
        return self.insurance_response(request, PolicySerializer(policy).data)
