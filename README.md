# Django Insurance Backend

这是一个 Django + Django REST Framework 后端项目，当前实现了 C 端保险产品出单流程的后端原型。项目只包含后端代码，不包含前端页面、Celery、Channels 或历史自动化测试平台模块。

接口详情不放在 README 中，统一放在 `docs/` 目录：

- `docs/insurance_real_issuance_api.md`：保险出单流程接口文档
- `docs/insurance_api_test_reference.md`：接口测试设计参考文档，包含入参、响应字段、字段含义和用例关注点
- `docs/insurance_real_backend_optimization.md`：真实保险后端能力优化说明
- `docs/insurance_crypto.md`：保险接口加密说明
- `docs/redis_cache.md`：Redis 缓存说明

## 目录结构

```text
aitesthub/
├── apps/
│   ├── __init__.py
│   └── insurance/
│       ├── admin.py
│       ├── apps.py
│       ├── cache.py
│       ├── crypto.py
│       ├── migrations/
│       ├── models.py
│       ├── serializers.py
│       ├── services.py
│       ├── tests.py
│       ├── urls.py
│       └── views.py
├── backend/
│   ├── __init__.py
│   ├── asgi.py
│   ├── request_logging.py
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── docs/
│   ├── insurance_crypto.md
│   ├── insurance_api_test_reference.md
│   ├── insurance_real_backend_optimization.md
│   ├── insurance_real_issuance_api.md
│   └── redis_cache.md
├── logs/
├── scripts/
│   ├── generate_insurance_cases.py
│   ├── start_local_redis_ui.ps1
│   └── test_insurance_ui_flow.py
├── .env
├── .env.example
├── manage.py
├── requirements.txt
└── README.md
```

## 环境要求

- Python 3.12
- MySQL 8.x 或兼容版本
- Redis，本地开发可使用 Windows Redis fork
- Windows PowerShell

## 安装依赖

```powershell
cd E:\aitesthub
.venv\Scripts\activate
pip install -r requirements.txt
```

如果还没有虚拟环境：

```powershell
cd E:\aitesthub
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## 环境变量

本地开发使用 `.env`，示例见 `.env.example`。

核心配置：

```env
SECRET_KEY=django-insecure-change-me
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
INSURANCE_CRYPTO_KEY=replace-with-a-strong-insurance-api-key
INSURANCE_API_KEY=
INSURANCE_TOKEN_AUTH_ENABLED=True
INSURANCE_TOKEN_TTL=7200

DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your-password
DB_NAME=baoxian

REDIS_URL=redis://127.0.0.1:6379/1
CACHE_TIMEOUT=86400
CACHE_KEY_PREFIX=aitesthub
INSURANCE_DETAIL_CACHE_TIMEOUT=86400
```

## 数据库初始化

先确认 MySQL 中已经创建数据库：

```sql
CREATE DATABASE baoxian DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

执行迁移：

```powershell
cd E:\aitesthub
.venv\Scripts\activate
python manage.py migrate
```

查看迁移状态：

```powershell
python manage.py showmigrations
```

检查项目配置：

```powershell
python manage.py check
```

## Redis 启动

本地 Windows 已安装 `redis-windows` fork，并提供了启动脚本。

启动 Redis 和 Redis Commander 可视化界面：

```powershell
cd E:\aitesthub
powershell -ExecutionPolicy Bypass -File scripts\start_local_redis_ui.ps1
```

启动后地址：

```text
Redis: redis://127.0.0.1:6379/1
Redis Commander: http://127.0.0.1:8081
```

手动检查 Redis：

```powershell
redis-cli ping
```

正常返回：

```text
PONG
```

验证 Django 缓存：

```powershell
python manage.py shell -c "from django.core.cache import cache; cache.set('ping', 'pong', 30); print(cache.get('ping'))"
```

正常返回：

```text
pong
```

## 启动后端服务

```powershell
cd E:\aitesthub
.venv\Scripts\activate
python manage.py runserver
```

默认访问：

```text
http://127.0.0.1:8000/
```

保险接口统一前缀：

```text
/api/insurance/
```

获取随机 token：

```text
POST /api/insurance/auth/token/
```

调用其他保险接口时带：

```http
Authorization: Bearer <access_token>
```

产品配置查询：

```text
GET /api/insurance/products/
GET /api/insurance/products/{product_code}/
```

## 常用命令

```powershell
# 激活虚拟环境
.venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 检查 Django 配置
python manage.py check

# 执行数据库迁移
python manage.py migrate

# 查看迁移状态
python manage.py showmigrations

# 启动 Redis 和可视化界面
powershell -ExecutionPolicy Bypass -File scripts\start_local_redis_ui.ps1

# 启动后端
python manage.py runserver

# 运行测试
python manage.py test
```

## 缓存策略

项目已接入 Redis 缓存。当前缓存范围是保险业务的详情数据：详情 GET 会读缓存，缓存未命中时查询数据库并写入缓存；写接口成功后也会主动写入或刷新相关详情缓存。

- 试算单详情
- 核保记录详情
- 投保单详情
- 支付订单详情
- 保单详情

这些缓存用于降低重复查询数据库的成本。默认缓存时间为 24 小时，业务状态发生变化时会先删除旧缓存，写接口成功后再写入最新缓存，避免读到旧状态。详细说明见 `docs/redis_cache.md`。

## 产品和费率配置

项目已增加产品、计划、保障责任、年龄费率、职业费率配置表。执行 `python manage.py migrate` 后会初始化示例产品 `PA_C_ACCIDENT`，试算接口会读取数据库配置计算保费。

如果 `.env` 配置了 `INSURANCE_API_KEY`，调用保险接口时需要带以下任一请求头：

```http
X-Insurance-API-Key: your-api-key
Authorization: Bearer your-api-key
```

默认启用随机 token 鉴权。先调用：

```http
POST /api/insurance/auth/token/
```

响应中的 `access_token` 每次都会随机生成，后续接口带：

```http
Authorization: Bearer <access_token>
```

`INSURANCE_API_KEY` 只作为内部系统固定密钥绕过 token 校验使用；不需要可以保持为空。

## 接口文档

接口文档不维护在 README 中：

- 推荐主流程接口：`docs/insurance_real_issuance_api.md`
- 接口测试设计参考：`docs/insurance_api_test_reference.md`
- 真实保险后端优化说明：`docs/insurance_real_backend_optimization.md`
- 加密请求/响应说明：`docs/insurance_crypto.md`

主流程：

```text
保费试算 -> 创建投保单 -> 投保单核保 -> 人工核保(可选) -> 创建支付订单 -> 支付回调确认 -> 承保出单 -> 查询保单/电子保单
```
