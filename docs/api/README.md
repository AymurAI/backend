# API Reference
Language: **English** | [Español](../es/api/README.md)

This document describes the currently mounted public API in `aymurai/api/main.py` + `aymurai/api/core.py`.

## Base URL and OpenAPI
- Local base URL: `http://localhost:8899`
- Swagger UI: `http://localhost:8899/docs`
- OpenAPI JSON: `http://localhost:8899/openapi.json`

## Public Endpoints (Mounted)

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/server/healthcheck` | Service liveness check |
| `GET` | `/server/stats/summary` | Runtime CPU/memory stats |
| `POST` | `/document-extract` | Deprecated alias of `/misc/document-extract` |
| `POST` | `/misc/document-extract` | Extract normalized paragraphs from uploaded document |
| `POST` | `/anonymizer/predict` | NER prediction for a paragraph |
| `POST` | `/anonymizer/disambiguate` | Canonical entity disambiguation + policy merge |
| `POST` | `/anonymizer/validation` | Fetch paragraph-level manual validation |
| `POST` | `/anonymizer/anonymize-document` | Compile and export anonymized document |
| `POST` | `/datapublic/predict/{document_id}` | Predict entities for data-public flow |
| `GET` | `/datapublic/validation/document/{document_id}` | Read document-level validation |
| `POST` | `/datapublic/validation/document/{document_id}` | Save document-level validation |
| `POST` | `/convert/pdf/odt` | Convert PDF to ODT |
| `POST` | `/convert/pdf/docx` | Convert PDF to DOCX |
| `POST` | `/convert/docx/odt` | Convert DOCX to ODT |
| `POST` | `/convert/docx/pdf` | Convert DOCX to PDF |
| `POST` | `/convert/odt/pdf` | Convert ODT to PDF |
| `POST` | `/convert/odt/docx` | Convert ODT to DOCX |

## Core Data Contracts

Note: the JSON snippets below are minimal valid examples. Real payloads may include additional fields depending on the endpoint and processing stage.

### `TextRequest`
```json
{
  "text": "Acusado: Ramiro Marrón DNI 34.555.666."
}
```

### `EntityAttributes` (relevant fields)
```json
{
  "aymurai_label": "PER",
  "aymurai_label_subclass": [],
  "aymurai_method": "flair",
  "aymurai_score": 0.97,
  "canonical_entity_id": "a3f8b60f-8e7e-4c8b-9de2-ec8dd3f44c12",
  "aymurai_label_instance": 1,
  "aymurai_disambiguation": "fuzzy",
  "aymurai_anonymize": true
}
```

### `DocLabel`
```json
{
  "text": "Ramiro Marrón",
  "start_char": 9,
  "end_char": 22,
  "attrs": {
    "aymurai_label": "PER"
  }
}
```

### `DocumentInformation`
```json
{
  "document": "Acusado: Ramiro Marrón DNI 34.555.666.",
  "labels": [
    {
      "text": "Ramiro Marrón",
      "start_char": 9,
      "end_char": 22,
      "attrs": {
        "aymurai_label": "PER"
      }
    }
  ]
}
```

### `LabelPolicy`
```json
{
  "anonymize": true,
  "disambiguation": "fuzzy",
  "use_subclass_when_available": true
}
```

### `RenderPolicy`
```json
{
  "suffix_mode": "auto",
  "suffix_threshold": 1
}
```

### `DocumentAnnotations`
```json
{
  "data": [
    {
      "document": "...",
      "labels": []
    }
  ],
  "label_policies": {
    "PER": {
      "anonymize": true,
      "disambiguation": "fuzzy",
      "use_subclass_when_available": false
    }
  },
  "render_policy": {
    "suffix_mode": "auto",
    "suffix_threshold": 1
  }
}
```

## Endpoint Details and Examples

### Server

#### `GET /server/healthcheck`
- Response `200`:

```json
{"status": "ok"}
```

```bash
curl -s http://localhost:8899/server/healthcheck
```

#### `GET /server/stats/summary`
- Response `200` (shape):

```json
{
  "is_docker": true,
  "cpu_core_limit": 4,
  "cpu_usage_percent": 0.0,
  "memory_limit_mb": 4096.0,
  "memory_usage_mb": 823.5
}
```

```bash
curl -s http://localhost:8899/server/stats/summary
```

### Document Extraction

#### `POST /misc/document-extract`
#### `POST /document-extract` (deprecated alias)
- Request: `multipart/form-data` with `file`
- Supported MIME types in extraction flow: DOCX, ODT, PDF
- Response `200`:

```json
{
  "document": ["Paragraph 1", "Paragraph 2"],
  "document_id": "f2b25507-cf88-5b11-8f2a-c0b6f940b7f8"
}
```

```bash
curl -s -X POST \
  -F "file=@/resources/data/sample/document-01.docx" \
  http://localhost:8899/misc/document-extract
