# NEXLINK PostgreSQL migrations

These SQL files are the schema source used by the current Docker development stack.

PostgreSQL executes them in filename order when a fresh database volume is initialized.

```text
001_initial_schema.sql
002_enrollment_and_metrics.sql
003_python_backend_schema.sql
```

The FastAPI application intentionally does not call `Base.metadata.create_all()` at startup. This prevents runtime code from silently changing a production schema.

For a clean local database:

```bash
docker compose down -v
docker compose up -d --build
```
