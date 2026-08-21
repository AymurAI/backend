# Defensoría del Pueblo (GCBA) — extracción de datos y sector

Este directorio contiene las notebooks de experimentación para el endpoint
`/llm/data-extraction` (código real en
`aymurai/api/endpoints/routers/llm/data_extraction/`). Este README explica **cómo
funciona hoy** la extracción, la inferencia de `sector` (secciones 1-4 — la parte
con más lógica propia y la que más cambió durante el desarrollo) y la persistencia
en base de datos, incluyendo cómo se reusan las validaciones humanas en corridas
futuras (sección 5).

## 1. Extracción de datos (paso LLM)

Dado un documento ya extraído (texto plano, vía `/misc/document-extract`), el LLM
devuelve una estructura con:

- `numero_recomendacion`, `fecha_recomendacion`
- `destinatarios`: lista de `{nombre, cargo, destinatario_principal, sector}` — el
  `sector` acá es una clasificación **macro**: `"GCBA"`, `"Empresa"`,
  `"Organismos Nacionales"` u `"Obra Social / Prepaga"`.
- `tema` / `subtema` (validados contra la taxonomía en `resources/llm/defensoria_extractor.yml`)
- `datos_personales`, `contenido_para_publicar`

`nombre` y `cargo` se devuelven **tal cual los extrajo el modelo** — son campos de
texto libre en el front, sin dropdown propio. Lo único que se procesa más allá del
LLM es, para cada destinatario con `sector="GCBA"`, la inferencia de **a qué sector
específico de GCBA pertenece** (`candidatos_sector`).

`tema`/`subtema` sí generan dropdowns propios (`temas_disponibles`/
`subtemas_disponibles`), pero son puramente estructurales (no hay búsqueda): el tema
del LLM va primero, seguido del resto de la taxonomía.

## 2. Inferencia de sector — paso 1: candidatos de organigrama

Para cada destinatario GCBA, `organigram_matching.search_candidates` busca en el
organigrama (`organigram_GCBA.json`, cargado por `_load_organigram_people`):

- hasta `top_k` filas por similitud de **nombre**
- hasta `top_k` filas por similitud de **cargo**

...como dos listas independientes (nunca se combinan en una sola respuesta — una
persona puede haber cambiado de cargo, así que el candidato de nombre y el de cargo
no tienen por qué coincidir en la misma fila del organigrama).

El backend de búsqueda (`fuzzy` / `embeddings` / `hybrid`, ponderado por
`hybrid_weight`) determina cómo se puntúa la similitud. Antes de comparar, tanto el
texto de la consulta como los valores del organigrama pasan por `clean_cargo`
(`organigram_matching.py`): normaliza, identifica un título de rol (ministro,
secretario, director, titular, jefe, etc. — ver `CARGO_ROLE_PREFIXES`) y corta la
cadena de institución padre que sigue (`"... del Ministerio de X del Gobierno de..."`),
porque el organigrama nunca trae esa cadena en sus propios valores de `cargo`.

Cada candidato resultante trae `nombre`, `cargo`, `score` y `ruta_cargos` (el camino
completo desde "Jefe de Gobierno" hasta esa fila) — este último es la entrada del
paso 2.

## 3. Inferencia de sector — paso 2: `sector_mode`

Con los candidatos de organigrama en mano, hay dos formas de resolver el sector
específico (`sector_mode`, configurable por request):

### `"csv"` — matching contra `destinatario_por_sector.csv`

Por cada candidato, `sector_matching.search_sector_candidates` busca su `cargo`
contra las ~140 filas de `destinatario_por_sector.csv` (columna `Destinatario` ->
columna `Destinatario por sector`), tomando hasta `sector_top_k` mejores matches (no
solo el mejor). Usa el mismo backend fuzzy/embeddings/hybrid que el paso 1.

### `"hierarchy"` — lectura directa del organigrama

