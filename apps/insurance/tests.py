import json

from django.test import Client, SimpleTestCase, override_settings
from django.core.cache import cache

from .cache import (
    delete_detail_cache,
    get_detail_cache,
    insurance_cache_key,
    set_detail_cache,
)
from .crypto import InsuranceCryptoError, decrypt_payload, encrypt_payload


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


class InsuranceCryptoTests(SimpleTestCase):
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
        self.assertIn('plan_code', decrypted)
