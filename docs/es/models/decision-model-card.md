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

Idioma: [English](../../models/decision-model-card.md) | **Español**

# Descripción del modelo

Este modelo es el clasificador actual de decisiones a nivel párrafo utilizado en el pipeline de producción `full-paragraph`.
Estima si un párrafo contiene una decisión judicial y, cuando se usa dentro del pipeline de AymurAI, emite una entidad sintética `DECISION` con una subcategoría basada en reglas.

Este modelo fue desarrollado por [{ collective.ai }](https://collectiveai.io) como parte del proyecto [AymurAI](https://aymurai.info) de [DataGenero](https://datagenero.org).

## Arquitectura

El clasificador actual de producción es un modelo compacto de bolsa de palabras con hashing, implementado con `torch.nn.EmbeddingBag`.
Su camino de inferencia está definido en `aymurai/models/decision/binregex.py` y `aymurai/models/decision/embeddingbag.py`.

A alto nivel, el modelo funciona así:

1. El texto de entrada se normaliza quitando tildes, pasando a minúsculas y colapsando espacios.
2. El texto se tokeniza por espacios en blanco.
3. Los tokens se hashean con BLAKE2b sobre un vocabulario fijo.
4. Los IDs de tokens se agrupan mediante embeddings promedio con `EmbeddingBag`.
5. Una capa de dropout y una cabeza lineal producen logits binarios (`not decision`, `decision`).
6. Si el score positivo supera el umbral configurado, el pipeline agrega una etiqueta `DECISION` al párrafo.

Configuración actual del checkpoint cargado por el modelo de producción:

| parámetro | valor |
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

## Usos previstos y limitaciones

AymurAI está pensado como una herramienta para abordar la falta de transparencia en el sistema judicial en relación con casos de violencia de género (VG) en América Latina. El objetivo es aumentar los niveles de reporte, construir confianza en el sistema de justicia y mejorar el acceso a la justicia para mujeres y personas LGBTIQ+. AymurAI genera y mantiene datasets anonimizados a partir de sentencias judiciales para comprender la violencia de género y apoyar el diseño de políticas públicas, además de contribuir a campañas de colectivos feministas.

Las capacidades de AymurAI se limitan a la recolección y análisis semiautomatizados de datos, y sus resultados pueden estar sujetos a limitaciones como la calidad y consistencia de los datos, posibles sesgos del modelo de IA y la disponibilidad de la información. Además, la efectividad de AymurAI para abordar la falta de transparencia del sistema judicial y mejorar el acceso a la justicia también puede depender de otros factores, como el nivel de cooperación de funcionarios judiciales y el contexto cultural y político más amplio.

Este modelo fue entrenado con un dataset cerrado proveniente de un juzgado penal argentino. Está diseñado para identificar si un párrafo contiene una decisión judicial. El uso de un dataset específico de dominio, proveniente de un juzgado penal argentino, hace que el modelo esté ajustado al contexto jurídico y cultural concreto, lo que permite resultados más precisos. Sin embargo, esto también implica que el modelo puede no ser aplicable o efectivo en otros países o regiones con sistemas jurídicos o normas culturales diferentes.

## Comportamiento en producción

Cuando este clasificador se utiliza a través de `DecisionEmbeddingBagBinRegex`, el comportamiento en producción incluye dos reglas adicionales además de la predicción binaria cruda:

- La clase positiva se emite solo cuando el score de decisión supera el umbral configurado (`0.5` en el pipeline de producción).
- Con `return_only_with_detalle=true`, el clasificador solo agrega una entidad `DECISION` si el párrafo ya contiene una entidad `DETALLE` proveniente de la etapa NER.

Si un párrafo es clasificado como decisión, el modelo emite una entidad `DECISION` que cubre el texto completo del párrafo. La etiqueta emitida incluye una subcategoría basada en reglas:

- `hace_lugar`
- `no_hace_lugar`

Esa subcategoría se asigna mediante postprocesamiento con expresiones regulares sobre el texto del párrafo.

# Uso

## Cómo usar el modelo en torch

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

Esto produce una salida similar a:

```text
[[0.0010057, 0.9989943]]
['hace_lugar']
```

La primera columna es la probabilidad de que el texto no sea una decisión, y la segunda columna es la probabilidad de que el texto sí sea una decisión.

## Uso del modelo en un pipeline de AymurAI

El pipeline actual de producción `full-paragraph` incluye este clasificador después de la etapa NER con Flair.

```python
from aymurai.pipeline import AymurAIPipeline

pipeline = AymurAIPipeline.load("/resources/pipelines/production/full-paragraph")

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

En producción, el clasificador se configura así:

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

# Entidades y métricas

## Descripción

Este modelo solo considera la clasificación de párrafos como decisiones o no decisiones.
Cuando la predicción es positiva, el pipeline emite una entidad sintética `DECISION` que cubre todo el párrafo.

Para la lista completa de entidades usadas por el flujo datapublic, consultá el catálogo de entidades de datapublic ([en](../../entities/datapublic/README.md)|[es](../entities/datapublic/README.md)).

Para una descripción completa de las entidades consideradas por AymurAI, ver el [Glosario para el dataset con perspectiva de género](https://docs.google.com/document/d/123B9T2abCEqBaxxOl5c7HBJZRdIMtKDWo6IKHIVil04/edit), elaborado por [DataGenero](https://datagenero.org) (solo en español).

## Datos

El modelo fue entrenado con un dataset de 1200 resoluciones judiciales de un juzgado penal argentino.

Dada la naturaleza de los datos (datos personales, características de la denuncia y protección de víctimas), los documentos se mantienen privados.

### Lista de personas colaboradoras en la anotación

El dataset fue anotado manualmente por:

* Diego Scopetta
* Franny Rodriguez Gerzovich ([email](mailto:fraanyrodriguez@gmail.com)|[linkedin](https://www.linkedin.com/in/francescarg))
* Laura Barreiro
* Matías Sosa
* Maximiliano Sosa
* Patricia Sandoval
* Santiago Bezchinsky ([email](mailto:santibezchinsky@gmail.com)|[linkedin](https://www.linkedin.com/in/santiago-bezchinsky))
* Zoe Rodriguez Gerzovich

## Métricas

Las siguientes métricas provienen de la notebook actual de entrenamiento/evaluación de EmbeddingBag y corresponden a la tarea binaria de clasificación de decisiones (`0 = no decisión`, `1 = decisión`).

### Split de validación

| métrica | clase 1 (decisión) | general |
|---|---:|---:|
| precision | 0.774 | - |
| recall | 0.896 | - |
| f1-score | 0.830 | - |
| accuracy | - | 0.962 |
| support | 336 | 3211 |

### Split de test

| métrica | clase 1 (decisión) | general |
|---|---:|---:|
| precision | 0.754 | - |
| recall | 0.905 | - |
| f1-score | 0.823 | - |
| accuracy | - | 0.959 |
| support | 336 | 3211 |

# Cita

Por favor citá [el siguiente paper](https://drive.google.com/file/d/1P-hW0JKXWZ44Fn94fDVIxQRTExkK6m4Y/view) al utilizar AymurAI:

```bibtex
@techreport{feldfeber2022,
  author      = {Feldfeber, Ivana and Quiroga, Yasm{'i}n Bel{'e}n and Guevara, Clarissa and Ciolfi Felice, Marianela},
  title       = {Feminisms in Artificial Intelligence: Automation Tools towards a Feminist Judiciary Reform in Argentina and Mexico},
  institution = {DataGenero},
  year        = {2022},
  url         = {https://drive.google.com/file/d/1P-hW0JKXWZ44Fn94fDVIxQRTExkK6m4Y/view}
}
```
