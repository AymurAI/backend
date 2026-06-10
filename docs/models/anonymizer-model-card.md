---
license: mit
language:
- es
tags:
- flair
- token-classification
- sequence-tagger-model
- anonymization
- judicial-text
datasets:
- ArJuzPCyF10
metrics:
- precision
- recall
- f1-score
widget:
- text: 1. DECLARAR EXTINGUIDA LA ACCIÓN PENAL en este caso por cumplimiento de la suspensión del proceso a prueba, y SOBRESEER a EZEQUIEL CAMILO MARCONNI, DNI 11.222.333, en orden a los delitos de lesiones leves agravadas, amenazas simples y agravadas por el uso de armas.
library_name: flair
pipeline_tag: token-classification
---

Language: **English** | [Español](../es/models/anonymizer-model-card.md)

# Model Description

This model is the NER component used by the production `flair-anonymizer` pipeline.
It detects spans that should be anonymized in judicial documents before disambiguation, validation, and document rendering.

Following the Flair guidelines for NER training, the model was trained on top of [BETO embeddings](https://huggingface.co/dccuchile/bert-base-spanish-wwm-uncased), a Spanish BERT model, with a BiLSTM-CRF architecture.

This model was developed by [{ collective.ai }](https://collectiveai.io) as part of the [AymurAI](https://aymurai.info) project by [DataGenero](https://datagenero.org).

## Intended uses & limitations

AymurAI is intended to help address the lack of available data on gender-based violence (GBV) rulings in Latin America. In the anonymization workflow, the immediate purpose of this model is to identify sensitive spans in legal documents so they can be reviewed and replaced before downstream use.

AymurAI remains a domain-specific system. Its capabilities are limited to semi-automated anonymization, collection, and analysis of judicial data, and the output may be affected by annotation quality, document heterogeneity, OCR or extraction errors, and the availability of representative training data.

This model was trained on a closed dataset from an Argentine criminal court. That domain specificity improves performance on the target setting, but it also means the model may not transfer well to other jurisdictions, document styles, or legal cultures.

## Production behavior

In production, this model is loaded through `aymurai.models.flair.core.FlairModel` from:

- `resources/pipelines/production/flair-anonymizer/pipeline.json`
- model path: `aymurai/anonymizer-beto-cased-flair`

Its raw span predictions are then post-processed by:

- `aymurai.transforms.anonymization_postprocess.core.AnonymizationEntityCleaner`
- `aymurai.transforms.datetime_formatter.core.DatetimeFormatter`

Those predictions feed the rest of the anonymization flow:

1. `POST /api/anonymizer/predict` runs span extraction.
2. `POST /api/anonymizer/disambiguate` assigns canonical entity IDs and effective per-label metadata.
3. Manual review may edit labels, `label_policies`, and `render_policy`.
4. `POST /api/anonymizer/anonymize-document` applies replacements in the output document.

# Usage

## How to use the model in Flair

Requires **[Flair](https://github.com/flairNLP/flair/)**.
Install it with `pip install flair`.

```python
from flair.data import Sentence
from flair.models import SequenceTagger

tagger = SequenceTagger.load("aymurai/anonymizer-beto-cased-flair")

sentence = Sentence(
    "1. DECLARAR EXTINGUIDA LA ACCIÓN PENAL en este caso por cumplimiento "
    "de la suspensión del proceso a prueba, y SOBRESEER a EZEQUIEL CAMILO "
    "MARCONNI, DNI 11.222.333, en orden a los delitos de lesiones leves "
    "agravadas, amenazas simples y agravadas por el uso de armas."
)

tagger.predict(sentence)

for entity in sentence.get_spans("ner"):
    print(entity)
```

This yields output similar to:

```text
Span[22:25]: "EZEQUIEL CAMILO MARCONNI" -> PER (0.9541)
Span[27:28]: "11.222.333" -> DNI (1.0)
```

## Using the model in an AymurAI pipeline

```python
from aymurai.pipeline import AymurAIPipeline

pipeline = AymurAIPipeline.load("/resources/pipelines/production/flair-anonymizer")

item = {
    "path": "dummy",
    "data": {
        "doc.text": (
            "Acusado: Ramiro Marrón DNI 34.555.666. "
            "Fecha: 17 de noviembre de 2024."
        )
    },
}

processed = pipeline.preprocess([item])
processed = pipeline.predict_single(processed[0])
processed = pipeline.postprocess([processed])

print(processed[0]["predictions"]["entities"])
```

# Entities and metrics

## Description

Please refer to the anonymizer entities catalog ([en](../entities/anonymizer/README.md)|[es](../es/entities/anonymizer/README.md)).

## Data

The model was trained with a dataset of 535 legal rulings from an Argentine criminal court.

Due to the nature of the data (personal data, complaint characteristics, and victim protection), the documents are kept private.

## Metrics

The following per-label metrics come from the published Hugging Face card for this anonymizer model family and should be interpreted as model-level NER metrics, not end-to-end anonymization quality.

| label | precision | recall | f1-score |
|---|---:|---:|---:|
| `BANCO` | 1.00 | 0.90 | 0.95 |
| `CBU` | 0.92 | 0.92 | 0.92 |
| `CORREO_ELECTRONICO` | 1.00 | 1.00 | 1.00 |
| `CUIJ` | 1.00 | 1.00 | 1.00 |
| `CUIT_CUIL` | 1.00 | 1.00 | 1.00 |
| `DIRECCION` | 0.97 | 0.85 | 0.91 |
| `DNI` | 0.96 | 1.00 | 0.98 |
| `EDAD` | 1.00 | 0.95 | 0.97 |
| `ESTUDIOS` | 1.00 | 1.00 | 1.00 |
| `FECHA` | 1.00 | 0.99 | 1.00 |
| `LINK` | 1.00 | 0.94 | 0.97 |
| `LOC` | 0.99 | 0.72 | 0.83 |
| `MARCA_AUTOMOVIL` | 0.95 | 1.00 | 0.97 |
| `NACIONALIDAD` | 1.00 | 0.94 | 0.97 |
| `NUM_ACTUACION` | 0.84 | 0.96 | 0.90 |
| `NUM_CAJA_AHORRO` | 0.00 | 0.00 | 0.00 |
| `NUM_EXPEDIENTE` | 0.98 | 0.92 | 0.95 |
| `NUM_MATRICULA` | 0.33 | 0.50 | 0.40 |
| `PATENTE_DOMINIO` | 1.00 | 1.00 | 1.00 |
| `PER` | 0.98 | 0.97 | 0.98 |
| `TELEFONO` | 0.97 | 1.00 | 0.99 |
| `TEXTO_ANONIMIZAR` | 0.98 | 0.61 | 0.75 |
| `macro avg` | 0.91 | 0.88 | 0.89 |

# Citation

Please cite [the following paper](https://drive.google.com/file/d/1P-hW0JKXWZ44Fn94fDVIxQRTExkK6m4Y/view) when using AymurAI:

```bibtex
@techreport{feldfeber2022,
  author      = {Feldfeber, Ivana and Quiroga, Yasm{\'i}n Bel{\'e}n and Guevara, Clarissa and Ciolfi Felice, Marianela},
  title       = {Feminisms in Artificial Intelligence: Automation Tools towards a Feminist Judiciary Reform in Argentina and Mexico},
  institution = {DataGenero},
  year        = {2022},
  url         = {https://drive.google.com/file/d/1P-hW0JKXWZ44Fn94fDVIxQRTExkK6m4Y/view}
}
```
