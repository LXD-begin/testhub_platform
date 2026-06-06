# 保险出单接口测试设计文档

本文档面向接口测试用例设计，覆盖当前项目中 `apps.insurance` 提供的全部 HTTP 接口。文档按推荐业务流程排序，同时保留旧兼容接口说明。

## 1. 通用约定

### 1.1 基础信息

| 项 | 内容 |
| --- | --- |
| 基础路径 | `/api/insurance/` |
| 请求格式 | `application/json` |
| 响应格式 | 统一 JSON 外层结构：`code`、`message`、`data` |
| 日期格式 | `YYYY-MM-DD`，例如 `2026-06-06` |
| 日期时间格式 | ISO 8601，例如 `2026-06-06T10:30:00+08:00` |
| 金额格式 | 字符串或数字均可传入校验，响应中金额通常为保留 2 位小数的字符串 |
| 认证 | 默认不启用；配置 `INSURANCE_API_KEY` 后必须传 `X-Insurance-API-Key` 或 `Authorization: Bearer <key>` |

### 1.2 统一响应结构

所有保险接口都会返回统一外层结构。本文档后续章节中的“成功响应”示例，如未特别说明，均表示外层 `data` 中的业务对象。

成功响应体：

```json
{
  "code": 200,
  "message": "成功",
  "data": {
    "业务字段": "业务数据"
  }
}
```

异常响应体：

```json
{
  "code": 999,
  "message": "失败原因或参数校验失败",
  "data": {
    "错误字段或错误类型": "错误详情"
  }
}
```

字段说明：

| 字段 | 类型 | 含义 | 用例关注点 |
| --- | --- | --- | --- |
| `code` | integer | 业务响应码，成功固定为 `200`，异常固定为 `999` | 所有接口都应优先断言该字段 |
| `message` | string | 成功时为 `成功`，异常时为失败原因或 `参数校验失败` | 异常用例可断言具体提示 |
| `data` | object/null/array | 成功时为接口业务数据；异常时为字段错误、错误类型或空 | 成功用例继续断言业务字段，异常用例断言错误详情 |

### 1.3 通用错误响应

DRF 参数校验失败时 HTTP 状态通常为 `400`，字段级错误会放在统一响应的 `data` 中：

```json
{
  "code": 999,
  "message": "参数校验失败",
  "data": {
    "plan_code": [
      "\"VIP\" is not a valid choice."
    ]
  }
}
```

业务校验失败时返回：

```json
{
  "code": 999,
  "message": "业务错误原因",
  "data": {
    "error_type": "BUSINESS_ERROR"
  }
}
```

资源不存在时返回：

```json
{
  "code": 999,
  "message": "资源不存在说明",
  "data": {
    "error_type": "NOT_FOUND"
  }
}
```

加密/解密失败时返回：

```json
{
  "code": 999,
  "message": "加密错误原因",
  "data": {
    "error_type": "CRYPTO_ERROR"
  }
}
```

### 1.4 加密请求说明

所有继承 `EncryptedInsuranceAPIView` 的接口都支持加密信封。普通 JSON 可直接调用；如果请求体是加密信封，后端会先解密再进入业务校验。

加密请求体：

```json
{
  "encrypted": true,
  "algorithm": "AES-256-GCM",
  "iv": "base64url-iv",
  "ciphertext": "base64url-ciphertext-with-tag"
}
```

可选请求头：

```http
X-Insurance-Encrypted: true
X-Insurance-Response-Encrypted: true
```

GET 接口如需加密响应，也可加：

```text
?encrypted=true
```

### 1.5 Redis 缓存读写约定

当前保险详情缓存采用同一套详情数据结构：

- 写接口成功后，会把本次创建或更新后的详情数据主动写入 Redis。
- GET 详情接口会先读 Redis；如果缓存未命中，则查询数据库并把查询结果写入 Redis。
- 状态变更时会先删除旧缓存，写接口成功返回前再写入最新缓存，避免后续 GET 读到旧状态。
- Redis 中缓存的是统一响应外层 `data` 里的业务对象，不包含外层 `code` 和 `message`。

重点写缓存接口：

| 写接口 | 主动写入/刷新缓存 |
| --- | --- |
| `POST /api/insurance/premium-trials/` | 试算单 `insurance:premium_quote:{quote_no}` |
| `POST /api/insurance/applications/` | 投保单，并刷新关联试算单 |
| `POST /api/insurance/applications/{application_no}/underwriting/` | 核保记录，并刷新投保单、试算单 |
| `POST /api/insurance/underwriting/{underwriting_no}/manual-review/` | 刷新核保记录、投保单、试算单 |
| `POST /api/insurance/payment-orders/` | 支付订单，并刷新投保单、试算单、核保记录 |
| `POST /api/insurance/payment-orders/{pay_order_no}/confirm/` | 刷新支付订单、投保单、试算单、核保记录 |
| `POST /api/insurance/application-policies/` | 保单，并刷新投保单、试算单、核保记录、支付订单 |
| `POST /api/insurance/underwriting/` | 旧版核保记录，并刷新关联试算单 |
| `POST /api/insurance/policies/` | 旧版保单，并刷新关联试算单、核保记录 |

