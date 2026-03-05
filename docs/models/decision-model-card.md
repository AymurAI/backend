---
license: mit
language:
- es
tags:
- text-classification
- embeddingbag
- binary-classification
- judicial-text
datasets:
- ArJuzPCyF10
metrics:
- f1
widget:
- text: 1. DECLARAR EXTINGUIDA LA ACCIÓN PENAL en este caso por cumplimiento de la suspensión del proceso a prueba, y SOBRESEER a EZEQUIEL CAMILO MARCONNI, DNI 11.222.333, en orden a los delitos de lesiones leves agravadas, amenazas simples y agravadas por el uso de armas.
library_name: torch
pipeline_tag: text-classification
---

Language: **English** | [Español](../es/models/decision-model-card.md)

# Model Description

This model is the current paragraph-level decision classifier used in the production `datapublic` pipeline.
It estimates whether a paragraph contains a judicial decision and, when used inside the AymurAI pipeline, emits a synthetic `DECISION` entity with a rule-based subclass.

This model was developed by [{ collective.ai }](https://collectiveai.io) as part of the [AymurAI](https://aymurai.info) project by [DataGenero](https://datagenero.org).

## Architecture

The current production classifier is a compact hashed bag-of-words model implemented with `torch.nn.EmbeddingBag`.
Its inference path is defined in `aymurai/models/decision/binregex.py` and `aymurai/models/decision/embeddingbag.py`.

At a high level, the model works as follows:

1. Input text is normalized with accent stripping, lowercasing, and whitespace collapsing.
2. Text is tokenized by whitespace.
3. Tokens are hashed with BLAKE2b into a fixed vocabulary.
4. Token IDs are pooled with mean `EmbeddingBag` embeddings.
5. A dropout layer and a linear head produce binary logits (`not decision`, `decision`).
6. If the positive score exceeds the configured threshold, the pipeline appends a `DECISION` label to the paragraph.

Current checkpoint configuration loaded with the production model:

| parameter | value |
|---|---|
| `vocab_size` | `20000` |
| `embed_dim` | `64` |
| `max_tokens` | `128` |
| `dropout` | `0.1` |
| `num_classes` | `2` |
| `batch_size` | `512` |
| `lr` | `0.005` |
| `weight_decay` | `0.001` |
| `epochs` | `50` |

## Intended uses & limitations

AymurAI is intended to be used as a tool to address the lack of transparency in the judicial system regarding gender-based violence (GBV) cases in Latin America. The goal is to increase report levels, build trust in the justice system, and improve access to justice for women and LGBTIQ+ people. AymurAI will generate and maintain anonymized datasets from legal rulings to understand GBV and support policy making, and also contribute to feminist collectives' campaigns.

AymurAI capabilities are limited to semi-automated data collection and analysis, and the results may be subject to limitations such as the quality and consistency of the data, potential biases in the AI model, and the availability of the data. Additionally, the effectiveness of AymurAI in addressing the lack of transparency in the judicial system and improving access to justice may also depend on other factors such as the level of cooperation from court officials and the broader cultural and political context.

This model was trained on a closed dataset from an Argentine criminal court. It is designed to identify whether a paragraph contains a judicial decision. The use of a domain-specific dataset from an Argentine criminal court ensures that the model is tailored to the specific legal and cultural context, allowing for more accurate results. However, it also means that the model may not be applicable or effective in other countries or regions with different legal systems or cultural norms.

## Production behavior

When this classifier is used through `DecisionEmbeddingBagBinRegex`, the production behavior includes two additional rules beyond the raw binary prediction:

- The positive class is emitted only when the decision score is above the configured threshold (`0.5` in the production pipeline).
- With `return_only_with_detalle=true`, the classifier only appends a `DECISION` entity if the paragraph already contains a `DETALLE` entity from the NER stage.

If a paragraph is classified as a decision, the model emits a `DECISION` entity covering the full paragraph text. The emitted label includes a rule-based subclass:

- `hace_lugar`
- `no_hace_lugar`

That subclass is assigned with regex-based post-processing over the paragraph text.

# Usage

## How to use the model in torch

```python
import torch

from aymurai.models.decision.binregex import DecisionEmbeddingBagBinRegex

model = DecisionEmbeddingBagBinRegex(
    model_checkpoint="https://github.com/AymurAI/backend/releases/download/v2.0.0-alpha.1/tiny-embeddingbag.safetensors",
    device="cpu",
    threshold=0.5,
    return_only_with_detalle=False,
)

text = "1. DECLARAR EXTINGUIDA LA ACCION PENAL en este caso por cumplimiento de la suspension del proceso a prueba, y SOBRESEER a EZEQUIEL CAMILO MARCONNI, DNI 11.222.333, en orden a los delitos de lesiones leves agravadas."

flat_tokens, offsets = model.model_input_from_text(text)
with torch.no_grad():
    logits = model.model(flat_tokens, offsets)
    probabilities = logits.softmax(dim=1).cpu().numpy()

print(probabilities)
print(model.get_subcategory(text))
```

This yields output similar to:

```text
[[0.0010057, 0.9989943]]
['hace_lugar']
```

The first column is the probability of the text not being a decision, and the second column is the probability of the text being a decision.

## Using the model in an AymurAI pipeline

The current production `datapublic` pipeline includes this classifier after the Flair NER stage.

```python
from aymurai.pipeline import AymurAIPipeline

pipeline = AymurAIPipeline.load("/resources/pipelines/production/datapublic")

item = {
    "path": "dummy",
    "data": {
        "doc.text": "1. DECLARAR EXTINGUIDA LA ACCIÓN PENAL en este caso por cumplimiento de la suspensión del proceso a prueba, y SOBRESEER a EZEQUIEL CAMILO MARCONNI, DNI 11.222.333, en orden a los delitos de lesiones leves agravadas."
    },
}

processed = pipeline.preprocess([item])
processed = pipeline.predict_single(processed[0])
processed = pipeline.postprocess([processed])

print(processed[0]["predictions"]["entities"])
```

In production, the classifier is configured as:

```json
{
  "aymurai.models.decision.binregex.DecisionEmbeddingBagBinRegex": {
    "model_checkpoint": "https://github.com/AymurAI/backend/releases/download/v2.0.0-alpha.1/tiny-embeddingbag.safetensors",
    "device": "cpu",
    "threshold": 0.5,
    "return_only_with_detalle": true
  }
}
```

# Entities and metrics

## Description

This model only considers the classification of paragraphs as decisions or non-decisions.
When the prediction is positive, the pipeline emits a synthetic `DECISION` entity that spans the full paragraph.

For the complete list of entities used by the datapublic flow, please refer to the datapublic entities catalog ([en](../entities/datapublic/README.md)|[es](../es/entities/datapublic/README.md)).

For a complete description of the entities considered by AymurAI, refer to the [Glossary for the Dataset with gender perspective](https://docs.google.com/document/d/123B9T2abCEqBaxxOl5c7HBJZRdIMtKDWo6IKHIVil04/edit) written by [DataGenero](https://datagenero.org) (Spanish only).

## Data

The model was trained with a dataset of 1200 legal rulings from an Argentine criminal court.

Due to the nature of the data (personal data, complaint characteristics, and victim protection), the documents are kept private.

### List of annotation contributors

The dataset was manually annotated by:

* Diego Scopetta
* Franny Rodriguez Gerzovich ([email](mailto:fraanyrodriguez@gmail.com)|[linkedin](https://www.linkedin.com/in/francescarg))
* Laura Barreiro
* Matías Sosa
* Maximiliano Sosa
* Patricia Sandoval
* Santiago Bezchinsky ([email](mailto:santibezchinsky@gmail.com)|[linkedin](https://www.linkedin.com/in/santiago-bezchinsky))
* Zoe Rodriguez Gerzovich

## Metrics

The following metrics were obtained from the current EmbeddingBag training/evaluation notebook and correspond to the binary decision classification task (`0 = not decision`, `1 = decision`).

### Validation split

| metric | class 1 (decision) | overall |
|---|---:|---:|
| precision | 0.774 | - |
| recall | 0.896 | - |
| f1-score | 0.830 | - |
| accuracy | - | 0.962 |
| support | 336 | 3211 |

### Test split

| metric | class 1 (decision) | overall |
|---|---:|---:|
| precision | 0.754 | - |
| recall | 0.905 | - |
| f1-score | 0.823 | - |
| accuracy | - | 0.959 |
| support | 336 | 3211 |

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
