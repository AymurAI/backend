# Models
Language: **English** | [Español](../es/models/README.md)

This section documents the individual models used by the backend.

## Available model docs
- Anonymizer NER model card: [anonymizer-model-card.md](anonymizer-model-card.md)
- Flair NER: [flair-model-card.md](flair-model-card.md)
- Decision classifier: [decision-model-card.md](decision-model-card.md)

## Current production usage
- `flair-anonymizer` uses the anonymizer NER model card documented here.
- `datapublic` uses the Flair NER model, the decision classifier, and multilingual sentence-transformer encoders for embedding-based subcategorization.

## Related docs
- Documentation index: [../README.md](../README.md)
- Pipelines index: [../pipelines/README.md](../pipelines/README.md)
- Anonymizer flow: [../pipelines/anonymizer/README.md](../pipelines/anonymizer/README.md)
- Datapublic flow: [../pipelines/datapublic/README.md](../pipelines/datapublic/README.md)