### 1.6 API Key 鉴权约定

`.env` 中 `INSURANCE_API_KEY` 留空时，本地开发和接口测试可直接请求。配置后，所有继承保险接口基类的接口都会校验 API Key。

请求头二选一：

```http
X-Insurance-API-Key: your-api-key
Authorization: Bearer your-api-key
```

缺少或错误时返回：

```json
{
  "code": 999,
  "message": "接口鉴权失败",
  "data": {
    "detail": "接口鉴权失败"
  }
}
```

## 2. 公共字段定义

### 2.1 人员信息 `Person`

用于 `applicant` 投保人和 `insured` 被保人。

| 字段 | 类型 | 必填 | 约束 | 含义 | 用例关注点 |
| --- | --- | --- | --- | --- | --- |
| `name` | string | 是 | 最大 64 字符 | 姓名 | 空值、超长、中文/英文 |
| `id_type` | string | 是 | `IDENTITY_CARD`、`PASSPORT` | 证件类型 | 非枚举值应 400 |
| `id_no` | string | 是 | 最大 32 字符 | 证件号码 | 身份证 18 位时会从第 7-14 位解析生日 |
| `mobile` | string | 否 | 最大 20 字符，可空字符串 | 手机号 | 当前只做长度校验，不校验手机号格式 |
| `email` | string | 否 | 邮箱格式，可空字符串 | 邮箱 | 非邮箱格式应 400 |
| `date_of_birth` | date | 否 | `YYYY-MM-DD` | 出生日期 | 非身份证证件时可用于计算年龄 |
| `gender` | string | 否 | `M`、`F` | 性别 | 非枚举值应 400 |

示例：

```json
{
  "name": "张三",
  "id_type": "IDENTITY_CARD",
  "id_no": "110101199001011234",
  "mobile": "13800138000",
  "email": "zhangsan@example.com",
  "gender": "M"
}
```

### 2.2 核保告知 `disclosures`

当前代码允许任意 JSON 对象，但业务规则会读取以下字段：

| 字段 | 类型 | 必填 | 含义 | 业务影响 |
| --- | --- | --- | --- | --- |
| `truth_declaration_confirmed` | boolean | 建议必填 | 是否确认如实告知 | 缺失或 `false` 时核保结论为 `DECLINED` |
| `health_answers` | object | 否 | 健康告知项 | 任一值为 truthy 且未拒保时，核保结论为 `REFERRED` |

示例：

```json
{
  "truth_declaration_confirmed": true,
  "health_answers": {
    "has_major_disease": false,
    "has_disability": false,
    "has_recent_claim": false
  }
}
```

### 2.3 受益人字段

| 字段 | 类型 | 必填 | 枚举/格式 | 含义 |
| --- | --- | --- | --- | --- |
| `beneficiary_type` | string | 否 | `LEGAL`、`DESIGNATED`，默认 `LEGAL` | 受益人类型，法定或指定 |
| `beneficiaries` | array<object> | 否 | 默认 `[]` | 指定受益人列表，当前只校验为对象数组，不校验对象内部字段 |

指定受益人示例：

```json
[
  {
    "name": "李四",
    "relation": "SPOUSE",
    "id_type": "IDENTITY_CARD",
    "id_no": "110101199201011234",
    "benefit_ratio": 100
  }
]
```

## 3. 推荐主流程接口

推荐主流程：

```text
保费试算 -> 创建投保单 -> 投保单核保 -> 人工核保(可选) -> 创建支付订单 -> 支付回调确认 -> 承保出单 -> 查询保单
```

## 3.0 产品配置查询

真实投保流程里，前端通常先查询产品、计划、保障责任和费率配置，再进入试算。当前项目已把产品、计划、责任、年龄费率和职业费率落到数据库配置表。

### 3.0.1 查询产品列表

### 接口

```http
GET /api/insurance/products/
```

### 用途

查询在售产品列表。返回每个产品下的计划、保障责任、年龄费率和职业费率配置。

### 成功响应

状态码：`200`

`data` 为数组，元素字段如下：

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `product_code` | string | 产品代码，例如 `PA_C_ACCIDENT` |
| `product_name` | string | 产品名称 |
| `description` | string | 产品详情说明 |
| `status` | string | 产品状态，`ACTIVE` 在售，`INACTIVE` 停售 |
| `min_age` / `max_age` | integer | 产品允许的被保人年龄范围 |
| `min_period_months` / `max_period_months` | integer | 产品允许的保障期限范围，单位月 |
| `effective_start` / `effective_end` | date/null | 产品销售起止日期 |
| `plans` | array | 产品计划列表 |
| `age_rate_factors` | array | 年龄费率因子 |
| `occupation_rate_factors` | array | 职业类别费率因子 |

`plans` 元素字段：

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `plan_code` | string | 计划代码，例如 `BASIC`、`STANDARD`、`PREMIUM` |
| `plan_name` | string | 计划名称 |
| `base_premium` | string | 基础保费 |
| `is_enabled` | boolean | 是否启用 |
| `sort_order` | integer | 展示排序 |
| `coverages` | array | 该计划下的保障责任 |

