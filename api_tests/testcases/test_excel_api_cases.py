from dataclasses import replace

import allure
import pytest
import requests

from api_tests.common.assertions import assert_response
from api_tests.common.context import CaseContext
from api_tests.common.excel_reader import load_cases
from api_tests.common.json_path import get_by_path
from api_tests.common.logger import get_logger
from api_tests.common.request_client import ApiClient
from api_tests.config import CASE_FILE


logger = get_logger(__name__)
client = ApiClient()
context = CaseContext()
cases = load_cases(CASE_FILE)


@pytest.mark.excel
@pytest.mark.parametrize('case', cases, ids=[case.case_id for case in cases])
def test_excel_api_case(case):
    if not context.is_finished(case.depends_on):
        pytest.skip(f'依赖用例未执行完成: {case.depends_on}')

    case = replace(
        case,
        path=context.render(case.path),
        expected_message=context.render(case.expected_message),
        expected_fields=context.render(case.expected_fields),
    )
    headers = context.render(case.headers)
    params = context.render(case.params)
    body = context.render(case.body)

    allure.dynamic.feature(case.module)
    allure.dynamic.story(case.title)
    allure.dynamic.title(f'{case.case_id} {case.title}')
    allure.dynamic.description(case.description)

    logger.info('执行用例 %s %s %s', case.case_id, case.method, case.path)
    logger.info('请求头: %s', headers)
    logger.info('请求参数: %s', params)
    logger.info('请求体: %s', body)

    try:
        response = client.request(case.method, case.path, headers=headers, params=params, body=body)
    except requests.RequestException as exc:
        raise AssertionError(f'{case.case_id} 请求失败，请确认后端服务已启动: {exc}') from exc

    logger.info('响应状态码: %s', response.status_code)
    logger.info('响应体: %s', response.text)
    allure.attach(str(headers), name='request_headers', attachment_type=allure.attachment_type.TEXT)
    allure.attach(str(params), name='request_params', attachment_type=allure.attachment_type.TEXT)
    allure.attach(str(body), name='request_body', attachment_type=allure.attachment_type.TEXT)
    allure.attach(response.text, name='response_body', attachment_type=allure.attachment_type.JSON)

    response_body = assert_response(case, response)
    for variable_name, json_path in case.extract.items():
        context.set(variable_name, get_by_path(response_body, json_path))
        logger.info('提取变量: %s=%s', variable_name, context.get(variable_name))

    context.mark_finished(case.case_id)
