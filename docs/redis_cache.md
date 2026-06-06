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

当前只缓存查询类详情接口：

| 数据 | 接口 | 缓存 key |
| --- | --- | --- |
| 试算单详情 | `GET /api/insurance/premium-trials/{quote_no}/` | `insurance:premium_quote:{quote_no}` |
| 核保记录详情 | `GET /api/insurance/underwriting/{underwriting_no}/` | `insurance:underwriting:{underwriting_no}` |
| 投保单详情 | `GET /api/insurance/applications/{application_no}/` | `insurance:application:{application_no}` |
| 支付订单详情 | `GET /api/insurance/payment-orders/{pay_order_no}/` | `insurance:payment_order:{pay_order_no}` |
| 保单详情 | `GET /api/insurance/policies/{policy_no}/` | `insurance:policy:{policy_no}` |

## 失效策略

以下业务操作会主动删除相关缓存：

- 核保会更新试算单状态，删除试算单缓存。
- 投保单提交核保会更新投保单、试算单和核保记录，删除相关缓存。
- 人工核保会更新核保记录和投保单，删除相关缓存。
- 创建支付订单会更新投保单状态，删除投保单缓存。
- 支付回调会更新支付订单和投保单，删除相关缓存。
- 出单会更新试算单、投保单、核保记录、支付订单和保单，删除相关缓存。

## 缓存时间

当前所有 Django 默认缓存和保险详情缓存都设置为 24 小时。保险流程里的投保单、核保、支付和出单状态会在服务层变更时主动删除相关缓存，所以状态变化后下次查询会重新写入最新缓存。

生产环境应配合更严格的 Redis 访问控制、数据脱敏、权限控制和更精细的缓存失效策略。

## 验证命令

```powershell
redis-cli keys "*insurance*"
python manage.py shell -c "from django.core.cache import cache; cache.set('ping', 'pong', 30); print(cache.get('ping'))"
```
