# Django Insurance Backend

这是一个最小 Django + DRF 后端项目，当前实现了 C 端保险产品出单流程的核心接口：

1. 保费试算：生成 `quote_no`
2. 自动核保：引用 `quote_no`，生成 `underwriting_no`
3. 承保出单：引用已通过的 `underwriting_no`，支付成功后生成 `policy_no`

接口之间强关联，不能跳步调用。

## 启动

```bash
.venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

## 流程接口

### 1. 保费试算

`POST /api/insurance/premium-trials/`

前端传参：

```json
{
  "product_code": "PA_C_ACCIDENT",
  "plan_code": "STANDARD",
  "effective_date": "2026-06-05",
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
  "has_social_security": true,
  "channel_code": "C_APP"
}
```

返回核心字段：

```json
{
  "quote_no": "QT20260604000001",
  "product_code": "PA_C_ACCIDENT",
  "product_name": "平安个人综合意外险",
  "plan_code": "STANDARD",
  "plan_name": "标准版",
  "coverages": [],
  "premium_detail": {
    "currency": "CNY",
    "standard_premium": "199.00",
    "discount_amount": "9.95",
    "payable_premium": "189.05"
  },
  "effective_date": "2026-06-05",
  "expiry_date": "2027-05-30",
  "status": "QUOTED",
  "valid_until": "2026-06-04T..."
}
```

前端必须保存 `quote_no`，下一步核保要传它。

### 2. 自动核保

`POST /api/insurance/underwriting/`

前端传参：

```json
{
  "quote_no": "QT20260604000001",
  "disclosures": {
    "truth_declaration_confirmed": true,
    "health_answers": {
      "has_major_disease": false,
      "has_disability": false,
      "has_recent_claim": false
    }
  },
  "beneficiary_type": "LEGAL",
  "beneficiaries": []
}
```

返回核心字段：

```json
{
  "uw_no": "UW20260604000001",
  "quote_no": "QT20260604000001",
  "decision": "APPROVED",
  "risk_level": "LOW",
  "reasons": ["自动核保规则通过"],
  "manual_review_required": false,
  "valid_until": "2026-06-05T..."
}
```

只有 `decision = APPROVED` 才允许进入承保出单。`REFERRED` 表示转人工，`DECLINED` 表示拒保。

### 3. 承保出单

`POST /api/insurance/policies/`

前端传参：

```json
{
  "underwriting_no": "UW20260604000001",
  "payment": {
    "pay_order_no": "PAY202606040001",
    "pay_status": "SUCCESS",
    "paid_amount": "189.05",
    "paid_time": "2026-06-04T12:00:00+08:00",
    "pay_channel": "WECHAT"
  },
  "delivery": {
    "email": "zhangsan@example.com",
    "sms_mobile": "13800138000"
  },
  "consent_confirmed": true
}
```

返回核心字段：

```json
{
  "policy_no": "PAIC20260604000001",
  "quote_no": "QT20260604000001",
  "underwriting_no": "UW20260604000001",
  "status": "ISSUED",
  "premium_detail": {
    "payable_premium": "189.05"
  },
  "payment": {
    "pay_order_no": "PAY202606040001",
    "pay_status": "SUCCESS",
    "paid_amount": "189.05"
  },
  "effective_date": "2026-06-05",
  "expiry_date": "2027-05-30",
  "issued_at": "2026-06-04T..."
}
```

## 查询接口

- `GET /api/insurance/premium-trials/{quote_no}/`
- `GET /api/insurance/underwriting/{underwriting_no}/`
- `GET /api/insurance/policies/{policy_no}/`

## 关键业务规则

- 核保必须引用有效的 `quote_no`。
- 试算单 30 分钟有效。
- 核保结果 24 小时有效。
- 职业类别 6 类拒保。
- 职业类别 5 类转人工。
- 年龄超过 65 周岁拒保。
- 年龄超过 60 周岁转人工。
- 健康告知异常转人工。
- 未确认如实告知声明拒保。
- 出单必须引用 `APPROVED` 的核保记录。
- 支付状态必须是 `SUCCESS`。
- 支付金额必须等于试算返回的 `payable_premium`。
- 同一个核保记录不能重复出单。
