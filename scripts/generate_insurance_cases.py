from pathlib import Path
import json

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill


def clone(obj):
    return json.loads(json.dumps(obj, ensure_ascii=False))


def body(obj):
    return json.dumps(obj, ensure_ascii=False, indent=2)


output = Path('保险出单流程接口测试用例.xlsx')

base_premium = {
    "product_code": "PA_C_ACCIDENT",
    "plan_code": "STANDARD",
    "effective_date": "2026-06-10",
    "insurance_period_months": 12,
    "applicant": {
        "name": "张三",
        "id_type": "IDENTITY_CARD",
        "id_no": "110101199001011234",
        "mobile": "13800138000",
        "email": "zhangsan@example.com"
    },
    "insured": {
        "name": "张三",
        "id_type": "IDENTITY_CARD",
        "id_no": "110101199001011234",
        "mobile": "13800138000"
    },
    "occupation_code": "010101",
    "occupation_category": 2,
    "has_social_security": True,
    "channel_code": "C_APP"
}

base_underwriting = {
    "quote_no": "${quote_no}",
    "disclosures": {
        "truth_declaration_confirmed": True,
        "health_answers": {
            "has_major_disease": False,
            "has_disability": False,
            "has_recent_claim": False
        }
    },
    "beneficiary_type": "LEGAL",
    "beneficiaries": []
}

base_policy = {
    "underwriting_no": "${underwriting_no}",
    "payment": {
        "pay_order_no": "PAY202606100001",
        "pay_status": "SUCCESS",
        "paid_amount": "${payable_premium}",
        "paid_time": "2026-06-10T12:00:00+08:00",
        "pay_channel": "WECHAT"
    },
    "delivery": {
        "email": "zhangsan@example.com",
        "sms_mobile": "13800138000"
    },
    "consent_confirmed": True
}

cases = []


def add(name, path, title, data, request_body, expected):
    cases.append([name, path, title, data, body(request_body), expected])


add('保费试算', 'POST /api/insurance/premium-trials/', '正常试算-标准版-职业2类-有社保', '标准产品、标准计划、身份证、职业2类、有社保', base_premium, 'HTTP 201；返回 quote_no；返回 coverages；premium_detail.payable_premium=189.05；status=QUOTED')

payload = clone(base_premium); payload['product_code'] = 'UNKNOWN_PRODUCT'
add('保费试算', 'POST /api/insurance/premium-trials/', '异常试算-产品代码不存在', 'product_code 不在产品配置中', payload, 'HTTP 400；code=BUSINESS_ERROR；message=产品不存在或已下架')

payload = clone(base_premium); payload['plan_code'] = 'VIP'
add('保费试算', 'POST /api/insurance/premium-trials/', '异常试算-计划代码非法', 'plan_code 不在 BASIC/STANDARD/PREMIUM', payload, 'HTTP 400；DRF 参数校验失败；提示 plan_code 非法')

payload = clone(base_premium); payload['insurance_period_months'] = 13
add('保费试算', 'POST /api/insurance/premium-trials/', '异常试算-保障期间超过12个月', 'insurance_period_months=13', payload, 'HTTP 400；DRF 参数校验失败；保障期间最大12个月')

payload = clone(base_premium); payload['occupation_category'] = 0
add('保费试算', 'POST /api/insurance/premium-trials/', '异常试算-职业类别小于1', 'occupation_category=0', payload, 'HTTP 400；DRF 参数校验失败；职业类别范围为1-6')

payload = clone(base_premium); payload['occupation_category'] = 6
add('保费试算', 'POST /api/insurance/premium-trials/', '边界试算-职业6类可试算但核保拒保', 'occupation_category=6', payload, 'HTTP 201；允许试算并返回 quote_no；后续核保应 DECLINED')

payload = clone(base_premium); del payload['insured']['id_no']
add('保费试算', 'POST /api/insurance/premium-trials/', '异常试算-被保人证件号缺失', 'insured.id_no 缺失', payload, 'HTTP 400；DRF 参数校验失败；被保人 id_no 必填')

payload = clone(base_premium); payload['effective_date'] = '2026/06/10'
add('保费试算', 'POST /api/insurance/premium-trials/', '异常试算-起保日期格式错误', 'effective_date 非 yyyy-mm-dd', payload, 'HTTP 400；DRF 参数校验失败；日期格式错误')

add('自动核保', 'POST /api/insurance/underwriting/', '正常核保-试算单有效且告知正常', '先调用保费试算拿 quote_no，再传入核保', base_underwriting, 'HTTP 201；返回 underwriting_no；decision=APPROVED；risk_level=LOW；manual_review_required=false')

payload = clone(base_underwriting); payload['quote_no'] = 'QT_NOT_EXISTS'
add('自动核保', 'POST /api/insurance/underwriting/', '异常核保-quote_no不存在', '未先试算或传错 quote_no', payload, 'HTTP 404；code=NOT_FOUND；message=试算单不存在')

payload = clone(base_underwriting); payload['disclosures']['truth_declaration_confirmed'] = False
add('自动核保', 'POST /api/insurance/underwriting/', '异常核保-未确认如实告知', 'truth_declaration_confirmed=false', payload, 'HTTP 201；decision=DECLINED；reasons 包含未确认如实告知声明')

payload = clone(base_underwriting); payload['disclosures']['health_answers']['has_major_disease'] = True
add('自动核保', 'POST /api/insurance/underwriting/', '异常核保-健康告知异常转人工', '健康告知任意项=true', payload, 'HTTP 201；decision=REFERRED；manual_review_required=true；reasons 包含健康告知异常')

