import hashlib
import secrets

from django.conf import settings
from django.core.cache import cache


TOKEN_CACHE_NAMESPACE = 'insurance:auth_token'


def token_timeout():
    return getattr(settings, 'INSURANCE_TOKEN_TTL', 7200)


def token_cache_key(token):
    digest = hashlib.sha256(token.encode('utf-8')).hexdigest()
    return f'{TOKEN_CACHE_NAMESPACE}:{digest}'


def issue_insurance_token():
    """生成一次随机接口 token，并写入缓存。

    token 明文只返回给调用方；缓存中保存 hash 后的 key，避免直接存明文 token。
    """
    token = secrets.token_urlsafe(32)
    cache.set(token_cache_key(token), True, timeout=token_timeout())
    return token


def validate_insurance_token(token):
    if not token:
        return False
    return cache.get(token_cache_key(token)) is True
