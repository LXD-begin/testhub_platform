import os

import pytest
from playwright.sync_api import Page, expect


INSURANCE_URL = (
    "https://mcore.health.pingan.com/internet/?sourceUserId=97309829"
    "#/index?g=AM000001039&c=APP&post_id=a_app_bxcp_0_fx&namespace=APP"
    "&pid=21813559198&from=APP&fromUserId=1005848587705349937"
    "&simpleShareCode=5045717e885cff49db0d83f33bb70960b974cbae86221fe99ded36919b0d55e9"
    "&pa_from=App_Store&sourceUserId=97309829"
)
FINAL_WAIT_MS = int(os.getenv("INSURANCE_FINAL_WAIT_MS", "8000"))


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        pytest.skip(f"Missing required environment variable: {name}")
    return value


def _click_if_visible(page: Page, role: str, name: str, timeout: int = 5000) -> bool:
    target = page.get_by_role(role, name=name)
    try:
        expect(target).to_be_visible(timeout=timeout)
    except AssertionError:
        return False

    target.click()
    return True


def test_fill_insurance_application_identity(page: Page) -> None:
    applicant_name = _required_env("INSURANCE_APPLICANT_NAME")
    applicant_idno = _required_env("INSURANCE_APPLICANT_IDNO")

    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(INSURANCE_URL, wait_until="domcontentloaded")

    _click_if_visible(page, "button", "同意并继续")

    plan_two = page.get_by_role("tab", name="计划二 5千免赔版")
    expect(plan_two).to_be_visible()
    plan_two.click()
    expect(plan_two).to_have_attribute("aria-selected", "true")

    apply_tab = page.get_by_role("tab", name="我要投保")
    expect(apply_tab).to_be_visible()
    apply_tab.click()

    name_input = page.get_by_placeholder("请输入本人姓名")
    expect(name_input).to_be_visible()
    name_input.fill(applicant_name)
    expect(name_input).to_have_value(applicant_name)

    idno_input = page.get_by_placeholder("请输入本人证件号码")
    expect(idno_input).to_be_visible()
    idno_input.fill(applicant_idno)
    expect(idno_input).to_have_value(applicant_idno)

    # The test intentionally stops before clicking "立即投保".
    expect(page.get_by_role("button", name="立即投保")).to_be_visible()
    page.wait_for_timeout(FINAL_WAIT_MS)
