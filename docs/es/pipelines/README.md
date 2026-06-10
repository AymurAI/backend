# Pipelines
Idioma: [English](../../pipelines/README.md) | **Español**

Esta sección documenta los pipelines de producción del backend por flujo.

## Documentación por flujo
- Anonymizer: [anonymizer/README.md](anonymizer/README.md)
- Datapublic: [datapublic/README.md](datapublic/README.md)

## Modelos relacionados
- Índice de modelos: [../models/README.md](../models/README.md)
- Model card de Flair NER: [../models/flair-model-card.md](../models/flair-model-card.md)
- Model card de Decision: [../models/decision-model-card.md](../models/decision-model-card.md)

## Fuentes de configuración en producción
- Config anonymizer: `resources/pipelines/production/flair-anonymizer/pipeline.json`
- Config datapublic: `resources/pipelines/production/datapublic/pipeline.json`

## Mapeo con API
- `POST /api/anonymizer/predict` -> `flair-anonymizer`
- `POST /api/datapublic/predict/{document_id}` -> `datapublic`

## Documentación relacionada
- Referencia API: [../api/README.md](../api/README.md)
- Base de datos interna: [../database/README.md](../database/README.md)
