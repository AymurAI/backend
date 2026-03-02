# Internal Database
Language: **English** | [Español](../es/database/README.md)

This document describes the internal persistence used by the API runtime.

## Engine and Migrations
- ORM: `SQLModel` (`sqlalchemy` backend)
- Migration tool: Alembic
- Runtime setting: `SQLALCHEMY_DATABASE_URI`
- Default DB URI: `sqlite:////resources/cache/sqlite/database.db`
- Startup behavior:
  1. API checks DB connectivity.
  2. If SQLite file does not exist, it creates parent directories.
  3. API runs `alembic upgrade head` on startup.

Related code:
- `aymurai/settings.py`
- `aymurai/api/startup/database.py`
- `aymurai/api/main.py`
- `aymurai/database/versions/13f78d08e925_create_database.py`

## ER Diagram
![Database ER diagram](schema.png)

Editable source: [`schema.mmd`](schema.mmd)

## Tables

### `anonymization_document`
| Column | Type | Nullable | Notes |
|---|---|---|---|
| `id` | `UUID` | no | Primary key |
| `created_at` | `DATETIME` | no | Server default `CURRENT_TIMESTAMP` |
| `updated_at` | `DATETIME` | yes | Updated on row changes |
| `name` | `TEXT` | no | Original filename |

### `anonymization_paragraph`
| Column | Type | Nullable | Notes |
|---|---|---|---|
| `id` | `UUID` | no | Primary key, derived from paragraph text hash |
| `text` | `TEXT` | no | Normalized paragraph text |
| `prediction` | `JSON` | yes | Model predictions (`list[DocLabel]`) |
| `validation` | `JSON` | yes | Manual labels (`list[DocLabel]`) |
| `created_at` | `DATETIME` | no | Server default `CURRENT_TIMESTAMP` |
| `updated_at` | `DATETIME` | yes | Updated on row changes |

### `anonymization_document_paragraph`
| Column | Type | Nullable | Notes |
|---|---|---|---|
| `id` | `UUID` | no | Link row identifier |
| `document_id` | `UUID` | no | FK -> `anonymization_document.id` |
| `paragraph_id` | `UUID` | no | FK -> `anonymization_paragraph.id` |
| `order` | `INTEGER` | yes | Paragraph order in source document |

Primary key is composite over `id`, `document_id`, `paragraph_id`.

### `datapublic_document`
| Column | Type | Nullable | Notes |
|---|---|---|---|
| `id` | `UUID` | no | Primary key (document identifier) |
| `prediction` | `JSON` | yes | Reserved document-level prediction payload; not written by the current public router |
| `validation` | `JSON` | yes | Document-level validation payload |
| `created_at` | `DATETIME` | no | Server default `CURRENT_TIMESTAMP` |
| `updated_at` | `DATETIME` | yes | Updated on row changes |

### `datapublic_paragraph`
| Column | Type | Nullable | Notes |
|---|---|---|---|
| `id` | `UUID` | no | Primary key, derived from paragraph text hash |
| `text` | `TEXT` | no | Normalized paragraph text |
| `prediction` | `JSON` | yes | Model predictions (`list[DocLabel]`) |
| `validation` | `JSON` | yes | Reserved for paragraph-level validation; public route is currently commented legacy logic |
| `created_at` | `DATETIME` | no | Server default `CURRENT_TIMESTAMP` |
| `updated_at` | `DATETIME` | yes | Updated on row changes |

### `datapublic_document_paragraph`
| Column | Type | Nullable | Notes |
|---|---|---|---|
| `id` | `UUID` | no | Link row identifier |
| `document_id` | `UUID` | no | FK -> `datapublic_document.id` |
| `paragraph_id` | `UUID` | no | FK -> `datapublic_paragraph.id` |
| `order` | `INTEGER` | yes | Paragraph order in source document |

Primary key is composite over `id`, `document_id`, `paragraph_id`.

## Endpoint to Persistence Mapping

### Anonymizer
- `POST /anonymizer/predict`
  - Reads `anonymization_paragraph` by paragraph UUID.
  - Writes `anonymization_paragraph.prediction` when cache is enabled.
- `POST /anonymizer/disambiguate`
  - Writes disambiguated predictions to `anonymization_paragraph.prediction`.
- `POST /anonymizer/validation`
  - Reads `anonymization_paragraph.validation`.
- `POST /anonymizer/anonymize-document`
  - Writes `anonymization_paragraph.validation`.
  - Creates `anonymization_document` keyed by uploaded file content hash.
  - Creates link rows in `anonymization_document_paragraph`.

### Data-public
- `POST /datapublic/predict/{document_id}`
  - Uses caller-provided `document_id` as the document primary key.
  - Ensures `datapublic_document` exists when `use_cache=true`.
  - Writes `datapublic_paragraph.prediction` when `use_cache=true`.
  - Writes link row in `datapublic_document_paragraph` when `use_cache=true`.
- `GET /datapublic/validation/document/{document_id}`
  - Reads `datapublic_document.validation`.
- `POST /datapublic/validation/document/{document_id}`
  - Upserts `datapublic_document.validation`.

## Legacy Note
Route modules for dataset CRUD (`/datapublic/dataset/*`) exist in code but are not mounted in the public router. Do not treat them as active public API until exposed in `core.router`.
