# 真实保险出单流程接口文档

本文档描述当前项目新增的“更接近真实保险公司出单系统”的推荐调用链路。

旧接口 `premium-trials -> underwriting -> policies` 仍然保留，便于兼容已有测试；真实流程建议使用下面的新链路：

```text
保费试算 -> 创建投保单 -> 投保单核保 -> 人工核保(可选) -> 创建支付订单 -> 支付回调确认 -> 承保出单 -> 查询保单/电子保单
```

## 通用说明

- 基础路径：`/api/insurance/`
- 请求格式：`application/json`
- 成功响应：返回对应业务对象 JSON。
- 业务失败响应：

```json
{
  "code": "BUSINESS_ERROR",
  "message": "投保单未核保通过，不能创建支付订单"
}
```

- 未找到响应：

```json
{
  "code": "NOT_FOUND",
  "message": "投保单不存在"
}
```

- 加密能力：所有新增 POST/GET 接口继承现有加密封装能力，可继续使用 `X-Insurance-Encrypted`、`X-Insurance-Response-Encrypted` 或 `?encrypted=true`。

## 状态流转

### 投保单状态

| 状态 | 含义 | 进入条件 |
| --- | --- | --- |
| `CREATED` | 已创建 | 创建投保单成功 |
| `SUBMITTED` | 已提交 | 提交核保处理中 |
| `UNDERWRITING_APPROVED` | 核保通过 | 自动核保或人工核保通过 |
| `UNDERWRITING_REFERRED` | 待人工核保 | 自动核保转人工 |
| `UNDERWRITING_DECLINED` | 核保拒保 | 自动核保或人工核保拒保 |
| `PAYMENT_PENDING` | 待支付 | 创建支付订单成功 |
| `PAID` | 已支付 | 支付订单回调成功 |
| `ISSUED` | 已出单 | 承保出单成功 |
| `CLOSED` | 已关闭 | 预留给撤单/超时关闭 |

### 核保结论

| 结论 | 含义 | 是否可支付 |
| --- | --- | --- |
| `APPROVED` | 通过 | 是 |
| `REFERRED` | 转人工 | 否，需人工复核 |
| `DECLINED` | 拒保 | 否 |

### 支付订单状态

| 状态 | 含义 | 是否可出单 |
| --- | --- | --- |
| `CREATED` | 已创建 | 否 |
| `SUCCESS` | 支付成功 | 是 |
| `FAILED` | 支付失败 | 否 |
| `CLOSED` | 已关闭 | 否 |

## 1. 保费试算

### 接口

`POST /api/insurance/premium-trials/`

### 请求

```json
{
  "product_code": "PA_C_ACCIDENT",
  "plan_code": "STANDARD",
  "effective_date": "2026-06-06",
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
    "mobile": "13800138000",
    "email": "zhangsan@example.com"
  },
  "occupation_code": "010101",
  "occupation_category": 2,
  "has_social_security": true,
  "channel_code": "C_APP"
}
```

### 响应重点字段

```json
{
  "quote_no": "QT20260605000001",
  "product_code": "PA_C_ACCIDENT",
  "plan_code": "STANDARD",
  "premium_detail": {
    "currency": "CNY",
    "standard_premium": "199.00",
    "discount_amount": "9.95",
    "payable_premium": "189.05"
  },
  "status": "QUOTED",
  "valid_until": "2026-06-05T13:30:00+08:00"
}
```

### 业务规则

- `quote_no` 是保费快照编号，后续创建投保单必须引用它。
- 试算单有效期为 30 分钟，过期后不能创建投保单或核保。

## 2. 创建投保单

### 接口

`POST /api/insurance/applications/`

### 请求

```json
{
  "quote_no": "QT20260605000001",
  "disclosures": {
    "truth_declaration_confirmed": true,
    "health_answers": {
      "has_major_disease": false,
      "has_disability": false,
      "has_recent_claim": false
    }
  },
  "beneficiary_type": "LEGAL",
  "beneficiaries": [],
  "consents": {
    "terms_confirmed": true,
    "exclusions_confirmed": true,
    "electronic_policy_confirmed": true
  },
  "channel_code": "C_APP"
}
```

### 响应重点字段

