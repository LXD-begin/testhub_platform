import json

from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.core.cache import cache
from rest_framework import status
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from .cache import (
    delete_detail_cache,
    get_detail_cache,
    insurance_cache_key,
    set_detail_cache,
)
from .crypto import InsuranceCryptoError, decrypt_payload, encrypt_payload
from .views import EncryptedInsuranceAPIView


TEST_CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'insurance-cache-tests',
    }
}


class InsuranceCacheTests(SimpleTestCase):
    def tearDown(self):
        cache.clear()

    def test_detail_cache_key_is_namespaced(self):
        self.assertEqual(
            insurance_cache_key('premium_quote', 'QT20260606000001'),
            'insurance:premium_quote:QT20260606000001',
        )

    @override_settings(CACHES=TEST_CACHES, INSURANCE_DETAIL_CACHE_TIMEOUT=60)
    def test_detail_cache_set_get_and_delete(self):
        set_detail_cache('premium_quote', 'QT20260606000001', {'status': 'QUOTED'})

        self.assertEqual(
            get_detail_cache('premium_quote', 'QT20260606000001'),
            {'status': 'QUOTED'},
        )

        delete_detail_cache('premium_quote', 'QT20260606000001')
        self.assertIsNone(get_detail_cache('premium_quote', 'QT20260606000001'))


class InsuranceWriteCacheTests(TestCase):
    def tearDown(self):
        cache.clear()

    def test_product_catalog_returns_default_product_config(self):
        response = Client().get('/api/insurance/products/')

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['code'], 200)
        self.assertEqual(body['data'][0]['product_code'], 'PA_C_ACCIDENT')
        self.assertEqual(body['data'][0]['plans'][0]['plan_code'], 'BASIC')

    @override_settings(CACHES=TEST_CACHES, INSURANCE_DETAIL_CACHE_TIMEOUT=60)
    def test_premium_trial_writes_detail_cache_after_create(self):
        response = Client().post(
            '/api/insurance/premium-trials/',
            data=json.dumps({
                'product_code': 'PA_C_ACCIDENT',
                'plan_code': 'STANDARD',
                'effective_date': '2026-06-06',
                'insurance_period_months': 12,
                'applicant': {
                    'name': '张三',
                    'id_type': 'IDENTITY_CARD',
                    'id_no': '110101199001011234',
                    'mobile': '13800138000',
                    'email': 'zhangsan@example.com',
                },
                'insured': {
                    'name': '张三',
                    'id_type': 'IDENTITY_CARD',
                    'id_no': '110101199001011234',
                    'mobile': '13800138000',
                    'email': 'zhangsan@example.com',
                },
                'occupation_code': '010101',
                'occupation_category': 2,
                'has_social_security': True,
                'channel_code': 'C_APP',
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 201)
        body = response.json()
        quote_no = body['data']['quote_no']
        cached = get_detail_cache('premium_quote', quote_no)

        self.assertEqual(body['code'], 200)
        self.assertIsNotNone(cached)
        self.assertEqual(cached['quote_no'], quote_no)
        self.assertEqual(cached['plan_code'], 'STANDARD')


class InsuranceCryptoTests(SimpleTestCase):
    @override_settings(INSURANCE_API_KEY='secret-test-key')
    def test_insurance_api_key_rejects_missing_key(self):
        response = Client().get('/api/insurance/products/')

        self.assertIn(response.status_code, [401, 403])
        body = response.json()
        self.assertEqual(body['code'], 999)
        self.assertEqual(body['message'], '接口鉴权失败')

    def test_plain_success_response_is_wrapped(self):
        request = Request(APIRequestFactory().get('/api/insurance/premium-trials/'))
        response = EncryptedInsuranceAPIView().insurance_response(request, {'quote_no': 'QT20260606000001'})

        self.assertEqual(response.data['code'], 200)
        self.assertEqual(response.data['message'], '成功')
        self.assertEqual(response.data['data'], {'quote_no': 'QT20260606000001'})

    def test_business_error_response_is_wrapped(self):
        request = Request(APIRequestFactory().get('/api/insurance/premium-trials/'))
        response = EncryptedInsuranceAPIView().insurance_response(
            request,
            {'code': 'BUSINESS_ERROR', 'message': '试算单已失效'},
            response_status=status.HTTP_400_BAD_REQUEST,
        )

        self.assertEqual(response.data['code'], 999)
        self.assertEqual(response.data['message'], '试算单已失效')
        self.assertEqual(response.data['data'], {'error_type': 'BUSINESS_ERROR'})

    def test_unexpected_exception_response_is_wrapped(self):
        view = EncryptedInsuranceAPIView()
        view.request = Request(APIRequestFactory().get('/api/insurance/premium-trials/'))

        response = view.handle_exception(RuntimeError('boom'))

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.data['code'], 999)
        self.assertEqual(response.data['message'], '服务器内部错误')
        self.assertIsNone(response.data['data'])

    @override_settings(INSURANCE_CRYPTO_KEY='test-insurance-key')
    def test_encrypt_and_decrypt_payload(self):
        payload = {
            'product_code': 'PA_C_ACCIDENT',
            'applicant': {
                'name': '张三',
                'id_no': '110101199001011234',
            },
        }

        envelope = encrypt_payload(payload)
        self.assertTrue(envelope['encrypted'])
        self.assertIn('iv', envelope)
        self.assertIn('ciphertext', envelope)
        self.assertEqual(decrypt_payload(envelope), payload)

    @override_settings(INSURANCE_CRYPTO_KEY='test-insurance-key')
    def test_decrypt_rejects_wrong_key(self):
        envelope = encrypt_payload({'quote_no': 'QT20260605000001'})

        with override_settings(INSURANCE_CRYPTO_KEY='wrong-key'):
            with self.assertRaises(InsuranceCryptoError):
                decrypt_payload(envelope)

    @override_settings(INSURANCE_CRYPTO_KEY='test-insurance-key')
    def test_encrypted_request_gets_encrypted_validation_error(self):
        envelope = encrypt_payload({'product_code': 'PA_C_ACCIDENT'})

        response = Client().post(
            '/api/insurance/premium-trials/',
            data=json.dumps(envelope),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.headers['X-Insurance-Encrypted'], 'true')
        decrypted = decrypt_payload(response.json())
        self.assertEqual(decrypted['code'], 999)
        self.assertEqual(decrypted['message'], '参数校验失败')
        self.assertIn('plan_code', decrypted['data'])
