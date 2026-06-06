# Redis 缓存说明

项目使用 Django 内置 Redis cache backend，配置位于 `backend/settings.py`。

## 本地启动 Redis

```powershell
cd E:\aitesthub
powershell -ExecutionPolicy Bypass -File scripts\start_local_redis_ui.ps1
```

启动后：

```text
Redis: redis://127.0.0.1:6379/1
Redis Commander: http://127.0.0.1:8081
```

Redis Commander 默认连接 DB 1，对应 Django 的 `REDIS_URL=redis://127.0.0.1:6379/1`。

## Django 配置

`.env` 中配置：

```env
REDIS_URL=redis://127.0.0.1:6379/1
CACHE_TIMEOUT=86400
CACHE_KEY_PREFIX=aitesthub
INSURANCE_DETAIL_CACHE_TIMEOUT=86400
```

`CACHE_TIMEOUT` 和 `INSURANCE_DETAIL_CACHE_TIMEOUT` 默认都是 86400 秒，也就是 24 小时。

## 当前缓存范围

当前缓存的是保险业务详情数据。详情 GET 接口会先读缓存，缓存未命中时查询数据库并写入缓存；写接口成功后也会把本次生成或更新的详情数据主动写入缓存。

| 数据 | 接口 | 缓存 key |
| --- | --- | --- |
| 试算单详情 | `GET /api/insurance/premium-trials/{quote_no}/` | `insurance:premium_quote:{quote_no}` |
| 核保记录详情 | `GET /api/insurance/underwriting/{underwriting_no}/` | `insurance:underwriting:{underwriting_no}` |
| 投保单详情 | `GET /api/insurance/applications/{application_no}/` | `insurance:application:{application_no}` |
| 支付订单详情 | `GET /api/insurance/payment-orders/{pay_order_no}/` | `insurance:payment_order:{pay_order_no}` |
| 保单详情 | `GET /api/insurance/policies/{policy_no}/` | `insurance:policy:{policy_no}` |

## 失效策略

服务层在状态变更前后会删除旧缓存，视图层在写接口成功返回前会写入最新缓存：

- 保费试算成功后，立即写入试算单缓存。
- 核保成功后，立即写入核保记录缓存，并刷新关联试算单缓存。
- 创建投保单成功后，立即写入投保单缓存，并刷新关联试算单缓存。
- 投保单提交核保成功后，立即写入核保记录缓存，并刷新投保单和试算单缓存。
- 人工核保复核成功后，立即刷新核保记录、投保单和试算单缓存。
- 创建支付订单成功后，立即写入支付订单缓存，并刷新投保单、试算单和核保记录缓存。
- 支付回调确认成功后，立即刷新支付订单、投保单、试算单和核保记录缓存。
- 出单成功后，立即写入保单缓存，并刷新投保单、试算单、核保记录和支付订单缓存。

## 缓存时间

当前所有 Django 默认缓存和保险详情缓存都设置为 24 小时。保险流程里的投保单、核保、支付和出单状态变化时，会先删除旧缓存，再在写接口成功后写入最新缓存；如果直接调用详情 GET，缓存未命中时也会重新写入最新缓存。

生产环境应配合更严格的 Redis 访问控制、数据脱敏、权限控制和更精细的缓存失效策略。

## 验证命令

```powershell
redis-cli keys "*insurance*"
python manage.py shell -c "from django.core.cache import cache; cache.set('ping', 'pong', 30); print(cache.get('ping'))"
```
