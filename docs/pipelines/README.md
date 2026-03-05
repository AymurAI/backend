# Pipelines
Language: **English** | [Español](../es/pipelines/README.md)

This section documents AymurAI backend production pipelines by workflow.

## Flow docs
- Anonymizer: [anonymizer/README.md](anonymizer/README.md)
- Datapublic: [datapublic/README.md](datapublic/README.md)

## Related model docs
- Models index: [../models/README.md](../models/README.md)
- Flair NER model card: [../models/flair-model-card.md](../models/flair-model-card.md)
- Decision model card: [../models/decision-model-card.md](../models/decision-model-card.md)

## Production pipeline sources
- Anonymizer config: `resources/pipelines/production/flair-anonymizer/pipeline.json`
- Datapublic config: `resources/pipelines/production/datapublic/pipeline.json`

## API mapping
- `POST /anonymizer/predict` -> `flair-anonymizer`
- `POST /datapublic/predict/{document_id}` -> `datapublic`

## Related docs
- API reference: [../api/README.md](../api/README.md)
- Internal database: [../database/README.md](../database/README.md)
