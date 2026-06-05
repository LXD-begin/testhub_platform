# AGENTS.md

This repository is a minimal Django backend starter.

## Scope

- Keep the project backend-only.
- Keep the framework minimal.
- Do not restore old business apps, automation testing modules, Allure files, frontend code, Celery, Channels, or historical APIs unless explicitly requested.

## Common Commands

```bash
.venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
python manage.py check
```

## Structure

- `backend/`: Django project configuration
- `apps/`: package for future Django apps
- `manage.py`: Django management entrypoint

## Development Notes

New APIs should be created from scratch in new Django apps and wired into `backend/urls.py`.
