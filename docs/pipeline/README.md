# Pipeline

<p style="text-align:center;">
<img src="assets/pipeline.png" width="75%" style="background-color:white" alt="schema"/>
</p>

# Preprocessing
El flujo de información comienza con un paso de pre-procesamiento de las resoluciones, en el que los documentos son subdivididos en párrafos y su texto es normalizado: se unifican múltiples espacios y se remueven tildes y/o caracteres especiales (esto último, sólo en el caso del modelo de decisión).
De esta manera, los párrafos constituyen la unidad mínima de análisis y las predicciones se generan en paralelo y de forma independiente entre sí.


# Inference
<p style="text-align:center;">
<img src="assets/inference-example.png" width="45%" style="background-color:white" alt="schema"/>
</p>

Luego del pre-procesamiento, ocurre la inferencia, es decir, el paso en que los modelos de inteligencia artificial procesan los textos para obtener distintas clasificaciones:
El modelo de NER identifica a qué categoría corresponde cada una de las palabras presentes en el texto.
El modelo de decisión indica si cada párrafo constituye una decisión judicial o no.

# Postprocessing

## Subcategorization
* Regex
Las expresiones regulares nos permiten identificar algunas subcategorías cuyos textos suelen repetirse siguiendo patrones muy marcados.
    - Violencia de género
    - Modalidad de la violencia
    - Relación entre acusado/a y denunciante
    - Tipo de resolución
    - Nivel de instrucción
    - Género
    - Persona acusada no determinada
    - Nombre
    - Artículo infringido
    - Decisión

* Sentence Similarity
El modelo de Universal Sentence Encoder Multilingual QA, publicado por Google, nos permite codificar el texto identificado como perteneciente a ciertas categorías para luego calcular un score de similitud semántica con respecto a cada subcategoría posible y así generar un ranking de candidatos, ordenado de mayor a menor similitud.
    - Conducta
    - Conducta descripción
    - Detalle
    - Objeto de la resolución


## Text Formating

## Filters


# Models
Los modelos de IA son la pieza fundamental del backend de AymurAI. Se encargan de las tareas de extracción de información de las resoluciones judiciales.
Para su desarrollo, utilizamos los siguientes frameworks de trabajo:
El modelo de NER fue desarrollado utilizando Flair, una biblioteca de Python creada por Humboldt - Universidad de Berlín con foco en modelos de procesamiento del lenguaje natural. Flair se basa en PyTorch, uno de los principales frameworks de inteligencia artificial, y permite la integración con Transformers, otra de las principales bibliotecas de modelos de procesamiento del lenguaje.
Para el modelo de decisión empleamos PyTorch de forma nativa.


## Model cards
* [Flair NER Spanish Judicial](./flair-model-card.md)
* [Decision Text Classification](./decision-model-card.md)
