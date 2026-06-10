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

Idioma: [English](../../models/anonymizer-model-card.md) | **Español**

# Descripción del modelo

Este modelo es el componente NER usado por el pipeline de producción `flair-anonymizer`.
Detecta spans que deben anonimizarse en documentos judiciales antes de la desambiguación, la validación manual y el render final del documento.

Siguiendo las guías de Flair para entrenamiento de NER, el modelo se entrenó sobre [embeddings BETO](https://huggingface.co/dccuchile/bert-base-spanish-wwm-uncased), una versión en español de BERT, con una arquitectura BiLSTM-CRF.

Este modelo fue desarrollado por [{ collective.ai }](https://collectiveai.io) como parte del proyecto [AymurAI](https://aymurai.info) de [DataGenero](https://datagenero.org).

## Usos previstos y limitaciones

AymurAI busca ayudar a abordar la falta de datos disponibles sobre resoluciones de violencia de género (VG) en América Latina. En el flujo de anonimización, el objetivo inmediato de este modelo es identificar spans sensibles en documentos legales para que puedan ser revisados y reemplazados antes de su uso posterior.

AymurAI sigue siendo un sistema específico de dominio. Sus capacidades se limitan a la anonimización, recolección y análisis semiautomatizados de datos judiciales, y la salida puede verse afectada por la calidad de la anotación, la heterogeneidad documental, errores de OCR o extracción y la disponibilidad de datos de entrenamiento representativos.

Este modelo fue entrenado con un dataset cerrado de un juzgado penal argentino. Esa especificidad de dominio mejora el desempeño en el contexto objetivo, pero también implica que el modelo puede no transferir bien a otras jurisdicciones, estilos documentales o culturas jurídicas.

## Comportamiento en producción

En producción, este modelo se carga a través de `aymurai.models.flair.core.FlairModel` desde:

- `resources/pipelines/production/flair-anonymizer/pipeline.json`
- model path: `aymurai/anonymizer-beto-cased-flair`

Sus predicciones de spans se postprocesan luego con:

- `aymurai.transforms.anonymization_postprocess.core.AnonymizationEntityCleaner`
- `aymurai.transforms.datetime_formatter.core.DatetimeFormatter`

Esas predicciones alimentan el resto del flujo de anonimización:

1. `POST /api/anonymizer/predict` ejecuta la extracción de spans.
2. `POST /api/anonymizer/disambiguate` asigna IDs canónicos y metadatos efectivos por label.
3. La revisión manual puede editar labels, `label_policies` y `render_policy`.
4. `POST /api/anonymizer/anonymize-document` aplica los reemplazos sobre el documento de salida.

# Uso

## Cómo usar el modelo en Flair

Requiere **[Flair](https://github.com/flairNLP/flair/)**.
Instalación: `pip install flair`.

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

Esto produce una salida similar a:

```text
Span[22:25]: "EZEQUIEL CAMILO MARCONNI" -> PER (0.9541)
Span[27:28]: "11.222.333" -> DNI (1.0)
```

## Uso del modelo en un pipeline de AymurAI

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

# Entidades y métricas

## Descripción

Consultá el catálogo de entidades de anonymizer ([en](../../entities/anonymizer/README.md)|[es](../entities/anonymizer/README.md)).

## Datos

El modelo fue entrenado con un dataset de 535 resoluciones judiciales de un juzgado penal argentino.

Dada la naturaleza de los datos (datos personales, características de la denuncia y protección de víctimas), los documentos se mantienen privados.

## Métricas

Las siguientes métricas por label provienen de la model card publicada en Hugging Face para esta familia de modelos de anonymizer y deben interpretarse como métricas NER a nivel modelo, no como calidad end-to-end de la anonimización.

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

# Cita

Por favor citá [el siguiente paper](https://drive.google.com/file/d/1P-hW0JKXWZ44Fn94fDVIxQRTExkK6m4Y/view) al utilizar AymurAI:

```bibtex
@techreport{feldfeber2022,
  author      = {Feldfeber, Ivana and Quiroga, Yasm{\'i}n Bel{\'e}n and Guevara, Clarissa and Ciolfi Felice, Marianela},
  title       = {Feminisms in Artificial Intelligence: Automation Tools towards a Feminist Judiciary Reform in Argentina and Mexico},
  institution = {DataGenero},
  year        = {2022},
  url         = {https://drive.google.com/file/d/1P-hW0JKXWZ44Fn94fDVIxQRTExkK6m4Y/view}
}
```