`coverages` 元素字段：

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `coverage_code` | string | 责任代码 |
| `coverage_name` | string | 责任名称 |
| `insured_amount` | string | 保额 |
| `description` | string | 责任说明 |
| `sort_order` | integer | 展示排序 |

### 3.0.2 查询产品详情

### 接口

```http
GET /api/insurance/products/{product_code}/
```

### 路径参数

| 参数 | 类型 | 必填 | 含义 |
| --- | --- | --- | --- |
| `product_code` | string | 是 | 产品代码 |

### 成功响应

状态码：`200`

响应字段同“查询产品列表”的单个产品对象。

## 3.1 保费试算

### 接口

```http
POST /api/insurance/premium-trials/
```

### 用途

根据产品、计划、保障期限、人员、职业类别等信息计算保费，生成 `quote_no`。后续创建投保单或旧版核保必须引用该试算单号。

### 请求参数

| 字段 | 类型 | 必填 | 约束 | 含义 | 用例关注点 |
| --- | --- | --- | --- | --- | --- |
| `product_code` | string | 是 | 最大 32 字符；当前仅支持 `PA_C_ACCIDENT` | 产品代码 | 不存在产品返回业务错误 |
| `plan_code` | string | 是 | `BASIC`、`STANDARD`、`PREMIUM` | 计划代码 | 非枚举值 400 |
| `effective_date` | date | 是 | `YYYY-MM-DD` | 保险起期 | 格式错误 400 |
| `insurance_period_months` | integer | 否 | 1-12，默认 12 | 保障期间，单位月 | 0、13、非数字应 400 |
| `applicant` | object | 是 | 见 `Person` | 投保人信息 | 缺字段应 400 |
| `insured` | object | 是 | 见 `Person` | 被保人信息 | 身份证生日会影响年龄因子 |
| `occupation_code` | string | 是 | 最大 16 字符 | 职业代码 | 当前仅保存/参与传参，不做字典校验 |
| `occupation_category` | integer | 是 | 1-6 | 职业类别 | 影响保费和核保规则 |
| `has_social_security` | boolean | 否 | 默认 `true` | 是否有社保 | `true` 时保费有 0.95 折扣 |
| `channel_code` | string | 否 | 最大 32 字符，默认 `C_APP` | 渠道代码 | 当前试算响应不直接返回该字段 |

### 请求示例

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

### 成功响应

状态码：`201`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `quote_no` | string | 试算单号，格式类似 `QT20260606000001` |
| `product_code` | string | 产品代码 |
| `product_name` | string | 产品名称 |
| `plan_code` | string | 计划代码 |
| `plan_name` | string | 计划名称 |
| `applicant` | object | 投保人快照 |
| `insured` | object | 被保人快照 |
| `coverages` | array<object> | 保障责任列表 |
| `premium_detail` | object | 保费明细 |
| `effective_date` | date | 保险起期 |
| `expiry_date` | date | 保险止期，当前按 `月份 * 30 - 1` 天计算 |
| `status` | string | 试算单状态，初始为 `QUOTED` |
| `valid_until` | datetime | 试算单有效截止时间，创建后 30 分钟 |
| `created_at` | datetime | 创建时间 |

`premium_detail` 字段：

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `currency` | string | 币种，当前为 `CNY` |
| `standard_premium` | string | 标准保费 |
| `discount_amount` | string | 优惠金额 |
| `payable_premium` | string | 应缴保费，后续支付金额必须等于该值 |
| `pricing_factors` | object | 计价因子，用于核保规则判断 |

响应示例：

```json
{
  "quote_no": "QT20260606000001",
  "product_code": "PA_C_ACCIDENT",
  "product_name": "平安个人综合意外险",
  "plan_code": "STANDARD",
  "plan_name": "标准版",
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
  "coverages": [
    {
      "code": "ACCIDENT_DEATH",
      "name": "意外身故/伤残",
      "insured_amount": "300000.00"
    }
  ],
  "premium_detail": {
    "currency": "CNY",
    "standard_premium": "199.00",
    "discount_amount": "9.95",
    "payable_premium": "189.05",
    "pricing_factors": {
      "insured_age": 36,
      "age_factor": "1.00",
      "occupation_category": 2,
      "occupation_factor": "1.00",
      "social_security_discount": "0.95",
      "period_months": 12
    }
  },
  "effective_date": "2026-06-06",
  "expiry_date": "2027-06-01",
  "status": "QUOTED",
  "valid_until": "2026-06-06T10:30:00+08:00",
  "created_at": "2026-06-06T10:00:00+08:00"
}
```

### 业务规则和测试点

| 场景 | 预期 |
| --- | --- |
| `product_code` 不存在 | `400 BUSINESS_ERROR`，产品不存在或已下架 |
| `plan_code` 不是枚举值 | `400` 字段校验失败 |
| `insurance_period_months=0` 或 `13` | `400` 字段校验失败 |
| `occupation_category=1/2/3/4/5/6` | 保费不同；5、6 会影响后续核保结论 |
| 身份证号长度为 18 | 根据身份证生日计算年龄 |
| 非身份证且未传生日 | 默认年龄按 30 岁计算 |

## 3.2 查询试算单详情

### 接口

```http
GET /api/insurance/premium-trials/{quote_no}/
```

