import base64
import hashlib
import json
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django.conf import settings


ALGORITHM = 'AES-256-GCM'
NONCE_SIZE = 12


class InsuranceCryptoError(ValueError):
    pass


def _urlsafe_b64decode(value):
    if not isinstance(value, str):
        raise InsuranceCryptoError('密文字段必须是字符串')
    padded = value + '=' * (-len(value) % 4)
    try:
        return base64.urlsafe_b64decode(padded.encode('ascii'))
    except Exception as exc:
        raise InsuranceCryptoError('密文字段不是有效的 Base64') from exc


def _urlsafe_b64encode(value):
    return base64.urlsafe_b64encode(value).decode('ascii').rstrip('=')


def _crypto_key():
    raw_key = getattr(settings, 'INSURANCE_CRYPTO_KEY', '')
    if not raw_key:
        raise InsuranceCryptoError('未配置 INSURANCE_CRYPTO_KEY')

    try:
        decoded = _urlsafe_b64decode(raw_key)
    except InsuranceCryptoError:
        decoded = b''
    if len(decoded) == 32:
        return decoded

    return hashlib.sha256(raw_key.encode('utf-8')).digest()


def encrypt_payload(payload):
    plaintext = json.dumps(payload, ensure_ascii=False, separators=(',', ':'), default=str).encode('utf-8')
    nonce = os.urandom(NONCE_SIZE)
    ciphertext = AESGCM(_crypto_key()).encrypt(nonce, plaintext, None)
    return {
        'encrypted': True,
        'algorithm': ALGORITHM,
        'iv': _urlsafe_b64encode(nonce),
        'ciphertext': _urlsafe_b64encode(ciphertext),
    }


def decrypt_payload(envelope):
    if not isinstance(envelope, dict):
        raise InsuranceCryptoError('加密请求体必须是 JSON 对象')
    if envelope.get('algorithm', ALGORITHM) != ALGORITHM:
        raise InsuranceCryptoError('不支持的加密算法')
    if envelope.get('encrypted') is not True:
        raise InsuranceCryptoError('加密请求体缺少 encrypted=true')

    nonce = _urlsafe_b64decode(envelope.get('iv'))
    ciphertext = _urlsafe_b64decode(envelope.get('ciphertext'))
    if len(nonce) != NONCE_SIZE:
        raise InsuranceCryptoError('iv 长度不正确')

    try:
        plaintext = AESGCM(_crypto_key()).decrypt(nonce, ciphertext, None)
    except InvalidTag as exc:
        raise InsuranceCryptoError('密文校验失败或密钥不正确') from exc

    try:
        return json.loads(plaintext.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InsuranceCryptoError('解密后的内容不是有效 JSON') from exc


def is_encrypted_envelope(payload):
    return isinstance(payload, dict) and payload.get('encrypted') is True and 'ciphertext' in payload