`sector_matching.resolve_sector_from_hierarchy` no toca el CSV: lee `ruta_cargos` del
candidato y aplica reglas fijas, en este orden:

1. **Organismos autónomos** (AGC, AGIP, Instituto de Vivienda de la Ciudad, COPIDIS —
   ver `_AUTONOMOUS_BODY_KEYWORDS`): si el candidato es uno de estos, o cuelga de uno
   de ellos, el sector es ese organismo — aunque el organigrama lo anide
   administrativamente bajo un ministerio (ej. AGIP cuelga de Ministerio de Hacienda
   y Finanzas, pero el sector es "AGIP").
2. **Ministerio**: si aparece un Ministerio en el camino (sea el cargo mismo o algo
   que dependa de él), ese es el sector.
3. **Secretaría**: si no hay ningún Ministerio en el camino pero aparece una
   Secretaría, esa es el sector (una Subsecretaría sola, sin Secretaría por encima,
   no alcanza — siempre pertenece a su Secretaría, nunca al revés).
4. **Jefatura de Gabinete**: si nada de lo anterior aplica pero el camino pasa por
   "Jefatura de Gabinete de Ministros" (organismos que cuelgan directo de ahí sin
   ministerio/secretaría intermedios), el sector es "Jefatura de Gabinete".
5. **Fallback**: el primer nivel real del camino tal cual (cubre organismos
   independientes como Vicejefatura de Gobierno, Procuración General, etc.).

Cada modo pondera el candidato de origen igual: el score final es
`(score de sector, si aplica) × (score del organigrama normalizado a [0,1]) ×
peso_campo`, donde `peso_campo = nombre_origen_weight` si el candidato vino de la
búsqueda por **nombre**, o `1.0` si vino de **cargo** — esto compensa que los nombres
tienden a puntuar más alto que los cargos por pura similitud de texto (un nombre o
matchea casi exacto o no matchea nada; un cargo tiene mucha más variabilidad de
redacción), aunque el cargo sea la señal más durable frente a un cambio de gobierno.

## 4. Configuración y default actual

| Parámetro | Default | Uso |
|---|---|---|
| `search_backend` | `"hybrid"` | Backend del paso 1 (y del paso 2 en modo `csv`). |
| `hybrid_weight` | **`0.25`** | Peso de embeddings en modo hybrid (fuzzy pesa el resto). |
| `top_k` | `5` | Candidatos de organigrama por campo (nombre/cargo). |
| `sector_mode` | **`"hierarchy"`** | Cómo resolver el sector específico (ver sección 3). |
| `sector_top_k` | `3` | Solo aplica con `sector_mode="csv"`. |
| `nombre_origen_weight` | **`0.0`** | Descuento a evidencia de nombre al inferir sector. |

**Por qué el default es `sector_mode="hierarchy"` (y no `"csv"`):**
`destinatario_por_sector.csv` es una lista curada de un corpus histórico puntual —
cubre 16 sectores, mientras que el organigrama tiene ~33. Si el sector real de un
destinatario no está en esas 16 filas, el modo `"csv"` **no puede acertar nunca**,
sin importar qué tan bueno sea el matching — tiene un techo de cobertura estructural
que `"hierarchy"` no tiene. Además, el CSV no se mantiene sincronizado con cambios en
el organigrama (ya encontramos inconsistencias de nombres entre ambos, como
"Secretaría de Deporte" vs "Secretaría de Deportes"), mientras que `"hierarchy"` lee
siempre la fuente más actualizada disponible.

`nombre_origen_weight=0.0` fue una decisión deliberada, no solo un ajuste fino: se
descarta por completo la evidencia de nombre para inferir sector, porque un nombre
puede matchear con score muy alto por pura casualidad de texto (aunque la persona ya
no ocupe ese cargo), y esa evidencia le puede ganar a la de cargo -- que es la señal
que realmente queremos que decida el sector.

## 5. Persistencia: predicción, validación humana y sectores ya confirmados

