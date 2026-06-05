import json
import logging
import time
import uuid


logger = logging.getLogger('request_process')


class RequestProcessLoggingMiddleware:
    """通用请求过程日志中间件。

    作用范围：
    - 所有 Django 请求都会经过这里，包括以后新增的每一个接口。

    打印内容：
    - 请求开始：请求ID、方法、路径、IP、请求头、请求体
    - 请求结束：请求ID、状态码、响应体、耗时
    - 请求异常：请求ID、异常类型、异常信息、耗时
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = uuid.uuid4().hex
        start_time = time.perf_counter()
        request.request_id = request_id

        self._log_request_start(request, request_id)

        try:
            response = self.get_response(request)
        except Exception:
            duration_ms = self._duration_ms(start_time)
            logger.exception(
                '请求异常 request_id=%s method=%s path=%s duration_ms=%s',
                request_id,
                request.method,
                request.get_full_path(),
                duration_ms,
            )
            raise

        duration_ms = self._duration_ms(start_time)
        response['X-Request-ID'] = request_id
        self._log_response_end(request, response, request_id, duration_ms)
        return response

    def _log_request_start(self, request, request_id):
        logger.info(
            '\n========== 请求开始 ==========\n'
            '请求ID: %s\n'
            '请求URL: %s %s\n'
            '客户端IP: %s\n'
            '请求头:\n%s\n'
            '请求参数:\n%s',
            request_id,
            request.method,
            request.get_full_path(),
            self._client_ip(request),
            self._pretty(self._headers(request)),
            self._pretty({
                'query': dict(request.GET),
                'body': self._body(request),
            }),
        )

    def _log_response_end(self, request, response, request_id, duration_ms):
        logger.info(
            '\n响应状态: %s\n'
            '响应头:\n%s\n'
            '响应参数:\n%s\n'
            '耗时: %sms\n'
            '========== 请求结束 ==========\n',
            response.status_code,
            self._pretty(self._response_headers(response)),
            self._pretty(self._response_body(response)),
            duration_ms,
        )

    def _headers(self, request):
        headers = {}
        for key, value in request.headers.items():
            # 业务排查通常需要请求头，但认证和 Cookie 不应明文落日志。
            if key.lower() in {'authorization', 'cookie', 'x-csrftoken'}:
                headers[key] = '***'
            else:
                headers[key] = value
        return headers

    def _body(self, request):
        if request.method in {'GET', 'HEAD', 'OPTIONS'}:
            return None
        body = request.body
        if not body:
            return None
        text = body.decode(request.encoding or 'utf-8', errors='replace')
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text

    def _response_body(self, response):
        if getattr(response, 'streaming', False):
            return '<streaming response>'
        content = getattr(response, 'content', b'')
        if not content:
            return None
        text = content.decode(getattr(response, 'charset', 'utf-8') or 'utf-8', errors='replace')
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text

    def _response_headers(self, response):
        return {key: value for key, value in response.items()}

    def _client_ip(self, request):
        forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')

    def _duration_ms(self, start_time):
        return round((time.perf_counter() - start_time) * 1000, 2)

    def _pretty(self, payload):
        if payload is None:
            return 'null'
        return json.dumps(payload, ensure_ascii=False, default=str, indent=2)