add('自动核保', 'POST /api/insurance/underwriting/', '异常核保-年龄超过60岁转人工', '先用1960年身份证试算，再核保', {**base_underwriting, 'quote_no': '${quote_no_from_age_60_plus}'}, 'HTTP 201；decision=REFERRED；reasons 包含年龄超过60周岁')
add('自动核保', 'POST /api/insurance/underwriting/', '异常核保-年龄超过65岁拒保', '先用1950年身份证试算，再核保', {**base_underwriting, 'quote_no': '${quote_no_from_age_65_plus}'}, 'HTTP 201；decision=DECLINED；reasons 包含年龄超过65周岁')
add('自动核保', 'POST /api/insurance/underwriting/', '异常核保-职业5类转人工', '先用 occupation_category=5 试算，再核保', {**base_underwriting, 'quote_no': '${quote_no_from_occupation_5}'}, 'HTTP 201；decision=REFERRED；manual_review_required=true；reasons 包含职业类别为5类')
add('自动核保', 'POST /api/insurance/underwriting/', '异常核保-职业6类拒保', '先用 occupation_category=6 试算，再核保', {**base_underwriting, 'quote_no': '${quote_no_from_occupation_6}'}, 'HTTP 201；decision=DECLINED；reasons 包含职业类别为6类')
add('自动核保', 'POST /api/insurance/underwriting/', '异常核保-试算单过期', '将 PremiumQuote.valid_until 调整为当前时间之前再核保', base_underwriting, 'HTTP 400；code=BUSINESS_ERROR；message=试算单已过期，请重新试算')

add('承保出单', 'POST /api/insurance/policies/', '正常出单-核保通过且支付成功', '先试算，再核保 APPROVED，再传 underwriting_no 和 payable_premium', base_policy, 'HTTP 201；返回 policy_no；status=ISSUED；quote_no/underwriting_no 关联正确')

payload = clone(base_policy); payload['underwriting_no'] = 'UW_NOT_EXISTS'
add('承保出单', 'POST /api/insurance/policies/', '异常出单-underwriting_no不存在', '未核保或传错核保单号', payload, 'HTTP 404；code=NOT_FOUND；message=核保记录不存在')

payload = clone(base_policy); payload['underwriting_no'] = '${referred_underwriting_no}'
add('承保出单', 'POST /api/insurance/policies/', '异常出单-核保转人工不能出单', '使用 decision=REFERRED 的 underwriting_no', payload, 'HTTP 400；code=BUSINESS_ERROR；message=仅自动核保通过的记录允许线上承保出单')

payload = clone(base_policy); payload['underwriting_no'] = '${declined_underwriting_no}'
add('承保出单', 'POST /api/insurance/policies/', '异常出单-核保拒保不能出单', '使用 decision=DECLINED 的 underwriting_no', payload, 'HTTP 400；code=BUSINESS_ERROR；message=仅自动核保通过的记录允许线上承保出单')

payload = clone(base_policy); payload['payment']['pay_status'] = 'FAIL'
add('承保出单', 'POST /api/insurance/policies/', '异常出单-支付失败', 'payment.pay_status=FAIL', payload, 'HTTP 400；DRF 参数校验失败；仅支付成功后允许承保出单')

payload = clone(base_policy); payload['payment']['paid_amount'] = '1.00'
add('承保出单', 'POST /api/insurance/policies/', '异常出单-支付金额不等于应缴保费', 'paid_amount != 试算返回 payable_premium', payload, 'HTTP 400；code=BUSINESS_ERROR；message=支付金额与应缴保费不一致')

payload = clone(base_policy); del payload['payment']['pay_order_no']
add('承保出单', 'POST /api/insurance/policies/', '异常出单-支付订单号缺失', 'payment.pay_order_no 缺失', payload, 'HTTP 400；DRF 参数校验失败；支付信息缺少字段 pay_order_no')

payload = clone(base_policy); payload['consent_confirmed'] = False
add('承保出单', 'POST /api/insurance/policies/', '异常出单-未确认投保声明', 'consent_confirmed=false', payload, 'HTTP 400；DRF 参数校验失败；必须确认投保声明、免责条款和电子保单协议')

add('承保出单', 'POST /api/insurance/policies/', '异常出单-重复出单', '同一个 APPROVED underwriting_no 连续调用两次出单接口', base_policy, '第一次 HTTP 201；第二次 HTTP 400；message=该核保记录已出单，不能重复出单')
add('承保出单', 'POST /api/insurance/policies/', '异常出单-核保结果过期', '将 UnderwritingCase.valid_until 调整为当前时间之前再出单', base_policy, 'HTTP 400；code=BUSINESS_ERROR；message=核保结果已过期，请重新核保')

wb = Workbook()
ws = wb.active
ws.title = 'Cases'
headers = ['接口中文名', '接口路径', '测试标题', '测试数据', '请求body', '预期结果']
ws.append(headers)
for row in cases:
    ws.append(row)

for cell in ws[1]:
    cell.font = Font(bold=True)
    cell.fill = PatternFill('solid', fgColor='D9EAF7')
    cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)

for idx, width in enumerate([16, 36, 34, 40, 72, 60], start=1):
    ws.column_dimensions[chr(64 + idx)].width = width

for row in ws.iter_rows(min_row=2):
    for cell in row:
        cell.alignment = Alignment(vertical='top', wrap_text=True)

ws.freeze_panes = 'A2'
ws.auto_filter.ref = ws.dimensions
wb.save(output)

print(output.resolve())
print(f'cases={len(cases)}')
