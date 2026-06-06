from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import AuthenticationFailed
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .cache import CACHE_NAMESPACES, get_detail_cache, set_detail_cache
from .crypto import (
    InsuranceCryptoError,
    decrypt_payload,
    encrypt_payload,
    is_encrypted_envelope,
)
from .models import Policy, PremiumQuote, Product, UnderwritingCase
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
    ProductSerializer,
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
SUCCESS_CODE = 200
ERROR_CODE = 999


class EncryptedInsuranceAPIView(APIView):
    """保险业务 API 基类。

    统一处理 API Key 鉴权、加密请求/响应、统一响应结构、详情缓存读写。
    """

    encrypted_request_attr = '_insurance_request_encrypted'

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        expected_api_key = getattr(settings, 'INSURANCE_API_KEY', '')
        if not expected_api_key:
            return

        authorization = request.headers.get('Authorization', '')
        bearer_token = authorization.removeprefix('Bearer ').strip() if authorization.startswith('Bearer ') else ''
        provided_api_key = request.headers.get('X-Insurance-API-Key') or bearer_token
        if provided_api_key != expected_api_key:
            raise AuthenticationFailed('接口鉴权失败')

    def success_payload(self, data, message='成功'):
        return {
            'code': SUCCESS_CODE,
            'message': message,
            'data': data,
        }

    def error_payload(self, message='失败', data=None):
        return {
            'code': ERROR_CODE,
            'message': message,
            'data': data,
        }

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

    def _error_response_data(self, data):
        if isinstance(data, dict):
            message = data.get('message') or data.get('detail') or '失败'
            error_type = data.get('code')
            details = {
                key: value
                for key, value in data.items()
                if key not in {'code', 'message', 'detail'}
            }
            if error_type:
                details = {'error_type': error_type, **details}
            return self.error_payload(str(message), details or None)
        return self.error_payload(str(data) if data else '失败')

    def _exception_message(self, data):
        if isinstance(data, dict):
            if 'detail' in data:
                return str(data['detail'])
            return '参数校验失败'
        if isinstance(data, list):
            return '参数校验失败'
        return str(data) if data else '失败'

    def raw_response(self, request, payload, response_status=status.HTTP_200_OK):
        if self.should_encrypt_response(request):
            response = Response(encrypt_payload(payload), status=response_status)
            response['X-Insurance-Encrypted'] = 'true'
            return response
        return Response(payload, status=response_status)

    def insurance_response(self, request, data, response_status=status.HTTP_200_OK):
        if response_status >= status.HTTP_400_BAD_REQUEST:
            return self.raw_response(request, self._error_response_data(data), response_status)
        return self.raw_response(request, self.success_payload(data), response_status)

    def cached_detail_response(self, request, cache_namespace, identifier, get_instance, serializer_class):
        data = get_detail_cache(cache_namespace, identifier)
        if data is None:
            instance = get_instance()
            data = serializer_class(instance).data
            set_detail_cache(cache_namespace, identifier, data)
        return self.insurance_response(request, data)

    def serialize_and_cache(self, instance, cache_namespace, identifier, serializer_class):
        data = serializer_class(instance).data
        set_detail_cache(cache_namespace, identifier, data)
        return data

    def cache_related_quote(self, quote):
        if quote:
            self.serialize_and_cache(
                quote,
                CACHE_NAMESPACES['premium_quote'],
                quote.quote_no,
                PremiumQuoteSerializer,
            )

    def cache_related_application(self, application):
        if application:
            self.serialize_and_cache(
                application,
                CACHE_NAMESPACES['application'],
                application.application_no,
                InsuranceApplicationSerializer,
            )

    def cache_related_underwriting(self, uw_case):
        if uw_case:
            self.serialize_and_cache(
                uw_case,
                CACHE_NAMESPACES['underwriting'],
                uw_case.uw_no,
                UnderwritingCaseSerializer,
            )

    def cache_related_payment_order(self, payment_order):
        if payment_order:
            self.serialize_and_cache(
                payment_order,
                CACHE_NAMESPACES['payment_order'],
                payment_order.pay_order_no,
                PaymentOrderSerializer,
            )

    def cache_related_policy(self, policy):
        if policy:
            self.serialize_and_cache(
                policy,
                CACHE_NAMESPACES['policy'],
                policy.policy_no,
                PolicySerializer,
            )

    def crypto_error_response(self, request, exc):
        setattr(request, self.encrypted_request_attr, True)
        return self.insurance_response(
            request,
            {'code': 'CRYPTO_ERROR', 'message': str(exc)},
            response_status=status.HTTP_400_BAD_REQUEST,
        )

    def handle_exception(self, exc):
        try:
            response = super().handle_exception(exc)
        except Exception:
            response = Response(
                self.error_payload('服务器内部错误'),
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
            response.exception = True
            if self.should_encrypt_response(self.request):
                response.data = encrypt_payload(response.data)
                response['X-Insurance-Encrypted'] = 'true'
            return response

        if response is not None:
            response.data = self.error_payload(
                self._exception_message(response.data),
                response.data,
            )
            if self.should_encrypt_response(self.request):
                response.data = encrypt_payload(response.data)
                response['X-Insurance-Encrypted'] = 'true'
        return response


class PremiumTrialView(EncryptedInsuranceAPIView):
    """接口：POST /api/insurance/premium-trials/。

    用途：保费试算，根据产品、计划、被保人年龄、职业类别和优惠规则计算应缴保费。
    """

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
        data = self.serialize_and_cache(
            quote,
            CACHE_NAMESPACES['premium_quote'],
            quote.quote_no,
            PremiumQuoteSerializer,
        )
        return self.insurance_response(request, data, response_status=status.HTTP_201_CREATED)


class PremiumQuoteDetailView(EncryptedInsuranceAPIView):
    """接口：GET /api/insurance/premium-trials/{quote_no}/。

    用途：查询试算单详情，优先读取 Redis 缓存，未命中时查询数据库并回写缓存。
    """

    def get(self, request, quote_no):
        return self.cached_detail_response(
            request,
            CACHE_NAMESPACES['premium_quote'],
            quote_no,
            lambda: get_object_or_404(PremiumQuote, quote_no=quote_no),
            PremiumQuoteSerializer,
        )


class UnderwritingView(EncryptedInsuranceAPIView):
    """接口：POST /api/insurance/underwriting/。

    用途：旧版自动核保，直接基于试算单生成核保记录；推荐新流程优先使用投保单核保接口。
    """

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
        data = self.serialize_and_cache(
            uw_case,
            CACHE_NAMESPACES['underwriting'],
            uw_case.uw_no,
            UnderwritingCaseSerializer,
        )
        self.cache_related_quote(uw_case.quote)
        return self.insurance_response(request, data, response_status=status.HTTP_201_CREATED)


class UnderwritingDetailView(EncryptedInsuranceAPIView):
    """接口：GET /api/insurance/underwriting/{underwriting_no}/。

    用途：查询核保记录详情。
    """

    def get(self, request, underwriting_no):
        return self.cached_detail_response(
            request,
            CACHE_NAMESPACES['underwriting'],
            underwriting_no,
            lambda: get_object_or_404(UnderwritingCase, uw_no=underwriting_no),
            UnderwritingCaseSerializer,
        )


class InsuranceApplicationView(EncryptedInsuranceAPIView):
    """接口：POST /api/insurance/applications/。

    用途：创建投保单，沉淀告知、受益人和投保确认留痕。
    """

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
        data = self.serialize_and_cache(
            application,
            CACHE_NAMESPACES['application'],
            application.application_no,
            InsuranceApplicationSerializer,
        )
        self.cache_related_quote(application.quote)
        return self.insurance_response(request, data, response_status=status.HTTP_201_CREATED)


class InsuranceApplicationDetailView(EncryptedInsuranceAPIView):
    """接口：GET /api/insurance/applications/{application_no}/。

    用途：查询投保单详情。
    """

    def get(self, request, application_no):
        from .models import InsuranceApplication

        return self.cached_detail_response(
            request,
            CACHE_NAMESPACES['application'],
            application_no,
            lambda: get_object_or_404(InsuranceApplication, application_no=application_no),
            InsuranceApplicationSerializer,
        )


class ApplicationUnderwritingView(EncryptedInsuranceAPIView):
    """接口：POST /api/insurance/applications/{application_no}/underwriting/。

    用途：按投保单提交核保，并把核保结论反写投保单状态。
    """

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
        data = self.serialize_and_cache(
            uw_case,
            CACHE_NAMESPACES['underwriting'],
            uw_case.uw_no,
            UnderwritingCaseSerializer,
        )
        self.cache_related_application(uw_case.application)
        self.cache_related_quote(uw_case.quote)
        return self.insurance_response(request, data, response_status=status.HTTP_201_CREATED)


class ManualUnderwritingReviewView(EncryptedInsuranceAPIView):
    """接口：POST /api/insurance/underwriting/{underwriting_no}/manual-review/。

    用途：人工核保复核，把自动核保转人工的案件改为最终结论。
    """

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
        data = ManualUnderwritingReviewSerializer(review).data
        self.cache_related_underwriting(review.underwriting)
        self.cache_related_application(review.underwriting.application)
        self.cache_related_quote(review.underwriting.quote)
        return self.insurance_response(request, data, response_status=status.HTTP_201_CREATED)


class PaymentOrderView(EncryptedInsuranceAPIView):
    """接口：POST /api/insurance/payment-orders/。

    用途：创建服务端支付订单，后续出单只认服务端支付状态。
    """

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
        data = self.serialize_and_cache(
            payment_order,
            CACHE_NAMESPACES['payment_order'],
            payment_order.pay_order_no,
            PaymentOrderSerializer,
        )
        self.cache_related_application(payment_order.application)
        self.cache_related_quote(payment_order.quote)
        self.cache_related_underwriting(payment_order.underwriting)
        return self.insurance_response(request, data, response_status=status.HTTP_201_CREATED)


class PaymentOrderDetailView(EncryptedInsuranceAPIView):
    """接口：GET /api/insurance/payment-orders/{pay_order_no}/。

    用途：查询支付订单详情。
    """

    def get(self, request, pay_order_no):
        from .models import PaymentOrder

        return self.cached_detail_response(
            request,
            CACHE_NAMESPACES['payment_order'],
            pay_order_no,
            lambda: get_object_or_404(PaymentOrder, pay_order_no=pay_order_no),
            PaymentOrderSerializer,
        )


class PaymentOrderConfirmView(EncryptedInsuranceAPIView):
    """接口：POST /api/insurance/payment-orders/{pay_order_no}/confirm/。

    用途：模拟支付中心回调，校验金额并更新支付结果。
    """

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
        data = self.serialize_and_cache(
            payment_order,
            CACHE_NAMESPACES['payment_order'],
            payment_order.pay_order_no,
            PaymentOrderSerializer,
        )
        self.cache_related_application(payment_order.application)
        self.cache_related_quote(payment_order.quote)
        self.cache_related_underwriting(payment_order.underwriting)
        return self.insurance_response(request, data)


class IssuePolicyView(EncryptedInsuranceAPIView):
    """接口：POST /api/insurance/policies/。

    用途：旧版承保出单，直接基于核保记录和前端支付信息生成保单。
    """

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
        data = self.serialize_and_cache(
            policy,
            CACHE_NAMESPACES['policy'],
            policy.policy_no,
            PolicySerializer,
        )
        self.cache_related_quote(policy.quote)
        self.cache_related_underwriting(policy.underwriting)
        return self.insurance_response(request, data, response_status=status.HTTP_201_CREATED)


class IssueApplicationPolicyView(EncryptedInsuranceAPIView):
    """接口：POST /api/insurance/application-policies/。

    用途：推荐出单接口，基于投保单、核保记录和服务端成功支付订单生成保单。
    """

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
        data = self.serialize_and_cache(
            policy,
            CACHE_NAMESPACES['policy'],
            policy.policy_no,
            PolicySerializer,
        )
        self.cache_related_application(policy.application)
        self.cache_related_quote(policy.quote)
        self.cache_related_underwriting(policy.underwriting)
        self.cache_related_payment_order(policy.payment_order)
        return self.insurance_response(request, data, response_status=status.HTTP_201_CREATED)


class PolicyDetailView(EncryptedInsuranceAPIView):
    """接口：GET /api/insurance/policies/{policy_no}/。

    用途：查询保单详情，包含电子保单和送达记录。
    """

    def get(self, request, policy_no):
        return self.cached_detail_response(
            request,
            CACHE_NAMESPACES['policy'],
            policy_no,
            lambda: get_object_or_404(Policy, policy_no=policy_no),
            PolicySerializer,
        )


class ProductListView(EncryptedInsuranceAPIView):
    """接口：GET /api/insurance/products/。

    用途：查询当前在售产品列表，前端可用它展示可投保产品和计划入口。
    """

    def get(self, request):
        products = Product.objects.filter(status=Product.Status.ACTIVE).prefetch_related(
            'plans__coverages',
            'age_rate_factors',
            'occupation_rate_factors',
        ).order_by('product_code')
        return self.insurance_response(request, ProductSerializer(products, many=True).data)


class ProductDetailView(EncryptedInsuranceAPIView):
    """接口：GET /api/insurance/products/{product_code}/。

    用途：查询单个产品详情，包含计划、责任、年龄费率和职业费率配置。
    """

    def get(self, request, product_code):
        product = get_object_or_404(
            Product.objects.prefetch_related(
                'plans__coverages',
                'age_rate_factors',
                'occupation_rate_factors',
            ),
            product_code=product_code,
        )
        return self.insurance_response(request, ProductSerializer(product).data)