Cada corrida se guarda, y las validaciones humanas se reusan para mejorar
corridas futuras. Todo esto vive en
`aymurai/database/{meta,crud,versions}/data_extraction/` (mismo patrón que
`anonymization`/`datapublic`: una tabla `SQLModel` por concepto, un módulo CRUD, y
las migraciones de Alembic correspondientes).

### 5.1 `llm_data_extraction` — una fila por documento extraído, cacheada por `document_id`

`POST /llm/data-extraction` guarda automáticamente el resultado en la tabla
`llm_data_extraction` (modelo `DataExtraction`), keyed por
`document.document_id` (el mismo id que devuelve `/misc/document-extract`, no un
hash derivado del texto). Columnas: `document` (texto fuente), `prediction`
(el `DataExtractionResult` tal cual lo devolvió el pipeline), `validation`
(`None` hasta que alguien valide) y `config` (todos los parámetros resueltos de
esa corrida: model, search_backend, hybrid_weight, top_k, sector_mode,
sector_top_k, nombre_origen_weight, max_retries, options).

Si ese `document_id` ya tiene una fila guardada, por default el endpoint la
devuelve directo (`existing.prediction`) **sin volver a llamar al LLM ni correr
el organigrama** -- es un caché por documento, corre por `extraction_service.
run_data_extraction`. Para forzar una nueva corrida (por ejemplo, para probar
otra config) hay que mandar `force_reextract: true` en el request; ahí sí se
sobreescribe la fila (`prediction`/`config` nuevos, `validation` se resetea a
`None` -- mirror del mismo comportamiento que `summarization_create_or_update`).

Este caché es independiente del lookup de la sección 5.3: uno es por
`document_id` exacto (mismo documento), el otro es por `nombre` de destinatario
(misma persona, en cualquier documento) -- son dos mecanismos distintos que no
se pisan entre sí.

### 5.2 Guardar una validación humana

`PUT /llm/data-extraction/{document_id}/validate` recibe el `DataExtractionResult`
ya corregido por un humano y:

1. Lo guarda como `validation` en la fila de `llm_data_extraction` de ese
   `document_id` (404 si nunca se extrajo ese documento).
2. Para cada destinatario con `sector` macro `"GCBA"` y `sector_confirmado` seteado,
   upsertea una fila en `llm_validated_destinatario` (modelo
   `ValidatedDestinatario`): `{nombre, cargo, sector}`, keyed por
   `nombre_normalizado` (`organigram_matching.normalize_text(nombre)` --
   minúsculas, sin tildes).

`sector` y `sector_confirmado` son campos **distintos** en `DestinatarioExtraction`
a propósito: `sector` siempre es la macro-categoría que devuelve el LLM ("GCBA",
"Empresa", "Organismos Nacionales", "Obra Social / Prepaga") y nunca se
sobreescribe; `sector_confirmado` es el sector específico de GCBA que el humano
elige de `candidatos_sector` (o tipea a mano) -- el front muestra `sector` y,
solo cuando es `"GCBA"`, `sector_confirmado` con sus opciones debajo. Es `None`
hasta que se valida.

### 5.3 Sectores ya validados, como primera sugerencia

Antes de correr la inferencia por organigrama (sección 2-3), cada destinatario
GCBA con `nombre` se busca en `llm_validated_destinatario` por coincidencia
**exacta** de `nombre_normalizado` (`extraction_service._validated_candidate`) --
sin fuzzy matching, para no traer falsos positivos por similitud de texto.

Si hay match, se antepone como primer elemento de `candidatos_sector`
(`origen_campo="validado"`, `score=1.0`), seguido de los candidatos normales del
organigrama sin alterar -- no lo reemplaza, así el humano siempre puede elegir
otro si la persona cambió de sector. Si no hay match (nombre nuevo, o nunca
validado antes), `candidatos_sector` sale igual que antes de esta sección.
