# API Tests

`api_tests` 是接口自动化测试框架目录，和 Django 后端项目解耦。

## 核心能力

- 使用 Excel 管理接口用例。
- 使用 `pytest` 参数化执行每一行用例。
- 使用 `requests` 发送 HTTP 请求。
- 使用 `${变量名}` 支持多接口串联。
- 使用 `allure-pytest` 生成测试报告数据。
- 使用 `logging` 输出执行日志。
- 使用 Git 读取 `dev-master` 分支的后端接口变化。

## 常用命令

```powershell
# 执行测试
pytest

# 生成 Excel 用例模板
python api_tests\tools\generate_insurance_cases_excel.py

# 从 dev-master 生成接口契约
python api_tests\tools\generate_api_contract.py

# 分析 dev-master 最新提交对接口测试的影响
python api_tests\tools\inspect_git_api_changes.py

# 查看 Allure 报告
allure serve api_tests\reports\allure-results
```

## 重要环境变量

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `API_BASE_URL` | `http://127.0.0.1:8000` | 被测后端服务地址 |
| `API_CASE_FILE` | `api_tests\data\insurance_api_cases.xlsx` | Excel 用例文件 |
| `API_REQUEST_TIMEOUT` | `10` | 请求超时时间，单位秒 |
| `BACKEND_BRANCH` | `dev-master` | 读取接口契约的后端分支 |
| `BACKEND_SOURCE_DIR` | 空 | 可选，指定一个已检出的后端代码目录 |
| `BACKEND_DIFF_BASE` | `dev-master~1` | Git 变化分析的起点 |
| `BACKEND_DIFF_TARGET` | `dev-master` | Git 变化分析的终点 |

## Excel 串联示例

第一条用例从响应里提取 token：

```json
{"token": "data.access_token"}
```

后续用例在请求头里引用：

```json
{"Authorization": "Bearer ${token}"}
```
