# CLAUDE.md

This repository branch is an API automation testing project.

## Scope

- Keep this branch independent from the Django backend source code.
- Do not add `apps/`, `backend/`, `manage.py`, Django migrations, Redis scripts, or backend runtime configuration to this branch.
- Read backend interface code and Git changes from the `dev-master` branch.
- Keep API cases in Excel under `api_tests/data/`.
- Keep generated Allure runtime files out of Git.

## Common Commands

```bash
.venv\Scripts\activate
pip install -r requirements.txt
pytest
python api_tests\tools\inspect_git_api_changes.py
python api_tests\tools\generate_api_contract.py
```

## Structure

- `api_tests/common/`: shared test framework helpers
- `api_tests/data/`: Excel API test cases
- `api_tests/testcases/`: pytest test entry points
- `api_tests/tools/`: contract generation and Git-change analysis tools
- `api_tests/reports/`: generated contracts, logs, and Allure report output

## Development Notes

Backend code belongs on `dev-master`. This branch should only maintain the software-testing framework and test assets.
