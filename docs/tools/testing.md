# Tool Testing

Core no-database tests live in:

- `backend/tests/test_tool_registry_helpers.py`
- `backend/tests/test_tool_system.py`

Run focused tests:

```bash
cd backend
.venv/bin/python -m pytest tests/test_tool_registry_helpers.py tests/test_tool_system.py
```

Run the backend suite:

```bash
cd backend
.venv/bin/python -m pytest
```

The backend pytest config scopes collection to `tests/` so archived/manual scripts are not collected as tests. DB-backed tests skip when the local Postgres test database is unavailable.

Useful checks:

```bash
backend/.venv/bin/python -m ruff check backend/app/agents backend/app/api/v1/endpoints/tools.py backend/tests/test_tool_system.py
backend/.venv/bin/python -m ruff format --check backend/app/agents backend/app/api/v1/endpoints/tools.py backend/tests/test_tool_system.py
```