```

Common errors:
- `504` extraction timeout
- `500` extractor/internal errors

### Anonymizer

#### `POST /anonymizer/predict`
- Request body: `TextRequest`
- Query param: `use_cache=true|false` (default `true`)
- Response `200`: `DocumentInformation`

```bash
curl -s -X POST "http://localhost:8899/anonymizer/predict?use_cache=true" \
  -H "Content-Type: application/json" \
  -d '{"text":"Acusado: Ramiro Marrón DNI 34.555.666."}'
```

#### `POST /anonymizer/disambiguate`
- Request body:

```json
{
  "paragraphs": [
    {
      "document": "Acusado: Ramiro Marrón DNI 34.555.666.",
      "labels": []
    }
  ],
  "label_policies": {
    "PER": {
      "anonymize": true,
      "disambiguation": "fuzzy",
      "use_subclass_when_available": false
    }
  }
}
```

- Response `200`: `DocumentAnnotations` (with `data` and effective `label_policies`)

```bash
curl -s -X POST http://localhost:8899/anonymizer/disambiguate \
  -H "Content-Type: application/json" \
  -d '{"paragraphs":[{"document":"Acusado: Ramiro Marrón DNI 34.555.666.","labels":[]}],"label_policies":{"PER":{"anonymize":true,"disambiguation":"fuzzy"}}}'
```

#### `POST /anonymizer/validation`
- Request body: `TextRequest`
- Response `200`: `list[DocLabel] | null`

```bash
curl -s -X POST http://localhost:8899/anonymizer/validation \
  -H "Content-Type: application/json" \
  -d '{"text":"Acusado: Ramiro Marrón DNI 34.555.666."}'
```

#### `POST /anonymizer/anonymize-document`
- Request: `multipart/form-data`
  - `file`: original document (`.docx`, `.pdf`, `.odt`)
  - `annotations`: JSON string serialized from `DocumentAnnotations`
- Response `200`: binary anonymized `.odt` file

```bash
curl -X POST http://localhost:8899/anonymizer/anonymize-document \
  -F "file=@/resources/data/sample/document-01.docx" \
  -F 'annotations={"data":[{"document":"Acusado: Ramiro Marrón DNI 34.555.666.","labels":[]}],"label_policies":{"PER":{"anonymize":true,"disambiguation":"fuzzy"}},"render_policy":{"suffix_mode":"auto","suffix_threshold":1}}'
```

Common errors:
- `400` invalid form payload
- `500` conversion/anonymization failures

### Data-Public

#### `POST /datapublic/predict/{document_id}`
- Path param: `document_id` (`UUID5`)
- Request body: `TextRequest`
- Query param: `use_cache=true|false` (default `true`)
- Response `200`: `DocumentInformation`

```bash
curl -s -X POST "http://localhost:8899/datapublic/predict/7e6b6f35-2f29-58f7-9f8e-fd1d9026a6bc?use_cache=true" \
  -H "Content-Type: application/json" \
  -d '{"text":"Buenos Aires, 17 de noviembre de 2024"}'
```

#### `GET /datapublic/validation/document/{document_id}`
- Response `200`: object or `null`
- Response `404`: document not found

```bash
curl -s http://localhost:8899/datapublic/validation/document/7e6b6f35-2f29-58f7-9f8e-fd1d9026a6bc
```

#### `POST /datapublic/validation/document/{document_id}`
- Request body: free-form JSON object (stored as document-level validation)
- Response `200`: empty body

```bash
curl -s -X POST http://localhost:8899/datapublic/validation/document/7e6b6f35-2f29-58f7-9f8e-fd1d9026a6bc \
  -H "Content-Type: application/json" \
  -d '{"materia":"penal","violencia_de_genero":"si"}'
```

### Document Conversion

All conversion endpoints use `multipart/form-data` with a `file` field.

| Method | Path | Input | Output |
|---|---|---|---|
| `POST` | `/convert/pdf/odt` | `.pdf` | `.odt` |
| `POST` | `/convert/pdf/docx` | `.pdf` | `.docx` |
| `POST` | `/convert/docx/odt` | `.docx` | `.odt` |
| `POST` | `/convert/docx/pdf` | `.docx` | `.pdf` |
| `POST` | `/convert/odt/pdf` | `.odt` | `.pdf` |
| `POST` | `/convert/odt/docx` | `.odt` | `.docx` |

For PDF input endpoints, optional query param:
- `backend=libreoffice|pandoc` (default: `libreoffice`)

Example:

```bash
curl -X POST "http://localhost:8899/convert/pdf/docx?backend=libreoffice" \
  -F "file=@input.pdf" -o output.docx
```

Common errors:
- `400` unsupported input extension
- `500` conversion tool failure

## Legacy / Not Public (Not Mounted)
The following route modules exist in code but are not included in `core.router` at runtime:

- `aymurai/api/endpoints/routers/datapublic/dataset.py`
  - includes `/datapublic/dataset/*` CRUD/batch routes, but router is not mounted.
- `aymurai/api/endpoints/routers/anonymizer/database.py`
  - `/anonymizer/database/*` routes exist, include is commented out.
- `aymurai/api/endpoints/routers/database/*`
  - additional DB admin routes exist, but no mounting in `core.router`.

Treat these as legacy/internal code paths until explicitly exposed in the public router.