```json
{
  "application_no": "APP20260605000001",
  "quote_no": "QT20260605000001",
  "status": "CREATED",
  "disclosures": {
    "truth_declaration_confirmed": true
  },
  "consents": {
    "terms_confirmed": true,
    "exclusions_confirmed": true,
    "electronic_policy_confirmed": true
  }
}
```

### 业务规则

- 同一 `quote_no` 只能创建一张投保单。
- `terms_confirmed`、`exclusions_confirmed`、`electronic_policy_confirmed` 必须全部为 `true`。
- 投保单保存客户告知、受益人、条款确认等合规留痕。

## 3. 查询投保单

### 接口

`GET /api/insurance/applications/{application_no}/`

### 响应重点字段

```json
{
  "application_no": "APP20260605000001",
  "quote_no": "QT20260605000001",
  "status": "CREATED",
  "premium_detail": {
    "payable_premium": "189.05"
  },
  "created_at": "2026-06-05T13:00:00+08:00"
}
```

## 4. 投保单提交核保

### 接口

`POST /api/insurance/applications/{application_no}/underwriting/`

### 请求

可以不传请求体，系统使用投保单中保存的告知信息；也可以传入新的告知覆盖投保单。

```json
{
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

### 响应重点字段

```json
{
  "uw_no": "UW20260605000001",
  "quote_no": "QT20260605000001",
  "application_no": "APP20260605000001",
  "decision": "APPROVED",
  "risk_level": "LOW",
  "reasons": [
    "自动核保规则通过"
  ],
  "manual_review_required": false,
  "valid_until": "2026-06-06T13:00:00+08:00"
}
```

### 业务规则

- 核保必须基于投保单和其关联的试算单。
- 核保通过后投保单状态变为 `UNDERWRITING_APPROVED`。
- 转人工后投保单状态变为 `UNDERWRITING_REFERRED`。
- 拒保后投保单状态变为 `UNDERWRITING_DECLINED`。

## 5. 人工核保复核

仅当自动核保返回 `REFERRED` 时调用。

### 接口

`POST /api/insurance/underwriting/{underwriting_no}/manual-review/`

### 请求

```json
{
  "decision": "APPROVED",
  "risk_level": "MEDIUM",
  "reasons": [
    "人工复核健康告知材料后同意承保"
  ],
  "review_notes": "已核对客户补充说明",
  "reviewer": "underwriter01"
}
```

### 响应重点字段

```json
{
  "review_no": "MR20260605000001",
  "underwriting_no": "UW20260605000001",
  "decision": "APPROVED",
  "risk_level": "MEDIUM",
  "reasons": [
    "人工复核健康告知材料后同意承保"
  ],
  "reviewer": "underwriter01",
  "reviewed_at": "2026-06-05T13:10:00+08:00"
}
```

### 业务规则

- 只允许对 `REFERRED` 或 `manual_review_required=true` 的核保记录复核。
- 同一核保记录只能复核一次。
- 人工复核会更新原核保记录结论，并同步投保单状态。

## 6. 创建支付订单

### 接口

`POST /api/insurance/payment-orders/`

### 请求

```json
{
  "application_no": "APP20260605000001",
  "pay_channel": "WECHAT"
}
```

### 响应重点字段

```json
{
  "pay_order_no": "PAY20260605000001",
  "application_no": "APP20260605000001",
  "quote_no": "QT20260605000001",
  "underwriting_no": "UW20260605000001",
  "amount": "189.05",
  "status": "CREATED",
  "pay_channel": "WECHAT"
}
```

### 业务规则

- 只有投保单状态为 `UNDERWRITING_APPROVED` 或 `PAYMENT_PENDING` 时允许创建支付订单。
- 支付金额由服务端从试算单 `payable_premium` 生成。
- 已有成功支付订单时，不能重复创建新的成功支付链路。

## 7. 查询支付订单

### 接口

`GET /api/insurance/payment-orders/{pay_order_no}/`

### 响应重点字段

```json
{
  "pay_order_no": "PAY20260605000001",
  "application_no": "APP20260605000001",
  "amount": "189.05",
  "status": "CREATED",
  "paid_at": null
}
```

## 8. 支付回调确认

### 接口

`POST /api/insurance/payment-orders/{pay_order_no}/confirm/`

### 请求

```json
{
  "pay_status": "SUCCESS",
  "paid_amount": "189.05",
  "external_trade_no": "WX202606051300000001",
  "pay_channel": "WECHAT"
}
```

### 响应重点字段

```json
{
  "pay_order_no": "PAY20260605000001",
  "amount": "189.05",
  "status": "SUCCESS",
  "external_trade_no": "WX202606051300000001",
  "paid_at": "2026-06-05T13:15:00+08:00"
}
```

### 业务规则

- `paid_amount` 必须等于服务端支付订单金额。
- 支付成功后投保单状态变为 `PAID`。
- 成功回调是幂等的：同一订单重复成功确认会返回已有成功订单。

## 9. 真实流程承保出单

### 接口

`POST /api/insurance/application-policies/`

### 请求

```json
{
  "application_no": "APP20260605000001",
  "delivery": {
    "email": "zhangsan@example.com",
    "sms_mobile": "13800138000"
  }
}
```

### 响应重点字段

```json
{
  "policy_no": "PAIC20260605000001",
  "application_no": "APP20260605000001",
  "quote_no": "QT20260605000001",
  "underwriting_no": "UW20260605000001",
  "pay_order_no": "PAY20260605000001",
  "status": "ISSUED",
  "payment": {
    "pay_order_no": "PAY20260605000001",
    "pay_status": "SUCCESS",
    "paid_amount": "189.05",
    "pay_channel": "WECHAT"
  },
  "electronic_policy": {
    "document_no": "EP20260605000001",
    "download_url": "/api/insurance/e-policies/PAIC20260605000001/download/",
    "verify_code": "VC20260605000001"
  },
  "delivery_records": [
    {
      "delivery_no": "DL20260605000001",
      "channel": "EMAIL",
      "recipient": "zhangsan@example.com",
      "status": "SENT"
    },
    {
      "delivery_no": "DL20260605000002",
      "channel": "SMS",
      "recipient": "13800138000",
      "status": "SENT"
    }
  ]
}
```

### 业务规则

- 投保单必须是 `PAID` 状态。
- 必须存在服务端 `SUCCESS` 支付订单。
- 核保记录必须是 `APPROVED` 且未过期。
- 同一投保单、核保记录、支付订单都只能生成一张正式保单。
- 出单成功后自动生成电子保单索引和送达记录。

## 10. 查询保单

### 接口

`GET /api/insurance/policies/{policy_no}/`

### 响应重点字段

```json
{
  "policy_no": "PAIC20260605000001",
  "application_no": "APP20260605000001",
  "status": "ISSUED",
  "effective_date": "2026-06-06",
  "expiry_date": "2027-06-01",
  "electronic_policy": {
    "document_no": "EP20260605000001",
    "download_url": "/api/insurance/e-policies/PAIC20260605000001/download/",
    "verify_code": "VC20260605000001"
  },
  "delivery_records": []
}
```

## 旧接口兼容说明

以下旧接口仍可使用，但它们是简化链路，不建议作为真实出单系统主流程：

- `POST /api/insurance/underwriting/`
- `POST /api/insurance/policies/`

旧接口特点：

- 不创建投保单。
- 不创建服务端支付订单。
- 出单时仍使用前端传入的支付信息。

新增真实流程的主出单接口是：

- `POST /api/insurance/application-policies/`

## 推荐测试场景

### 自动核保通过出单

1. 创建标准职业、年龄 18-60 岁、健康告知全否的试算单。
2. 创建投保单并确认全部条款。
3. 提交核保，期望 `decision=APPROVED`。
4. 创建支付订单，期望金额等于 `payable_premium`。
5. 支付回调成功。
6. 承保出单，期望生成 `policy_no`、`electronic_policy` 和 `delivery_records`。

### 转人工后出单

1. 创建职业类别 5 或健康告知异常的试算单。
2. 提交核保，期望 `decision=REFERRED`。
3. 调人工核保复核，将 `decision` 改为 `APPROVED`。
4. 继续支付和出单。

### 拒保拦截

1. 创建职业类别 6 或年龄超过 65 岁的试算单。
2. 提交核保，期望 `decision=DECLINED`。
3. 创建支付订单应返回业务错误。

### 支付金额不一致拦截

1. 创建支付订单。
2. 支付回调时传入错误 `paid_amount`。
3. 期望返回 `BUSINESS_ERROR`，投保单不能进入 `PAID`。