### 路径参数

| 参数 | 类型 | 必填 | 含义 |
| --- | --- | --- | --- |
| `quote_no` | string | 是 | 试算单号 |

### 成功响应

状态码：`200`

响应字段同“保费试算”成功响应。

### 缓存说明

该接口已接入 Redis 缓存，缓存 key：

```text
insurance:premium_quote:{quote_no}
```

Django 实际写入 Redis 时会加上 key prefix 和版本号，示例：

```text
aitesthub:1:insurance:premium_quote:QT20260606000001
```

## 3.3 创建投保单

### 接口

```http
POST /api/insurance/applications/
```

### 用途

基于有效试算单创建正式投保申请，沉淀投保告知、受益人、条款确认等信息。

### 请求参数

| 字段 | 类型 | 必填 | 约束 | 含义 | 用例关注点 |
| --- | --- | --- | --- | --- | --- |
| `quote_no` | string | 是 | 最大 32 字符 | 试算单号 | 不存在返回 404；过期返回业务错误 |
| `disclosures` | object | 否 | 默认 `{}` | 核保告知信息 | 后续核保会使用 |
| `beneficiary_type` | string | 否 | `LEGAL`、`DESIGNATED`，默认 `LEGAL` | 受益人类型 | 非枚举值 400 |
| `beneficiaries` | array<object> | 否 | 默认 `[]` | 指定受益人列表 | 当前只校验数组元素为对象 |
| `consents` | object | 是 | 必须包含并确认 3 个字段 | 投保确认留痕 | 缺任一确认返回业务错误 |
| `channel_code` | string | 否 | 最大 32 字符，默认 `C_APP` | 渠道代码 | 记录到投保单 |

`consents` 必须为：

| 字段 | 类型 | 必填 | 含义 |
| --- | --- | --- | --- |
| `terms_confirmed` | boolean | 是 | 是否确认保险条款 |
| `exclusions_confirmed` | boolean | 是 | 是否确认免责条款 |
| `electronic_policy_confirmed` | boolean | 是 | 是否确认电子保单协议 |

### 请求示例

