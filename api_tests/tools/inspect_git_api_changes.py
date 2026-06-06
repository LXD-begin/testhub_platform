import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from api_tests.config import BACKEND_DIFF_BASE, BACKEND_DIFF_TARGET  # noqa: E402


API_RELATED_RULES = {
    'apps/insurance/urls.py': '路由变化：检查是否新增、删除或修改接口路径，并同步 Excel 用例。',
    'apps/insurance/views.py': '视图变化：检查状态码、统一响应结构、鉴权、缓存和异常逻辑。',
    'apps/insurance/serializers.py': '序列化器变化：检查入参字段、必填项、枚举、长度、金额、日期等校验。',
    'apps/insurance/services.py': '业务逻辑变化：补充正流程、业务异常流程和多接口串联用例。',
    'apps/insurance/models.py': '模型变化：检查数据字段、状态枚举、响应字段和测试数据准备。',
    'apps/insurance/tokens.py': '鉴权变化：补充 token 获取、缺少 token、非法 token、过期 token 等用例。',
    'apps/insurance/cache.py': '缓存变化：补充缓存写入、缓存命中、缓存更新和缓存失效验证。',
}


def run_git(args):
    result = subprocess.run(
        ['git', *args],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f'Git 命令执行失败: git {" ".join(args)}\n{result.stderr}')
    return result.stdout


def git_changed_files():
    output = run_git(['diff', '--name-status', BACKEND_DIFF_BASE, BACKEND_DIFF_TARGET])
    changed = []
    for line in output.splitlines():
        if not line.strip():
            continue
        parts = line.split('\t')
        status = parts[0]
        path = parts[-1]
        changed.append((status, path))
    return changed


def inspect():
    changed = git_changed_files()
    print(f'后端分支变化范围: {BACKEND_DIFF_BASE}..{BACKEND_DIFF_TARGET}')
    print('\n本次后端变更文件:')
    if not changed:
        print('- 没有发现变更')
        return

    for status, path in changed:
        print(f'- {status} {path}')

    print('\n接口自动化影响分析:')
    matched = False
    changed_paths = {path for _, path in changed}
    for file, suggestion in API_RELATED_RULES.items():
        if file in changed_paths:
            matched = True
            print(f'- {file}: {suggestion}')

    if any(path.startswith('apps/insurance/migrations/') for path in changed_paths):
        matched = True
        print('- apps/insurance/migrations/: 数据库结构或初始化数据变化，请检查测试数据准备和断言字段。')

    if any(path.startswith('docs/') for path in changed_paths):
        matched = True
        print('- docs/: 接口文档变化，请检查 Excel 用例描述、字段含义和断言是否需要同步。')

    if not matched:
        print('- 没有发现保险接口核心代码变化，通常不需要新增接口用例。')

    print('\n建议执行:')
    print('1. python api_tests\\tools\\generate_api_contract.py')
    print('2. 按上面的影响分析补充或修改 api_tests\\data\\insurance_api_cases.xlsx')
    print('3. pytest')
    print('4. allure serve api_tests\\reports\\allure-results')


if __name__ == '__main__':
    inspect()
