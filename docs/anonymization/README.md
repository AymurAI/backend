## Pipeline actual de anonimización

1. `/misc/document-extract` recibe el DOCX/PDF y devuelve el payload estructurado con `document_id` y la lista de párrafos.
2. `/anonymizer/predict` procesa cada párrafo y retorna las entidades detectadas (`aymurai_label`, texto y offsets) que el frontend reúne sobre el texto completo. Las predicciones originales se persisten en la base de datos.
3. Se validan manualmente las etiquetas consolidadas directamente en la interfaz gráfica. Al confirmar, se persisten las validaciones en la base de datos.
4. `/anonymizer/anonymize-document` aplica los reemplazos según las entidades confirmadas y genera el documento anonimizado listo para descarga.

## Anonimización con Desambiguación de Entidades Canónicas

1. `/misc/document-extract` recibe el DOCX/PDF y devuelve el payload estructurado (`document_id`, lista de párrafos) tal como hoy.
2. Se procesa cada párrafo con `/anonymizer/predict`, obteniendo los resultados de NER (`aymurai_label`, texto, offsets, contexto previo y posterior y otros atributos).
3. Se consolida la inferencia: agrupamos todas las menciones detectadas y armamos un paquete enriquecido con contexto circundante (párrafo u oraciones vecinas).
4. Módulo de fuzzy-matching cruza cada mención extraida para sugerir candidatos de `CanonicalEntities` (`canonical_text` y `aliases`).
5. El contexto del paso 3 más las sugerencias del paso 4 son insumo para el servicio de desambiguación (LLM); el modelo se encarga de validar los `CanonicalEntities` sugeridos o proponer nuevos, al tiempo que infiere atributos adicionales (rol procesal), devolviendo una lista refinada de `CanonicalEntities`.
6. Con esa lista se ejecuta el mapeo de `Entity` a `CanonicalEntity`: cada mención NER queda anotada con un `canonical_entity_id` y un `aymurai_label_instance` (índice entero por orden de aparición) y cualquier atributo inferido, generando la desambiguación de entidades.
7. El frontend consume esos outputs y muestra el texto original con dos niveles de revisión: etiquetas NER y asignación canónica.
8. Tras la validación manual, el cliente invoca `/anonymizer/anonymize-document`, que ahora utiliza políticas de render (`render_policy`) para aplicar reemplazos consistentes (etiqueta o subclase con sufijos opcionales) y generar el documento anonimizado final.
9. El documento anonimizado queda disponible para descarga y se registran en la base de datos las decisiones finales (etiquetas y canónicos).

## Cambios principales en el modelo de datos

### Nuevos campos en `EntityAttributes`

- `canonical_entity_id`: UUID de la entidad canónica asignada a cada mención.
- `aymurai_label_instance`: índice entero por orden de aparición del `canonical_entity_id` dentro de un mismo label (1, 2, 3...).
- `aymurai_label_subclass`: lista de roles inferidos por LLM (p. ej. "Denunciante", "Juez/a").
- `aymurai_disambiguation`: método aplicado para la desambiguación efectiva del label (`llm`, `fuzzy`, `none`).
- `aymurai_anonymize`: flag efectivo de anonimización (True/False).

### Políticas por label (nueva interfaz)

Se incorpora un esquema de políticas por etiqueta que permite decidir:

- `disambiguation`: `"none" | "fuzzy" | "llm"`
- `anonymize`: `true | false`

Estas políticas pueden venir de:

1. Configuración del servidor (variable de entorno `DISAMBIGUATION_LABEL_POLICIES`).
2. Request del usuario (campo `label_policies` en `/anonymizer/disambiguate` y `/anonymizer/anonymize-document`).

## Render Policy (integración con frontend)

Para evitar sumar flags adicionales en cada entidad, el comportamiento de render se controla con un objeto `render_policy` (a nivel request/documento), que define:

