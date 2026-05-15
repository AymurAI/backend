# Referencia de API
Idioma: [English](../../api/README.md) | **Español**

Este documento describe la API pública actualmente montada en `aymurai/api/main.py` + `aymurai/api/core.py`.

## Base URL y OpenAPI
- Base local: `http://localhost:8899`
- Swagger UI: `http://localhost:8899/api/docs`
- OpenAPI JSON: `http://localhost:8899/api/openapi.json`

## Endpoints públicos (montados)

| Método | Path | Propósito |
|---|---|---|
| `GET` | `/api/server/healthcheck` | Liveness del servicio |
| `GET` | `/api/server/stats/summary` | Métricas de CPU/memoria |
| `POST` | `/api/document-extract` | Alias deprecado de `/api/misc/document-extract` |
| `POST` | `/api/misc/document-extract` | Extrae párrafos normalizados de un documento |
| `POST` | `/api/anonymizer/predict` | Predicción NER por párrafo |
| `POST` | `/api/anonymizer/disambiguate` | Desambiguación canónica + merge de políticas |
| `POST` | `/api/anonymizer/validation` | Obtiene validación manual por párrafo |
| `POST` | `/api/anonymizer/anonymize-document` | Compila y exporta documento anonimizado |
| `POST` | `/api/datapublic/predict/{document_id}` | Predicción para flujo data-public |
| `GET` | `/api/datapublic/validation/document/{document_id}` | Lee validación a nivel documento |
| `POST` | `/api/datapublic/validation/document/{document_id}` | Guarda validación a nivel documento |
| `POST` | `/api/convert/pdf/odt` | Convierte PDF a ODT |
| `POST` | `/api/convert/pdf/docx` | Convierte PDF a DOCX |
| `POST` | `/api/convert/docx/odt` | Convierte DOCX a ODT |
| `POST` | `/api/convert/docx/pdf` | Convierte DOCX a PDF |
| `POST` | `/api/convert/odt/pdf` | Convierte ODT a PDF |
| `POST` | `/api/convert/odt/docx` | Convierte ODT a DOCX |

## Contratos de datos principales

Nota: los snippets JSON de abajo son ejemplos mínimos válidos. Los payloads reales pueden incluir campos adicionales según el endpoint y la etapa de procesamiento.

### `TextRequest`
```json
{
  "text": "Acusado: Ramiro Marrón DNI 34.555.666."
}
```

### `EntityAttributes` (campos relevantes)
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

## Detalle de endpoints y ejemplos

### Server

#### `GET /server/healthcheck`
- Respuesta `200`:

```json
{"status": "ok"}
```

```bash
curl -s http://localhost:8899/api/server/healthcheck
```

#### `GET /server/stats/summary`
- Respuesta `200` (forma):

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
curl -s http://localhost:8899/api/server/stats/summary
```

### Extracción de documentos

#### `POST /misc/document-extract`
#### `POST /document-extract` (alias deprecado)
- Request: `multipart/form-data` con `file`
- MIME types soportados en extracción: DOCX, ODT, PDF
- Respuesta `200`:

```json
{
  "document": ["Párrafo 1", "Párrafo 2"],
  "document_id": "f2b25507-cf88-5b11-8f2a-c0b6f940b7f8"
}
```

```bash
curl -s -X POST \
  -F "file=@/resources/data/sample/document-01.docx" \
  http://localhost:8899/api/misc/document-extract
```

Errores comunes:
- `504` timeout de extracción
- `500` errores del extractor/internos

### Anonymizer

#### `POST /anonymizer/predict`
- Body: `TextRequest`
- Query param: `use_cache=true|false` (default `true`)
- Respuesta `200`: `DocumentInformation`

```bash
curl -s -X POST "http://localhost:8899/api/anonymizer/predict?use_cache=true" \
  -H "Content-Type: application/json" \
  -d '{"text":"Acusado: Ramiro Marrón DNI 34.555.666."}'
```

#### `POST /anonymizer/disambiguate`
- Body request:

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

- Respuesta `200`: `DocumentAnnotations` (incluye `data` y `label_policies` efectivas)

```bash
curl -s -X POST http://localhost:8899/api/anonymizer/disambiguate \
  -H "Content-Type: application/json" \
  -d '{"paragraphs":[{"document":"Acusado: Ramiro Marrón DNI 34.555.666.","labels":[]}],"label_policies":{"PER":{"anonymize":true,"disambiguation":"fuzzy"}}}'
