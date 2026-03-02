# Pipeline de Datapublic
Idioma: [English](../../../pipelines/datapublic/README.md) | **Español**

Referencia técnica orientada al flujo de extracción de información del datapublic.

## Alcance
Este flujo extrae información estructurada a partir de párrafos y soporta persistencia de validación a nivel documento para curación de dataset público.

## Diagrama
![Diagrama del pipeline de datapublic](../../../pipelines/datapublic/pipeline.png)

## Entrypoints de runtime
- `POST /misc/document-extract`
- `POST /datapublic/predict/{document_id}`
- `GET /datapublic/validation/document/{document_id}`
- `POST /datapublic/validation/document/{document_id}`

## Flujo paso a paso
1. Extracción de texto (`/misc/document-extract`) divide el documento fuente en párrafos normalizados.
2. Predicción (`/datapublic/predict/{document_id}`) procesa cada párrafo y devuelve predicciones; la persistencia en caché ocurre solo cuando `use_cache=true` (default).
3. Revisión en UI agrega la salida validada a nivel documento.
4. Los endpoints de validación leen/escriben payload de validación de documento.

## Componentes técnicos

### Configuración del pipeline
- Fuente: `resources/pipelines/production/full-paragraph/pipeline.json`
- Preprocesamiento:
  - `aymurai.models.flair.utils.FlairTextNormalize`
- Modelos:
  - `aymurai.models.flair.core.FlairModel` (`aymurai/flair-ner-spanish-judicial`)
  - `aymurai.models.decision.binregex.DecisionEmbeddingBagBinRegex` (`return_only_with_detalle=true` en producción)
- Postprocesamiento:
  - `aymurai.transforms.entity_subcategories.regex.RegexSubcategorizer`
  - `aymurai.transforms.datetime_formatter.core.DatetimeFormatter`
  - `aymurai.transforms.entity_subcategories.sentence_transformer.SentenceTransformerSubcategorizer` (4 instancias configuradas en producción para `CONDUCTA`, `CONDUCTA_DESCRIPCION`, `DETALLE` y `OBJETO_DE_LA_RESOLUCION`)
  - `aymurai.transforms.entity_subcategories.article.ArticleSubcategorizer`

### Algoritmos y procesamiento
- Extracción NER sobre párrafos judiciales.
- Clasificación/filtro de decisiones para relevancia, con gating en producción para que `DECISION` solo se emita cuando ya existe una entidad `DETALLE`.
- Subcategorización rule-based + embeddings.
- Normalización de fecha/hora y mapeo por artículo.

### Contratos de API usados por este flujo
- `TextRequest`
- `DocumentInformation`
- `DataPublicDocumentAnnotations` (payload libre de validación a nivel documento)

### Módulos backend relevantes
- Router: `aymurai/api/endpoints/routers/datapublic/datapublic.py`
- Carga de pipeline e inferencia: endpoint de predicción en `aymurai/api/endpoints/routers/datapublic/datapublic.py`.

## Persistencia (DB)
Tablas usadas por este flujo:
- `datapublic_paragraph`
- `datapublic_document`
- `datapublic_document_paragraph`

## Notas
- El directorio de pipeline en producción sigue llamándose `full-paragraph`.
- `document_id` es la clave de agrupamiento a nivel documento para asociar predicciones por párrafo y el payload de validación.
- La persistencia de validación es a nivel documento y acepta intencionalmente un objeto JSON libre.
- `GET /datapublic/validation/document/{document_id}` devuelve `404` cuando el documento no existe; `POST` crea o actualiza el payload de validación.
- El router público no monta actualmente `/datapublic/dataset/*`.
- La validación a nivel párrafo aparece en código como lógica legacy comentada y no forma parte del flujo público.

## Modelos usados por este flujo
- Flair NER: [../../models/flair-model-card.md](../../models/flair-model-card.md)
- Clasificador de decisiones: [../../models/decision-model-card.md](../../models/decision-model-card.md)

## Documentación relacionada
- Índice de pipelines: [../README.md](../README.md)
- Entidades de datapublic: [../../entities/datapublic/README.md](../../entities/datapublic/README.md)
- Referencia API: [../../api/README.md](../../api/README.md)
- Base interna: [../../database/README.md](../../database/README.md)
