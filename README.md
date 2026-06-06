# 接口自动化测试项目

这个分支是独立的接口自动化测试项目，专门维护 `python + pytest + requests + allure + logging + openpyxl` 这套软件测试框架。

后端接口项目不放在这个分支里。后端代码统一在 `dev-master` 分支维护，本分支的工具通过 Git 读取 `dev-master` 的提交变化和接口代码。

## 分支职责

| 分支 | 职责 |
| --- | --- |
| `dev-master` | Django 后端接口项目，写接口、模型、序列化器、业务逻辑 |
| `ai_api_project` | 接口自动化测试项目，写 Excel 用例、pytest 执行逻辑、Allure 报告、Git 变化分析 |

## 目录结构

```text
aitesthub/
├─ api_tests/
│  ├─ common/
│  │  ├─ assertions.py              # 统一响应断言
│  │  ├─ context.py                 # 用例变量提取和 ${变量} 替换
│  │  ├─ excel_reader.py            # Excel 用例读取
│  │  ├─ json_path.py               # 简单 JSON 路径取值
│  │  ├─ logger.py                  # 日志配置
│  │  └─ request_client.py          # requests 请求封装
│  ├─ data/
│  │  └─ insurance_api_cases.xlsx   # 接口自动化 Excel 用例
│  ├─ reports/
│  │  └─ api_contract.json          # 从 dev-master 生成的接口契约
│  ├─ testcases/
│  │  └─ test_excel_api_cases.py    # pytest 测试入口
│  └─ tools/
│     ├─ generate_api_contract.py   # 读取 dev-master 后端代码并生成接口契约
│     ├─ generate_insurance_cases_excel.py
│     └─ inspect_git_api_changes.py # 分析 dev-master 最新提交对接口测试的影响
├─ pytest.ini
├─ requirements.txt
└─ README.md
```

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

## 后端服务要求

执行接口自动化前，需要先让 `dev-master` 分支的后端服务运行起来。

推荐用 `git worktree` 单独开一个后端工作区，这样 `ai_api_project` 自动化分支和 `dev-master` 后端分支不会互相覆盖：

```powershell
cd E:\aitesthub
git worktree add E:\aitesthub-backend dev-master
cd E:\aitesthub-backend
.venv\Scripts\activate
pip install -r requirements.txt
python manage.py runserver
```

后端启动后，回到 `E:\aitesthub` 的 `ai_api_project` 分支执行自动化测试。

默认测试地址：

```text
http://127.0.0.1:8000
```

如果后端地址不是默认地址，可以在执行前指定：

```powershell
$env:API_BASE_URL="http://127.0.0.1:8000"
pytest
```

## 执行接口自动化

```powershell
cd E:\aitesthub
.venv\Scripts\activate
pytest
```

只执行某一条用例：

```powershell
pytest -k AUTH_001
```

指定 Excel 用例文件：

```powershell
$env:API_CASE_FILE="E:\aitesthub\api_tests\data\insurance_api_cases.xlsx"
pytest
```

## 查看 Allure 报告

pytest 执行后会生成原始报告数据：

```text
api_tests\reports\allure-results
```

如果本机已安装 Allure 命令行：

```powershell
allure serve api_tests\reports\allure-results
```

生成静态 HTML 报告：

```powershell
allure generate api_tests\reports\allure-results -o api_tests\reports\allure-report --clean
allure open api_tests\reports\allure-report
```

如果提示 `allure` 命令不存在，需要先安装 Allure CLI。

## Excel 用例字段

| 字段 | 含义 |
| --- | --- |
| `case_id` | 用例编号，必须唯一 |
| `module` | 模块名，用于 Allure feature |
| `title` | 用例标题 |
| `enabled` | 是否启用，填 `是` 或 `否` |
| `method` | 请求方法，例如 `GET`、`POST` |
| `path` | 接口路径，例如 `/api/insurance/products/` |
| `headers` | JSON 格式请求头 |
| `params` | JSON 格式查询参数 |
| `body` | JSON 格式请求体 |
| `extract` | 响应变量提取，例如 `{"token":"data.access_token"}` |
| `expected_status` | 预期 HTTP 状态码 |
| `expected_code` | 预期业务响应码 |
| `expected_message` | 预期响应 message |
| `expected_fields` | JSON 字段断言，例如 `{"data.status":"ISSUED"}` |
| `depends_on` | 依赖用例编号，用于多接口串联 |
| `description` | 用例说明 |

变量提取后，可以在后续用例中使用：

```json
{"Authorization": "Bearer ${token}"}
```

## 生成 Excel 模板

```powershell
python api_tests\tools\generate_insurance_cases_excel.py
```

注意：这个命令会覆盖 `api_tests\data\insurance_api_cases.xlsx`，只在需要重置模板时执行。

## 读取 dev-master 生成接口契约

这个命令会从 Git 中导出 `dev-master` 分支代码到临时目录，然后读取 Django 的 URL、View、Serializer，生成接口路径、请求字段、校验条件和响应字段。

```powershell
python api_tests\tools\generate_api_contract.py
```

输出文件：

```text
api_tests\reports\api_contract.json
```

可配置项：

```powershell
$env:BACKEND_BRANCH="dev-master"
$env:BACKEND_SOURCE_DIR="E:\aitesthub_backend"
python api_tests\tools\generate_api_contract.py
```

说明：

- `BACKEND_BRANCH`：默认读取 `dev-master`。
- `BACKEND_SOURCE_DIR`：如果你有一个单独的后端工作区，可以直接指定目录；不指定时会从 Git 临时导出 `dev-master`。

## 分析 dev-master 的 Git 变化

查看 `dev-master` 最新一次提交改了哪些接口相关文件：

```powershell
python api_tests\tools\inspect_git_api_changes.py
```

默认等价于对比：

```text
dev-master~1..dev-master
```

也可以指定对比范围：

```powershell
$env:BACKEND_DIFF_BASE="dev-master~3"
$env:BACKEND_DIFF_TARGET="dev-master"
python api_tests\tools\inspect_git_api_changes.py
```

这个工具会告诉你哪些变更可能需要补充 Excel 用例，例如路由变化、入参校验变化、业务逻辑变化、响应字段变化等。
