# Phase 7 Complete — Database & Persistence

**Date:** 2026-03-02

## What Was Built

### Database Layer (`app/db/__init__.py`)
- Async SQLAlchemy engine (`create_async_engine`) using `settings.DATABASE_URL`
- `AsyncSessionLocal` session factory (`async_sessionmaker`, `expire_on_commit=False`)
- `Base` (`DeclarativeBase`) imported by all ORM models
- `get_db()` FastAPI dependency — yields a session, auto-commits on success, rolls back on error
- Connection pooling via `pool_size`, `max_overflow`, `pool_pre_ping`

### Document ORM Model (`app/models/document.py`)
SQLAlchemy 2.0 declarative-style model with `Mapped[]` annotations.

**Table: `documents`**

| Column | Type | Notes |
|--------|------|-------|
| id | BIGINT PK | Autoincrement — real DB id passed to Celery |
| public_id | VARCHAR(36) UNIQUE | UUID for external references |
| filename / original_filename | VARCHAR(255) | Stored name + user's original name |
| file_path | TEXT | Absolute path on disk |
| file_type | VARCHAR(50) | pdf / docx / txt / html / md |
| file_size | BIGINT | Bytes |
| status | VARCHAR(50) | pending / processing / completed / failed |
| chunk_count | INTEGER nullable | Set after Celery task completes |
| embedding_model | VARCHAR(255) nullable | Set after Celery task completes |
| qdrant_collection | VARCHAR(255) | Which Qdrant collection |
| doc_metadata | JSONB nullable | Extracted document metadata |
| error_message | TEXT nullable | Set if task fails |
| created_at / updated_at | TIMESTAMPTZ | Auto-managed |

Indexes: `idx_documents_status`, `idx_documents_created_at`

`DocumentStatus` string enum: `pending`, `processing`, `completed`, `failed`

### Alembic Setup
- `alembic.ini` — root config, UTC timestamps, log config
- `alembic/env.py` — reads `settings.database_url_sync`, imports `Base.metadata` + all models; supports offline + online migrations
- `alembic/script.py.mako` — standard migration template
- `alembic/versions/0001_create_documents_table.py` — creates `documents` table + indexes; includes `downgrade()`

Apply migrations: `make db-migrate` (runs `alembic upgrade head`)

### Document Routes — All Stubs Implemented (`app/api/routes/documents.py`)

| Route | Before | After |
|-------|--------|-------|
| `POST /documents/upload` | Used hash-based numeric ID | Creates DB record first, passes real `doc.id` to Celery |
| `GET /documents/{id}` | 501 stub | `db.get(Document, id)` → 404 or `DocumentResponse` |
| `GET /documents/` | 501 stub | Paginated query with status/file_type filters |
| `DELETE /documents/{id}` | 501 stub | Deletes from DB + Qdrant + disk |
| `GET /documents/stats/overview` | 501 stub | Aggregate SQL (count by status/type, total chunks, total size) |
| `POST /documents/search` | Hardcoded filenames | Resolves real filenames from DB |
| `POST /documents/query` | Hardcoded filenames | Resolves real filenames from DB |

### Celery Task DB Integration (`app/tasks/document_tasks.py`)
Event loop created at task start (moved from mid-task). Three DB status updates added:
1. **Before Step 1** — status → `processing`
2. **After Step 4** — status → `completed`, sets `chunk_count` + `embedding_model`
3. **In except block** — status → `failed`, sets `error_message` (best-effort, won't shadow original exception)

### Schema Fix
`DocumentResponse.chunk_count` changed from `int` to `Optional[int] = None` (column is nullable).
`DocumentResponse.metadata` uses `validation_alias="doc_metadata"` so pydantic reads the ORM column name correctly while keeping `metadata` as the JSON field name.

## Files Created

| File | Purpose |
|------|---------|
| `app/db/__init__.py` | Engine, session factory, Base, get_db() |
| `app/models/document.py` | Document ORM model + DocumentStatus enum |
| `app/models/__init__.py` | Exports Base, Document, DocumentStatus |
| `alembic.ini` | Alembic configuration |
| `alembic/env.py` | Async-aware migration environment |
| `alembic/script.py.mako` | Migration template |
| `alembic/versions/0001_create_documents_table.py` | Initial migration |
| `tests/unit/test_document_model.py` | 10 unit tests |

## Files Modified

| File | Change |
|------|--------|
| `app/api/routes/documents.py` | All stubs implemented, upload uses real DB id |
| `app/tasks/document_tasks.py` | DB status updates at 3 lifecycle points |
| `app/schemas/document.py` | `chunk_count` Optional, `metadata` validation_alias |

## Test Results

```
162 passed in 6.75s
```

New tests in `tests/unit/test_document_model.py` (10 tests):
- DocumentStatus enum values and string comparison
- Document model instantiation and repr
- Optional fields default to None
- DocumentResponse.model_validate() from ORM object
- Schema handles pending document with null chunk_count
- _update_db_status updates fields and calls commit
- _update_db_status handles missing document gracefully
- _update_db_status sets error_message on failure

## Next Phase

**Phase 8 — Testing & Quality Assurance**: write comprehensive unit + integration tests, ensure CI coverage.