```

#### `POST /anonymizer/validation`
- Body: `TextRequest`
- Respuesta `200`: `list[DocLabel] | null`

```bash
curl -s -X POST http://localhost:8899/api/anonymizer/validation \
  -H "Content-Type: application/json" \
  -d '{"text":"Acusado: Ramiro Marrón DNI 34.555.666."}'
```

#### `POST /anonymizer/anonymize-document`
- Request: `multipart/form-data`
  - `file`: documento original (`.docx`, `.pdf`, `.odt`)
  - `annotations`: string JSON serializado de `DocumentAnnotations`
- Respuesta `200`: archivo `.odt` anonimizado (binario)

```bash
curl -X POST http://localhost:8899/api/anonymizer/anonymize-document \
  -F "file=@/resources/data/sample/document-01.docx" \
  -F 'annotations={"data":[{"document":"Acusado: Ramiro Marrón DNI 34.555.666.","labels":[]}],"label_policies":{"PER":{"anonymize":true,"disambiguation":"fuzzy"}},"render_policy":{"suffix_mode":"auto","suffix_threshold":1}}'
```

Errores comunes:
- `400` payload multipart inválido
- `500` errores de anonimización/conversión

### Data-Public

#### `POST /datapublic/predict/{document_id}`
- Path param: `document_id` (`UUID5`)
- Body: `TextRequest`
- Query param: `use_cache=true|false` (default `true`)
- Respuesta `200`: `DocumentInformation`

```bash
curl -s -X POST "http://localhost:8899/api/datapublic/predict/7e6b6f35-2f29-58f7-9f8e-fd1d9026a6bc?use_cache=true" \
  -H "Content-Type: application/json" \
  -d '{"text":"Buenos Aires, 17 de noviembre de 2024"}'
```

#### `GET /datapublic/validation/document/{document_id}`
- Respuesta `200`: objeto o `null`
- Respuesta `404`: documento inexistente

```bash
curl -s http://localhost:8899/api/datapublic/validation/document/7e6b6f35-2f29-58f7-9f8e-fd1d9026a6bc
```

#### `POST /datapublic/validation/document/{document_id}`
- Body: objeto JSON libre (se persiste como validación a nivel documento)
- Respuesta `200`: body vacío

```bash
curl -s -X POST http://localhost:8899/api/datapublic/validation/document/7e6b6f35-2f29-58f7-9f8e-fd1d9026a6bc \
  -H "Content-Type: application/json" \
  -d '{"materia":"penal","violencia_de_genero":"si"}'
```

### Conversión de documentos

Todos los endpoints de conversión usan `multipart/form-data` con campo `file`.

| Método | Path | Input | Output |
|---|---|---|---|
| `POST` | `/api/convert/pdf/odt` | `.pdf` | `.odt` |
| `POST` | `/api/convert/pdf/docx` | `.pdf` | `.docx` |
| `POST` | `/api/convert/docx/odt` | `.docx` | `.odt` |
| `POST` | `/api/convert/docx/pdf` | `.docx` | `.pdf` |
| `POST` | `/api/convert/odt/pdf` | `.odt` | `.pdf` |
| `POST` | `/api/convert/odt/docx` | `.odt` | `.docx` |

Para endpoints con input PDF, query param opcional:
- `backend=libreoffice|pandoc` (default: `libreoffice`)

Ejemplo:

```bash
curl -X POST "http://localhost:8899/convert/pdf/docx?backend=libreoffice" \
  -F "file=@input.pdf" -o output.docx
```

Errores comunes:
- `400` extensión de entrada no soportada
- `500` falla de herramienta de conversión

## Legacy / no pública (no montada)
Las siguientes rutas existen en código pero no están incluidas en `core.router` en runtime:

- `aymurai/api/endpoints/routers/datapublic/dataset.py`
  - define `/api/datapublic/dataset/*`, pero ese router no está montado.
- `aymurai/api/endpoints/routers/anonymizer/database.py`
  - define `/api/anonymizer/database/*`, pero su include está comentado.
- `aymurai/api/endpoints/routers/database/*`
  - rutas administrativas de DB, sin montaje en `core.router`.

Estas rutas deben tratarse como caminos internos/legacy hasta su exposición explícita.
