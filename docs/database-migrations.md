# Database Migrations

The canonical migration system is `backend/alembic`. The older
`database/migrations` tree is retained only as historical reference and should
not be used for new schema changes.

## Supported Database

Use PostgreSQL 17 with both required extensions available:

- `pgcrypto`, used for `gen_random_uuid()`
- `vector`, used by pgvector `vector(3072)` embedding columns

For local development, start the bundled pgvector image:

```bash
docker compose up -d db
```

Or point `backend/.env` `DATABASE_URL` at another PostgreSQL 17 instance with
pgvector installed:

```bash
DATABASE_URL=postgresql+asyncpg://senorita:senorita@localhost:5433/senorita
```

## Fresh Database Setup

Run migrations from the backend directory:

```bash
cd backend
source .venv/bin/activate
alembic upgrade head
```

Do not call `Base.metadata.create_all()` to initialize production or
development databases. The FastAPI app expects migrations to have already been
applied.

## Existing Database Upgrade

Before changing an existing database:

1. Take a database backup.
2. Confirm which migration table the database uses:

```sql
SELECT version_num FROM alembic_version;
```

3. If the database is already managed by `backend/alembic`, run:

```bash
cd backend
alembic upgrade head
```

4. If the database was initialized with the historical `database/migrations`
tree or with SQLAlchemy `create_all()`, compare its schema against a fresh
`backend/alembic upgrade head` database, then stamp only after verification:

```bash
cd backend
alembic stamp b6a4df3e91c2
```

Use `stamp` only for databases whose schema is already present. It does not
create or repair tables.

## Regression Test

The migration regression tests create disposable databases and run real Alembic
commands:

```bash
cd backend
pytest tests/test_migrations.py -q
```

The tests skip when PostgreSQL is unreachable. If PostgreSQL is reachable but
pgvector is not installed, migration tests fail because that is not a supported
runtime database.
