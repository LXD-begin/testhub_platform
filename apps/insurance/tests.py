import json

from django.test import Client, SimpleTestCase, override_settings

from .crypto import InsuranceCryptoError, decrypt_payload, encrypt_payload


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
