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
    IssuePolicyRequestSerializer,
    PolicySerializer,
    PremiumQuoteSerializer,
    PremiumTrialRequestSerializer,
    UnderwritingCaseSerializer,
    UnderwritingRequestSerializer,
)
from .services import create_premium_quote, issue_policy, underwrite


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


class PolicyDetailView(EncryptedInsuranceAPIView):
    def get(self, request, policy_no):
        policy = get_object_or_404(Policy, policy_no=policy_no)
        return self.insurance_response(request, PolicySerializer(policy).data)
