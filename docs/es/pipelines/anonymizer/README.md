# Pipeline de Anonymizer
Idioma: [English](../../../pipelines/anonymizer/README.md) | **Español**

Referencia técnica orientada al flujo de anonimización.

## Alcance
Este flujo extrae entidades del texto judicial y compila documentos anonimizados.

## Diagrama
![Diagrama del pipeline de anonymizer](../../../pipelines/anonymizer/pipeline.png)

Fuente editable: [../../../pipelines/anonymizer/pipeline.excalidraw](../../../pipelines/anonymizer/pipeline.excalidraw)

## Entrypoints de runtime
- `POST /api/misc/document-extract`
- `POST /api/anonymizer/predict`
- `POST /api/anonymizer/disambiguate`
- `POST /api/anonymizer/validation`
- `POST /api/anonymizer/anonymize-document`

## Flujo paso a paso
1. Extracción de texto (`/api/misc/document-extract`) divide el documento fuente en párrafos normalizados.
2. Predicción (`/api/anonymizer/predict`) ejecuta NER por párrafo.
3. Desambiguación (`/api/anonymizer/disambiguate`) asigna IDs canónicos y metadatos efectivos para la desambiguación/anonimización.
4. Revisión manual en UI para editar etiquetas/políticas.
5. Compilación (`/api/anonymizer/anonymize-document`) aplica reemplazos preservando el formato de origen: una entrada PDF devuelve PDF y una entrada DOCX se exporta como ODT.

## Componentes técnicos

### Configuración del pipeline
- Fuente: `resources/pipelines/production/flair-anonymizer/pipeline.json`
- Preprocesamiento:
  - `aymurai.models.flair.utils.FlairTextNormalize`
- Modelo:
  - `aymurai.models.flair.core.FlairModel`
  - base model path: `aymurai/anonymizer-beto-cased-flair`
- Postprocesamiento:
  - `aymurai.transforms.anonymization_postprocess.core.AnonymizationEntityCleaner`
  - `aymurai.transforms.datetime_formatter.core.DatetimeFormatter`

### Contratos de API usados por este flujo
- `DocumentInformation`
- `DocumentAnnotations`
- `LabelPolicy`
- `RenderPolicy`
- `EntityAttributes` (en particular: `canonical_entity_id`, `aymurai_label_instance`, `aymurai_disambiguation`, `aymurai_anonymize`)

### Módulos backend relevantes
- Router: `aymurai/api/endpoints/routers/anonymizer/anonymizer.py`
- Render/anonymize: `aymurai/text/anonymization/docx.py` and `aymurai/text/anonymization/pdf.py`
- Desambiguación canónica: `aymurai/utils/entity_disambiguation/`

## Persistencia (DB)
Tablas usadas por este flujo:
- `anonymization_paragraph`
- `anonymization_document`
- `anonymization_document_paragraph`

## Notas
- La anonimización de PDF redacta el texto en el documento y preserva el layout no afectado, las anotaciones, los metadatos y el watermark.
- La anonimización de DOCX procesa reemplazos antes de convertir el resultado a ODT.
- Las políticas por label se mergean desde entorno y request.
- `render_policy` controla el comportamiento de sufijos (`auto`, `always`, `never`).

## Documentación relacionada
- Índice de pipelines: [../README.md](../README.md)
- Entidades de anonymizer: [../../entities/anonymizer/README.md](../../entities/anonymizer/README.md)
- Model card de anonymizer: [../../models/anonymizer-model-card.md](../../models/anonymizer-model-card.md)
- Referencia API: [../../api/README.md](../../api/README.md)
- Base interna: [../../database/README.md](../../database/README.md)
