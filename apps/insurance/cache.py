import logging

from django.conf import settings
from django.core.cache import cache


logger = logging.getLogger(__name__)

CACHE_NAMESPACES = {
    'premium_quote': 'premium_quote',
    'underwriting': 'underwriting',
    'application': 'application',
    'payment_order': 'payment_order',
    'policy': 'policy',
}


def insurance_cache_key(namespace, identifier):
    return f'insurance:{namespace}:{identifier}'


def detail_cache_timeout():
    return getattr(settings, 'INSURANCE_DETAIL_CACHE_TIMEOUT', 60)


def get_detail_cache(namespace, identifier):
    key = insurance_cache_key(namespace, identifier)
    try:
        return cache.get(key)
    except Exception:
        logger.exception('Failed to read insurance cache key=%s', key)
        return None


def set_detail_cache(namespace, identifier, data, timeout=None):
    key = insurance_cache_key(namespace, identifier)
    try:
        cache.set(key, data, timeout=timeout or detail_cache_timeout())
    except Exception:
        logger.exception('Failed to write insurance cache key=%s', key)


def delete_detail_cache(namespace, identifier):
    if not identifier:
        return
    key = insurance_cache_key(namespace, identifier)
    try:
        cache.delete(key)
    except Exception:
        logger.exception('Failed to delete insurance cache key=%s', key)


def delete_quote_cache(quote_no):
    delete_detail_cache(CACHE_NAMESPACES['premium_quote'], quote_no)


def delete_underwriting_cache(underwriting_no):
    delete_detail_cache(CACHE_NAMESPACES['underwriting'], underwriting_no)


def delete_application_cache(application_no):
    delete_detail_cache(CACHE_NAMESPACES['application'], application_no)


def delete_payment_order_cache(pay_order_no):
    delete_detail_cache(CACHE_NAMESPACES['payment_order'], pay_order_no)


def delete_policy_cache(policy_no):
    delete_detail_cache(CACHE_NAMESPACES['policy'], policy_no)


def delete_caches_for_underwriting(uw_case):
    if not uw_case:
        return
    delete_underwriting_cache(uw_case.uw_no)
    if getattr(uw_case, 'quote_id', None):
        delete_quote_cache(uw_case.quote.quote_no)
    if getattr(uw_case, 'application_id', None):
        delete_application_cache(uw_case.application.application_no)


def delete_caches_for_application(application):
    if not application:
        return
    delete_application_cache(application.application_no)
    if getattr(application, 'quote_id', None):
        delete_quote_cache(application.quote.quote_no)


def delete_caches_for_payment_order(order):
    if not order:
        return
    delete_payment_order_cache(order.pay_order_no)
    if getattr(order, 'application_id', None):
        delete_application_cache(order.application.application_no)
    if getattr(order, 'quote_id', None):
        delete_quote_cache(order.quote.quote_no)
    if getattr(order, 'underwriting_id', None):
        delete_underwriting_cache(order.underwriting.uw_no)


def delete_caches_for_policy(policy):
    if not policy:
        return
    delete_policy_cache(policy.policy_no)
    if getattr(policy, 'quote_id', None):
        delete_quote_cache(policy.quote.quote_no)
    if getattr(policy, 'underwriting_id', None):
        delete_underwriting_cache(policy.underwriting.uw_no)
    if getattr(policy, 'application_id', None):
        delete_application_cache(policy.application.application_no)
    if getattr(policy, 'payment_order_id', None):
        delete_payment_order_cache(policy.payment_order.pay_order_no)