```json
{
  "quote_no": "QT20260606000001",
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

### 成功响应

状态码：`201`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `application_no` | string | 投保单号，格式类似 `APP20260606000001` |
| `quote_no` | string | 关联试算单号 |
| `status` | string | 投保单状态，初始为 `CREATED` |
| `product_code` | string | 产品代码 |
| `product_name` | string | 产品名称 |
| `plan_code` | string | 计划代码 |
| `plan_name` | string | 计划名称 |
| `applicant` | object | 投保人信息 |
| `insured` | object | 被保人信息 |
| `disclosures` | object | 核保告知 |
| `beneficiary_type` | string | 受益人类型 |
| `beneficiaries` | array | 指定受益人列表 |
| `consents` | object | 投保确认信息 |
| `premium_detail` | object | 试算保费明细 |
| `channel_code` | string | 渠道代码 |
| `submitted_at` | datetime/null | 提交核保时间，创建时通常为 `null` |
| `created_at` | datetime | 创建时间 |
| `updated_at` | datetime | 更新时间 |

### 业务规则和测试点

| 场景 | 预期 |
| --- | --- |
| `quote_no` 不存在 | `404 NOT_FOUND` |
| 试算单已过期 | `400 BUSINESS_ERROR` |
| 同一 `quote_no` 重复创建投保单 | `400 BUSINESS_ERROR` |
| `consents` 缺 `terms_confirmed` | `400 BUSINESS_ERROR` |
| `consents` 某个确认字段为 `false` | `400 BUSINESS_ERROR` |

## 3.4 查询投保单详情

### 接口

```http
GET /api/insurance/applications/{application_no}/
```

### 路径参数

| 参数 | 类型 | 必填 | 含义 |
| --- | --- | --- | --- |
| `application_no` | string | 是 | 投保单号 |

### 成功响应

状态码：`200`

响应字段同“创建投保单”成功响应。

### 缓存说明

缓存 key：

```text
insurance:application:{application_no}
```

## 3.5 投保单提交核保

### 接口

```http
POST /api/insurance/applications/{application_no}/underwriting/
```

### 用途

以投保单为主实体提交核保，生成核保记录，并按核保结论同步投保单状态。

### 路径参数

| 参数 | 类型 | 必填 | 含义 |
| --- | --- | --- | --- |
| `application_no` | string | 是 | 投保单号 |

### 请求参数

| 字段 | 类型 | 必填 | 约束 | 含义 |
| --- | --- | --- | --- | --- |
| `disclosures` | object | 否 | JSON 对象 | 新的告知信息；不传则使用投保单已有告知 |
| `beneficiary_type` | string | 否 | `LEGAL`、`DESIGNATED` | 可覆盖投保单受益人类型 |
| `beneficiaries` | array<object> | 否 | 对象数组 | 可覆盖投保单受益人列表 |

### 请求示例

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

### 成功响应

状态码：`201`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `uw_no` | string | 核保单号，格式类似 `UW20260606000001` |
| `quote_no` | string | 关联试算单号 |
| `application_no` | string/null | 关联投保单号 |
| `decision` | string | 核保结论：`APPROVED`、`REFERRED`、`DECLINED` |
| `risk_level` | string | 风险等级：`LOW`、`MEDIUM`、`HIGH`、`REJECT` |
| `reasons` | array<string> | 核保原因 |
| `manual_review_required` | boolean | 是否需要人工核保 |
| `valid_until` | datetime | 核保结果有效截止时间，创建后 24 小时 |
| `created_at` | datetime | 核保时间 |

### 核保业务规则

| 条件 | `decision` | `risk_level` | 说明 |
| --- | --- | --- | --- |
| 职业类别 1-4、年龄 <=60、健康告知无异常、确认如实告知 | `APPROVED` | `LOW` | 可继续支付 |
| 职业类别 5 | `REFERRED` | `HIGH` | 需要人工复核 |
| 职业类别 6 | `DECLINED` | `REJECT` | 拒保 |
| 年龄 >60 且 <=65，且此前未拒保 | `REFERRED` | `MEDIUM` | 需要人工复核 |
| 年龄 >65 | `DECLINED` | `REJECT` | 拒保 |
| 任意健康告知值为 true，且此前未拒保 | `REFERRED` | `MEDIUM` | 需要人工复核 |
| `truth_declaration_confirmed` 缺失或为 false | `DECLINED` | `REJECT` | 拒保 |

### 投保单状态流转

| 核保结论 | 投保单状态 |
| --- | --- |
| `APPROVED` | `UNDERWRITING_APPROVED` |
| `REFERRED` | `UNDERWRITING_REFERRED` |
| `DECLINED` | `UNDERWRITING_DECLINED` |

### 业务规则和测试点

| 场景 | 预期 |
| --- | --- |
| 投保单不存在 | `404 NOT_FOUND` |
| 投保单状态为 `PAYMENT_PENDING`、`PAID`、`ISSUED`、`CLOSED`、`UNDERWRITING_DECLINED` | `400 BUSINESS_ERROR` |
| 关联试算单过期 | `400 BUSINESS_ERROR` |
| 已出单试算单再次核保 | `400 BUSINESS_ERROR` |

## 3.6 查询核保记录详情

### 接口

```http
GET /api/insurance/underwriting/{underwriting_no}/
```

### 路径参数

| 参数 | 类型 | 必填 | 含义 |
| --- | --- | --- | --- |
| `underwriting_no` | string | 是 | 核保单号 |

### 成功响应

状态码：`200`

响应字段同“投保单提交核保”成功响应。

### 缓存说明

缓存 key：

```text
insurance:underwriting:{underwriting_no}
```

## 3.7 人工核保复核

### 接口

```http
POST /api/insurance/underwriting/{underwriting_no}/manual-review/
```

### 用途

仅用于自动核保结论为 `REFERRED` 的投保单流程核保记录，由人工核保员给出最终核保意见。

### 路径参数

| 参数 | 类型 | 必填 | 含义 |
| --- | --- | --- | --- |
| `underwriting_no` | string | 是 | 核保单号 |

### 请求参数

| 字段 | 类型 | 必填 | 约束 | 含义 |
| --- | --- | --- | --- | --- |
| `decision` | string | 是 | `APPROVED`、`REFERRED`、`DECLINED` | 人工核保结论 |
| `risk_level` | string | 是 | `LOW`、`MEDIUM`、`HIGH`、`REJECT` | 人工评定风险等级 |
| `reasons` | array<string> | 否 | 默认 `[]` | 人工核保原因 |
| `review_notes` | string | 否 | 可空，默认 `""` | 内部复核备注 |
| `reviewer` | string | 是 | 最大 64 字符 | 复核人员 |

### 请求示例

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

### 成功响应

状态码：`201`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `review_no` | string | 人工核保复核单号，格式类似 `MR20260606000001` |
| `underwriting_no` | string | 关联核保单号 |
| `decision` | string | 人工核保结论 |
| `risk_level` | string | 风险等级 |
| `reasons` | array<string> | 人工复核原因 |
| `review_notes` | string | 复核备注 |
| `reviewer` | string | 复核人员 |
| `reviewed_at` | datetime | 复核时间 |

### 业务规则和测试点

| 场景 | 预期 |
| --- | --- |
| 核保记录不存在 | `404 NOT_FOUND` |
| 核保记录不是 `REFERRED` 且不需要人工复核 | `400 BUSINESS_ERROR` |
| 同一核保记录重复人工复核 | `400 BUSINESS_ERROR` |
| 旧版核保接口生成的记录未关联投保单 | `400 BUSINESS_ERROR` |
| 人工复核 `APPROVED` | 投保单状态变为 `UNDERWRITING_APPROVED` |
| 人工复核 `DECLINED` | 投保单状态变为 `UNDERWRITING_DECLINED` |

## 3.8 创建支付订单

### 接口

```http
POST /api/insurance/payment-orders/
```

### 用途

基于核保通过的投保单创建服务端支付订单。推荐流程中后续出单只认可服务端支付订单状态，不认可前端自报支付成功。

### 请求参数

| 字段 | 类型 | 必填 | 约束 | 含义 |
| --- | --- | --- | --- | --- |
| `application_no` | string | 是 | 最大 32 字符 | 投保单号 |
| `pay_channel` | string | 否 | 最大 32 字符，默认 `MOCK` | 支付渠道，例如 `MOCK`、`WECHAT`、`ALIPAY` |

### 请求示例

```json
{
  "application_no": "APP20260606000001",
  "pay_channel": "WECHAT"
}
```

### 成功响应

状态码：`201`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `pay_order_no` | string | 支付订单号，格式类似 `PAY20260606000001` |
| `application_no` | string | 关联投保单号 |
| `quote_no` | string | 关联试算单号 |
| `underwriting_no` | string | 关联核保单号 |
| `amount` | string/decimal | 应付金额，等于试算 `payable_premium` |
| `status` | string | 支付状态：`CREATED`、`SUCCESS`、`FAILED`、`CLOSED` |
| `pay_channel` | string | 支付渠道 |
| `external_trade_no` | string | 外部支付流水号，创建时通常为空 |
| `paid_at` | datetime/null | 支付成功时间 |
| `created_at` | datetime | 创建时间 |
| `updated_at` | datetime | 更新时间 |

### 业务规则和测试点

| 场景 | 预期 |
| --- | --- |
| 投保单不存在 | `404 NOT_FOUND` |
| 投保单未核保通过 | `400 BUSINESS_ERROR` |
| 投保单已出单 | `400 BUSINESS_ERROR` |
| 未找到有效核保通过记录 | `400 BUSINESS_ERROR` |
| 核保结果过期 | `400 BUSINESS_ERROR` |
| 已有成功支付订单 | `400 BUSINESS_ERROR` |
| 已有 `CREATED` 待支付订单 | 返回已有待支付订单，不重复创建 |
| 创建成功 | 投保单状态变为 `PAYMENT_PENDING` |

## 3.9 查询支付订单详情

### 接口

```http
GET /api/insurance/payment-orders/{pay_order_no}/
```

### 路径参数

| 参数 | 类型 | 必填 | 含义 |
| --- | --- | --- | --- |
| `pay_order_no` | string | 是 | 支付订单号 |

### 成功响应

状态码：`200`

响应字段同“创建支付订单”成功响应。

### 缓存说明

缓存 key：

```text
insurance:payment_order:{pay_order_no}
```

## 3.10 支付订单回调确认

### 接口

```http
POST /api/insurance/payment-orders/{pay_order_no}/confirm/
```

### 用途

模拟支付中心回调，确认支付结果。真实系统应在这里验签并核对支付平台流水。

### 路径参数

| 参数 | 类型 | 必填 | 含义 |
| --- | --- | --- | --- |
| `pay_order_no` | string | 是 | 支付订单号 |

### 请求参数

| 字段 | 类型 | 必填 | 约束 | 含义 |
| --- | --- | --- | --- | --- |
| `pay_status` | string | 是 | `SUCCESS`、`FAILED` | 支付结果 |
| `paid_amount` | decimal | 是 | 最多 10 位，2 位小数 | 实付金额，必须等于支付订单 `amount` |
| `external_trade_no` | string | 否 | 最大 64 字符，可空 | 外部交易流水号 |
| `pay_channel` | string | 否 | 最大 32 字符，可空 | 支付渠道 |

### 请求示例

```json
{
  "pay_status": "SUCCESS",
  "paid_amount": "189.05",
  "external_trade_no": "WX202606061030000001",
  "pay_channel": "WECHAT"
}
```

### 成功响应

状态码：`200`

响应字段同“创建支付订单”成功响应，成功后：

| 字段 | 变化 |
| --- | --- |
| `status` | 变为 `SUCCESS` |
| `external_trade_no` | 回写请求中的外部流水号 |
| `paid_at` | 写入支付成功时间 |

### 业务规则和测试点

| 场景 | 预期 |
| --- | --- |
| 支付订单不存在 | `404 NOT_FOUND` |
| `paid_amount` 与订单金额不一致 | `400 BUSINESS_ERROR` |
| `pay_status=FAILED` | 订单状态变为 `FAILED`，返回 `400 BUSINESS_ERROR` |
| 已经是 `SUCCESS` 的订单再次成功回调 | 幂等返回原订单 |
| 支付成功 | 投保单状态变为 `PAID` |

## 3.11 按投保单承保出单

### 接口

```http
POST /api/insurance/application-policies/
```

### 用途

推荐主流程的正式出单接口。要求投保单已核保通过、已支付成功，并存在服务端成功支付订单。

### 请求参数

| 字段 | 类型 | 必填 | 约束 | 含义 |
| --- | --- | --- | --- | --- |
| `application_no` | string | 是 | 最大 32 字符 | 投保单号 |
| `delivery` | object | 否 | 默认 `{}` | 电子保单送达信息，不传则默认使用投保人邮箱和手机号 |

`delivery` 建议字段：

| 字段 | 类型 | 必填 | 含义 |
| --- | --- | --- | --- |
| `email` | string | 否 | 电子保单邮件送达地址 |
| `sms_mobile` | string | 否 | 短信送达手机号 |

### 请求示例

```json
{
  "application_no": "APP20260606000001",
  "delivery": {
    "email": "zhangsan@example.com",
    "sms_mobile": "13800138000"
  }
}
```

### 成功响应

状态码：`201`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `policy_no` | string | 保单号，格式类似 `PAIC20260606000001` |
| `application_no` | string | 关联投保单号 |
| `quote_no` | string | 关联试算单号 |
| `underwriting_no` | string | 关联核保单号 |
| `pay_order_no` | string | 关联支付订单号 |
| `status` | string | 保单状态，当前为 `ISSUED` |
| `applicant` | object | 投保人信息 |
| `insured` | object | 被保人信息 |
| `coverages` | array<object> | 保障责任 |
| `premium_detail` | object | 保费明细 |
| `payment` | object | 支付信息快照 |
| `effective_date` | date | 保险起期 |
| `expiry_date` | date | 保险止期 |
| `issued_at` | datetime | 出单时间 |
| `electronic_policy` | object/null | 电子保单索引 |
| `delivery_records` | array<object> | 电子保单送达记录 |

`electronic_policy` 字段：

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `document_no` | string | 电子保单文档号 |
| `policy_no` | string | 保单号 |
| `download_url` | string | 电子保单下载地址；当前只生成地址，未实现下载接口 |
| `verify_code` | string | 验真码 |
| `generated_at` | datetime | 生成时间 |

`delivery_records` 字段：

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `delivery_no` | string | 送达流水号 |
| `policy_no` | string | 保单号 |
| `channel` | string | `EMAIL` 或 `SMS` |
| `recipient` | string | 收件邮箱或手机号 |
| `status` | string | `SENT` 或 `FAILED` |
| `payload` | object | 送达内容 |
| `sent_at` | datetime | 发送时间 |

### 业务规则和测试点

| 场景 | 预期 |
| --- | --- |
| 投保单不存在 | `404 NOT_FOUND` |
| 投保单状态不是 `PAID` | `400 BUSINESS_ERROR` |
| 投保单已出单 | `400 BUSINESS_ERROR` |
| 不存在成功支付订单 | `400 BUSINESS_ERROR` |
| 核保未通过 | `400 BUSINESS_ERROR` |
| 核保结果过期 | `400 BUSINESS_ERROR` |
| 核保记录已出单 | `400 BUSINESS_ERROR` |
| 支付订单已出单 | `400 BUSINESS_ERROR` |
| 出单成功 | 投保单状态变为 `ISSUED`，试算单状态变为 `ISSUED` |

## 3.12 查询保单详情

### 接口

```http
GET /api/insurance/policies/{policy_no}/
```

### 路径参数

| 参数 | 类型 | 必填 | 含义 |
| --- | --- | --- | --- |
| `policy_no` | string | 是 | 保单号 |

### 成功响应

状态码：`200`

响应字段同“按投保单承保出单”成功响应。

### 缓存说明

缓存 key：

```text
insurance:policy:{policy_no}
```

## 4. 旧兼容接口

以下接口仍可使用，但不是推荐主流程。它们用于兼容简化测试链路。

## 4.1 旧版自动核保

### 接口

```http
POST /api/insurance/underwriting/
```

### 用途

直接基于 `quote_no` 核保，不创建投保单。

### 请求参数

| 字段 | 类型 | 必填 | 约束 | 含义 |
| --- | --- | --- | --- | --- |
| `quote_no` | string | 是 | 最大 32 字符 | 试算单号 |
| `disclosures` | object | 是 | JSON 对象 | 核保告知 |
| `beneficiary_type` | string | 否 | `LEGAL`、`DESIGNATED`，默认 `LEGAL` | 受益人类型 |
| `beneficiaries` | array<object> | 否 | 默认 `[]` | 指定受益人 |

### 成功响应

状态码：`201`

响应字段同“投保单提交核保”，但 `application_no` 为空。

### 业务规则

同投保单核保规则，但不关联投保单，因此不能走人工复核接口。

## 4.2 旧版承保出单

### 接口

```http
POST /api/insurance/policies/
```

### 用途

直接基于核保单和前端传入的支付信息出单。该接口不创建服务端支付订单，因此不建议作为真实流程主接口。

### 请求参数

| 字段 | 类型 | 必填 | 约束 | 含义 |
| --- | --- | --- | --- | --- |
| `underwriting_no` | string | 是 | 最大 32 字符 | 核保单号 |
| `payment` | object | 是 | 必须包含 3 个字段 | 前端传入支付信息 |
| `delivery` | object | 否 | 默认 `{}` | 送达信息 |
| `consent_confirmed` | boolean | 是 | 必须为 `true` | 是否确认投保声明 |

`payment` 必须包含：

| 字段 | 类型 | 必填 | 约束 | 含义 |
| --- | --- | --- | --- | --- |
| `pay_order_no` | string | 是 | 任意字符串 | 支付订单号，旧接口不校验是否存在服务端订单 |
| `pay_status` | string | 是 | 必须为 `SUCCESS` | 支付状态 |
| `paid_amount` | decimal | 是 | 有效金额 | 实付金额，必须等于试算应缴保费 |

可额外传：

| 字段 | 类型 | 必填 | 含义 |
| --- | --- | --- | --- |
| `paid_time` | string | 否 | 支付时间 |
| `pay_channel` | string | 否 | 支付渠道 |

### 请求示例

```json
{
  "underwriting_no": "UW20260606000001",
  "payment": {
    "pay_order_no": "PAY-MOCK-001",
    "pay_status": "SUCCESS",
    "paid_amount": "189.05",
    "paid_time": "2026-06-06T10:30:00+08:00",
    "pay_channel": "WECHAT"
  },
  "delivery": {
    "email": "zhangsan@example.com",
    "sms_mobile": "13800138000"
  },
  "consent_confirmed": true
}
```

### 成功响应

状态码：`201`

响应字段同保单详情，但 `application_no` 和 `pay_order_no` 可能为空，因为旧流程未创建投保单和服务端支付订单。

### 业务规则和测试点

| 场景 | 预期 |
| --- | --- |
| 核保记录不存在 | `404 NOT_FOUND` |
| 核保结论不是 `APPROVED` | `400 BUSINESS_ERROR` |
| 核保结果过期 | `400 BUSINESS_ERROR` |
| 核保记录已出单 | `400 BUSINESS_ERROR` |
| `payment.pay_status` 不是 `SUCCESS` | `400` 字段校验失败 |
| `payment.paid_amount` 不是有效金额 | `400` 字段校验失败 |
| `paid_amount` 与 `payable_premium` 不一致 | `400 BUSINESS_ERROR` |
| `consent_confirmed=false` | `400` 字段校验失败 |

## 5. 状态和枚举汇总

### 5.1 试算单状态

| 值 | 含义 |
| --- | --- |
| `QUOTED` | 已试算 |
| `UNDERWRITTEN` | 已核保 |
| `ISSUED` | 已出单 |
| `EXPIRED` | 已失效 |

### 5.2 投保单状态

| 值 | 含义 |
| --- | --- |
| `CREATED` | 已创建 |
| `SUBMITTED` | 已提交核保 |
| `UNDERWRITING_APPROVED` | 核保通过 |
| `UNDERWRITING_REFERRED` | 待人工核保 |
| `UNDERWRITING_DECLINED` | 核保拒保 |
| `PAYMENT_PENDING` | 待支付 |
| `PAID` | 已支付 |
| `ISSUED` | 已出单 |
| `CLOSED` | 已关闭，当前预留 |

### 5.3 核保结论

| 值 | 含义 |
| --- | --- |
| `APPROVED` | 通过 |
| `REFERRED` | 转人工 |
| `DECLINED` | 拒保 |

### 5.4 风险等级

| 值 | 含义 |
| --- | --- |
| `LOW` | 低风险 |
| `MEDIUM` | 中风险 |
| `HIGH` | 高风险 |
| `REJECT` | 拒保风险 |

### 5.5 支付订单状态

| 值 | 含义 |
| --- | --- |
| `CREATED` | 已创建 |
| `SUCCESS` | 支付成功 |
| `FAILED` | 支付失败 |
| `CLOSED` | 已关闭，当前预留 |

### 5.6 保单状态

| 值 | 含义 |
| --- | --- |
| `ISSUED` | 已承保 |
| `CANCELLED` | 已撤单，当前预留 |

## 6. 建议接口用例矩阵

### 6.1 正向主流程

| 步骤 | 接口 | 关键断言 |
| --- | --- | --- |
| 1 | `POST /premium-trials/` | 返回 `quote_no`，状态 `QUOTED` |
| 2 | `POST /applications/` | 返回 `application_no`，状态 `CREATED` |
| 3 | `POST /applications/{application_no}/underwriting/` | 返回 `uw_no`，`decision=APPROVED` |
| 4 | `POST /payment-orders/` | 返回 `pay_order_no`，金额等于 `payable_premium` |
| 5 | `POST /payment-orders/{pay_order_no}/confirm/` | `status=SUCCESS`，投保单进入 `PAID` |
| 6 | `POST /application-policies/` | 返回 `policy_no`，状态 `ISSUED`，生成电子保单 |
| 7 | `GET /policies/{policy_no}/` | 能查询到保单详情 |

### 6.2 重点反向场景

| 场景 | 建议覆盖点 |
| --- | --- |
| 参数必填 | 缺少每个必填字段 |
| 参数格式 | 日期格式错误、邮箱格式错误、金额非法、布尔值非法 |
| 枚举边界 | `plan_code`、`id_type`、`beneficiary_type`、`decision`、`pay_status` 非法 |
| 数值边界 | `insurance_period_months=0/1/12/13`，`occupation_category=0/1/5/6/7` |
| 试算单过期 | 修改或构造过期试算单后创建投保单/核保 |
| 核保规则 | 职业 5 转人工、职业 6 拒保、年龄 61 转人工、年龄 66 拒保、健康告知异常转人工、未确认如实告知拒保 |
| 状态流转 | 未核保不能支付，未支付不能出单，已出单不能重复出单 |
| 支付金额 | 金额少付、多付、格式错误 |
| 幂等/重复 | 重复创建投保单、重复创建支付订单、重复支付回调、重复人工复核、重复出单 |
| 缓存 | 写接口成功后 Redis DB 1 立即出现或刷新对应 key；GET 详情缓存未命中时也会写入对应 key |
