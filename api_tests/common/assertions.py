from api_tests.common.json_path import get_by_path


def assert_response(case, response):
    assert response.status_code == case.expected_status, (
        f'{case.case_id} HTTP 状态码不符合预期: '
        f'expected={case.expected_status}, actual={response.status_code}, body={response.text}'
    )

    try:
        body = response.json()
    except ValueError as exc:
        raise AssertionError(f'{case.case_id} 响应不是 JSON: {response.text}') from exc

    if case.expected_code is not None:
        assert body.get('code') == case.expected_code, (
            f'{case.case_id} 业务 code 不符合预期: '
            f'expected={case.expected_code}, actual={body.get("code")}, body={body}'
        )
    if case.expected_message:
        assert body.get('message') == case.expected_message, (
            f'{case.case_id} message 不符合预期: '
            f'expected={case.expected_message}, actual={body.get("message")}, body={body}'
        )
    for path, expected in case.expected_fields.items():
        actual = get_by_path(body, path)
        assert actual == expected, (
            f'{case.case_id} 字段断言失败: {path}, '
            f'expected={expected}, actual={actual}, body={body}'
        )
    return body