- `use_subclass_when_available`: usar `aymurai_label_subclass` cuando exista.
- `fallback_to_label`: si no hay subclase, usar `aymurai_label`.
- `suffix_mode`: `"auto" | "always" | "never"`.
- `suffix_threshold`: umbral para agregar sufijo en modo `auto`.

Esto permite generar tokens como:

- `<JUEZ/A>` si hay un solo juez.
- `<DENUNCIANTE_1>`, `<DENUNCIANTE_2>` si hay múltiples.
- `<PER>` si no hay subclase disponible y `fallback_to_label` está activo.

El `render_policy` puede definirse por entorno (`RENDER_POLICY`) o por request y se aplica al momento de exportar el documento con `/anonymizer/anonymize-document`.

## Cambios en la API

### `/anonymizer/disambiguate`

- **Nuevo input opcional**: `label_policies`.
- **Nuevo output**: `label_policies` y metadatos efectivos en cada `DocLabel` (`aymurai_disambiguation`, `aymurai_anonymize`).
- La selección de labels para LLM/fuzzy se define por políticas, no por un modo global.

### `/anonymizer/anonymize-document`

- **Input**: `DocumentAnnotations` incluye `label_policies` y `render_policy`.
- **Render**: los tokens se generan según `render_policy` y respetan `aymurai_anonymize`.

## Plan de evaluación incremental

El objetivo general es optimizar la extracción y desambiguación de entidades. Para avanzar con criterio orientado a métricas mediremos cada capa y el sistema end-to-end.

- **NER**: aunque el modelo actual cubre el caso de uso, debemos planificar un nuevo ciclo de entrenamiento y finetuning. Será importante consolidar un dataset público anotado con las entidades a detectar, para lo cual podemos aprovechar repositorios públicos de documentos legales de Argentina (e idealmente, del resto de latinoamérica). Para el etiquetado automático, podemos combinar predicciones del NER actual con las extracciones obtenidas usando [`langextract`](/notebooks/experiments/anonymization/05-langextract.ipynb), y conservar solo las coincidencias exactas entre ambos sistemas para minimizar ruido. Luego, se deberán realizar algunas revisiones manuales para asegurar calidad. Este dataset nos permitirá definir un split de evaluación estable y automatizar el cálculo de F1 por etiqueta para comparar versiones de forma consistente.
- **Heurística de agrupación**: vamos a contrastar variantes como Levenshtein normalizada, token fuzzy matching o TF-IDF con coseno. Cada método se ejecutará sobre predicciones reales del NER (para medir robustez ante ruido) y sobre etiquetas existentes (para estimar el techo teórico). La métrica utilizada para evaluar será aquella definida en `/notebooks/experiments/entity-disambiguation/Desarrollo metrica.md`, contra un conjunto de `CanonicalEntities` ya anotados.
- **LLM para desambiguación**: la calidad depende de cómo se promptea y del contexto entregado. Deberíamos experimentar con distintas ventanas de contexto variable (documento completo, párrafos que contienen entidades, oraciones vecinas, metadata, etc.), variantes de prompt (instrucciones directas versus cadenas guiadas) y configuraciones de temperatura/top-p. Cada variante se evaluará con la métrica anteriormente mencionada.

Finalmente consolidaremos una evaluación integrada combinando el mejor NER disponible, la heurística con mayor cobertura y baja tasa de falsos positivos y la versión de prompt más precisa. El benchmark se ejecutará sobre un conjunto de documentos de validación con etiquetas canónicas revisadas.

## Consideraciones de integración con frontend

- Necesitamos habilitar una lista configurable de entidades a excluir de la anonimización. El frontend deberá permitir que la persona usuaria decida, por ejemplo, mantener visibles o no entidades específicas o menciones a funcionariaos públicos según su rol procesal.
- Las exclusiones y la edición manual posterior impactan directamente en el ordenamiento de los `aymurai_label_instance`. Habrá que recalcular los sufijos luego de aplicar exclusiones y validaciones para evitar huecos o inconsistencias entre el texto mostrado y los reemplazos finales.
