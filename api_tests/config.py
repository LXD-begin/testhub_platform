import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent

API_BASE_URL = os.environ.get('API_BASE_URL', 'http://127.0.0.1:8000')
CASE_FILE = Path(os.environ.get('API_CASE_FILE', BASE_DIR / 'data' / 'insurance_api_cases.xlsx'))
REQUEST_TIMEOUT = float(os.environ.get('API_REQUEST_TIMEOUT', '10'))

BACKEND_BRANCH = os.environ.get('BACKEND_BRANCH', 'dev-master')
BACKEND_SOURCE_DIR = os.environ.get('BACKEND_SOURCE_DIR', '')
BACKEND_DIFF_TARGET = os.environ.get('BACKEND_DIFF_TARGET', BACKEND_BRANCH)
BACKEND_DIFF_BASE = os.environ.get('BACKEND_DIFF_BASE', f'{BACKEND_DIFF_TARGET}~1')

LOG_DIR = BASE_DIR / 'reports' / 'logs'
LOG_FILE = LOG_DIR / 'api_test.log'
