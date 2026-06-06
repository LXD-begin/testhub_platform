import io
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
from contextlib import contextmanager
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from api_tests.config import BACKEND_BRANCH, BACKEND_SOURCE_DIR  # noqa: E402


CONTRACT_FILE = PROJECT_ROOT / 'api_tests' / 'reports' / 'api_contract.json'


@contextmanager
def backend_source_dir():
    """Return a backend source directory without requiring Django code in this branch."""
    if BACKEND_SOURCE_DIR:
        source_dir = Path(BACKEND_SOURCE_DIR).resolve()
        if not source_dir.exists():
            raise FileNotFoundError(f'BACKEND_SOURCE_DIR 不存在: {source_dir}')
        yield source_dir
        return

    with tempfile.TemporaryDirectory(prefix='aitesthub_backend_', ignore_cleanup_errors=True) as temp_dir:
        result = subprocess.run(
            ['git', 'archive', '--format=tar', BACKEND_BRANCH],
            cwd=PROJECT_ROOT,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            stderr = result.stderr.decode('utf-8', errors='ignore')
            raise RuntimeError(f'导出后端分支失败: {BACKEND_BRANCH}\n{stderr}')

        with tarfile.open(fileobj=io.BytesIO(result.stdout), mode='r:') as archive:
            archive.extractall(temp_dir, filter='data')
        yield Path(temp_dir)


def field_schema(field):
    schema = {
        'type': field.__class__.__name__,
        'required': getattr(field, 'required', False),
        'read_only': getattr(field, 'read_only', False),
        'allow_blank': getattr(field, 'allow_blank', None),
        'max_length': getattr(field, 'max_length', None),
        'min_value': str(getattr(field, 'min_value', '')) or None,
        'max_value': str(getattr(field, 'max_value', '')) or None,
        'help_text': str(getattr(field, 'help_text', '')) or None,
        'label': str(getattr(field, 'label', '')) or None,
    }
    choices = getattr(field, 'choices', None)
    if choices:
        schema['choices'] = list(choices.keys())
    if hasattr(field, 'fields'):
        schema['children'] = serializer_schema(field.__class__)
    child = getattr(field, 'child', None)
    if child:
        schema['child'] = field_schema(child)
    return {key: value for key, value in schema.items() if value not in (None, '', [])}


def serializer_schema(serializer_class):
    if serializer_class is None:
        return None
    serializer = serializer_class()
    return {name: field_schema(field) for name, field in serializer.fields.items()}


def flatten_urlpatterns(patterns, prefix=''):
    for item in patterns:
        route = prefix + str(item.pattern)
        if hasattr(item, 'url_patterns'):
            yield from flatten_urlpatterns(item.url_patterns, route)
        else:
            view_class = getattr(item.callback, 'view_class', None)
            if view_class:
                yield route, view_class


def normalize_path(route):
    path = re.sub(r'<(?:[^:>]+:)?([^>]+)>', r'{\1}', route)
    return '/' + path


def build_view_contracts(serializers, views):
    return {
        views.InsuranceTokenView: {
            'POST': {'request': None, 'response': None},
        },
        views.ProductListView: {
            'GET': {'request': None, 'response': serializers.ProductSerializer},
        },
        views.ProductDetailView: {
            'GET': {'request': None, 'response': serializers.ProductSerializer},
        },
        views.PremiumTrialView: {
            'POST': {'request': serializers.PremiumTrialRequestSerializer, 'response': serializers.PremiumQuoteSerializer},
        },
        views.PremiumQuoteDetailView: {
            'GET': {'request': None, 'response': serializers.PremiumQuoteSerializer},
        },
        views.InsuranceApplicationView: {
            'POST': {
                'request': serializers.InsuranceApplicationCreateSerializer,
                'response': serializers.InsuranceApplicationSerializer,
            },
        },
        views.InsuranceApplicationDetailView: {
            'GET': {'request': None, 'response': serializers.InsuranceApplicationSerializer},
        },
        views.ApplicationUnderwritingView: {
            'POST': {
                'request': serializers.ApplicationUnderwritingRequestSerializer,
                'response': serializers.UnderwritingCaseSerializer,
            },
        },
        views.UnderwritingView: {
            'POST': {'request': serializers.UnderwritingRequestSerializer, 'response': serializers.UnderwritingCaseSerializer},
        },
        views.UnderwritingDetailView: {
            'GET': {'request': None, 'response': serializers.UnderwritingCaseSerializer},
        },
        views.ManualUnderwritingReviewView: {
            'POST': {
                'request': serializers.ManualUnderwritingReviewRequestSerializer,
                'response': serializers.ManualUnderwritingReviewSerializer,
            },
        },
        views.PaymentOrderView: {
            'POST': {'request': serializers.PaymentOrderCreateSerializer, 'response': serializers.PaymentOrderSerializer},
        },
        views.PaymentOrderDetailView: {
            'GET': {'request': None, 'response': serializers.PaymentOrderSerializer},
        },
        views.PaymentOrderConfirmView: {
            'POST': {'request': serializers.PaymentOrderConfirmSerializer, 'response': serializers.PaymentOrderSerializer},
        },
        views.IssuePolicyView: {
            'POST': {'request': serializers.IssuePolicyRequestSerializer, 'response': serializers.PolicySerializer},
        },
        views.IssueApplicationPolicyView: {
            'POST': {'request': serializers.IssuePolicyFromApplicationRequestSerializer, 'response': serializers.PolicySerializer},
        },
        views.PolicyDetailView: {
            'GET': {'request': None, 'response': serializers.PolicySerializer},
        },
    }


def generate():
    with backend_source_dir() as source_dir:
        sys.path.insert(0, str(source_dir))
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

        try:
            import django
            from django.urls import get_resolver
        except ImportError as exc:
            raise RuntimeError(
                '读取 dev-master 后端代码失败。请确认当前 Python 环境已安装后端依赖，'
                '或者通过 BACKEND_SOURCE_DIR 指向一个可运行的后端工作区。'
            ) from exc

        django.setup()
        try:
            from apps.insurance import serializers, views
        except ImportError as exc:
            raise RuntimeError('导入 dev-master 的保险接口代码失败，请检查后端分支代码是否完整。') from exc

        view_contracts = build_view_contracts(serializers, views)
        endpoints = []
        for route, view_class in flatten_urlpatterns(get_resolver().url_patterns):
            if not route.startswith('api/insurance/'):
                continue
            contracts = view_contracts.get(view_class, {})
            for method, config in contracts.items():
                endpoints.append(
                    {
                        'method': method,
                        'path': normalize_path(route),
                        'view': view_class.__name__,
                        'description': (view_class.__doc__ or '').strip(),
                        'request_fields': serializer_schema(config['request']),
                        'response_fields': serializer_schema(config['response']),
                        'source_branch': BACKEND_BRANCH,
                    }
                )

    CONTRACT_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONTRACT_FILE.write_text(json.dumps(endpoints, ensure_ascii=False, indent=2), encoding='utf-8')
    return endpoints


if __name__ == '__main__':
    result = generate()
    print(f'已从 {BACKEND_BRANCH} 生成接口契约: {CONTRACT_FILE}')
    print(f'接口数量: {len(result)}')
