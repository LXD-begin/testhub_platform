# 保险接口加密说明

保险接口支持 AES-256-GCM 加密信封。普通 JSON 调用仍然可用；如果请求体是加密信封，后端会先解密再走原业务校验，并自动返回加密响应。

## 配置密钥

在 `.env` 中配置：

```bash
INSURANCE_CRYPTO_KEY=replace-with-a-strong-insurance-api-key
```

后端会使用这个值派生 256-bit AES 密钥。生产环境必须替换为高强度密钥，并避免和 `SECRET_KEY` 共用。

## POST 加密请求格式

把原始业务 JSON 加密后，提交下面这个外层 JSON：

```json
{
  "encrypted": true,
  "algorithm": "AES-256-GCM",
  "iv": "base64url-iv",
  "ciphertext": "base64url-ciphertext-with-tag"
}
```

也可以同时带请求头：

```http
X-Insurance-Encrypted: true
```

加密请求的响应也是同样的加密信封，响应头会包含：

```http
X-Insurance-Encrypted: true
```

## GET 加密响应

查询接口没有请求体，需要加密响应时加查询参数：

```http
GET /api/insurance/premium-trials/{quote_no}/?encrypted=true
```

或请求头：

```http
X-Insurance-Response-Encrypted: true
```
