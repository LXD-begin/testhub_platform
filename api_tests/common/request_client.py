from urllib.parse import urljoin

import requests

from api_tests.config import API_BASE_URL, REQUEST_TIMEOUT


class ApiClient:
    def __init__(self, base_url=API_BASE_URL, timeout=REQUEST_TIMEOUT):
        self.base_url = base_url.rstrip('/') + '/'
        self.timeout = timeout
        self.session = requests.Session()

    def request(self, method, path, headers=None, params=None, body=None):
        url = urljoin(self.base_url, path.lstrip('/'))
        return self.session.request(
            method=method,
            url=url,
            headers=headers or {},
            params=params or {},
            json=body,
            timeout=self.timeout,
        )
