# Métrica de evaluación para el desambiguador de entidades

Este documento describe la métrica con la que evaluamos el módulo de **desambiguación de entidades canónicas** en documentos judiciales. La métrica es independiente del NER (que se evalúa por separado con F1 por clase) y se centra en medir la calidad de la resolución de entidades.

La métrica:

- recibe dos JSON:
  - `gold_json`: referencia (ground truth),
  - `pred_json`: salida del desambiguador;
- calcula cuatro componentes complementarios:
- $F1_{\text{ent}}$: calidad en la **detección de entidades canónicas**,
- $\text{AliasF1}_{\text{macro}}$: calidad en la **agrupación de aliases**,
- $Acc_{\text{label}}$: exactitud del **label** (`aymurai_label`),
- $Acc_{\text{rol}}$: exactitud del **rol** (`attributes["rol"]`);
- devuelve un escalar final como combinación ponderada:

$$
\text{Score}_{\text{global}} =
w_{\text{ent}} \cdot F1_{\text{ent}} +
w_{\text{alias}} \cdot \text{AliasF1}_{\text{macro}} +
w_{\text{label}} \cdot Acc_{\text{label}} +
w_{\text{rol}} \cdot Acc_{\text{rol}}.
$$

Valores por defecto de los pesos:

- $w_{\text{ent}} = 0.40$
- $w_{\text{alias}} = 0.35$
- $w_{\text{label}} = 0.20$
- $w_{\text{rol}} = 0.05$

---

## 1. Modelo de datos y notación

Tanto `gold_json` como `pred_json` se modelan como una **lista de entidades canónicas**. Cada entidad sigue la estructura:

```json
{
  "entity_id": "",
  "aymurai_label": "",
  "canonical_text": "",
  "aliases": [],
  "attributes": {},
  "relations": []
}
```

Denotamos:

- Conjunto de entidades gold (referencia): $G = \{ g_1, g_2, \dots, g_N \}$
- Conjunto de entidades predichas: $P = \{ p_1, p_2, \dots, p_M \}$

Para cada entidad $e \in G \cup P$:

- $\text{label}(e)$ es su `aymurai_label`.
- $\text{aliases}(e)$ es el conjunto de aliases (incluyendo `canonical_text`).
- $\text{rol}(e)$ es `attributes["role"]` si existe (en caso contrario es `None`).

La métrica está inspirada en trabajos de **entity resolution** y **coreference**, donde interesa comparar la formación de clusters más que strings exactos.

---

## 2. Preprocesamiento: normalización y conjuntos de aliases

Cada alias se normaliza para mitigar variaciones de formato. Se procesa tanto la lista `aliases` como `canonical_text`, y se construye un conjunto de strings normalizados que representa a la entidad.

### 2.1. Normalización de texto

Sea una función $\text{norm}(\cdot)$ que:

1. convierte a minúsculas,
2. aplica `strip()` para remover espacios extras,
3. elimina tildes y acentos utilizando normalización Unicode.

```python
import unicodedata

def normalize_text(text: str) -> str:
    if text is None:
        return ""
    text = text.strip().lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return text
```

### 2.2. Construcción del conjunto de aliases

Para cada entidad $e$:

$$
\text{aliases}(e) = \{ \text{norm}(a) \mid a \in e.\text{aliases} \} \cup \{ \text{norm}(e.\text{canonical\_text}) \}.
$$

```python
from typing import Any, Dict, Set

def get_alias_set(entity: Dict[str, Any]) -> Set[str]:
    aliases = {
        normalize_text(a)
        for a in entity.get("aliases", [])
        if normalize_text(a)
    }
    canonical = normalize_text(entity.get("canonical_text", ""))
    if canonical:
        aliases.add(canonical)
    return aliases
```

---

## 3. Similitud entre entidades: Jaccard sobre aliases

Para medir qué tan similares son dos entidades, usamos la similitud de **Jaccard** sobre sus conjuntos de aliases:

$$
\text{sim}(g_i, p_j) =
\frac{\lvert \text{aliases}(g_i) \cap \text{aliases}(p_j) \rvert}
     {\lvert \text{aliases}(g_i) \cup \text{aliases}(p_j) \rvert}.
$$

- Valor 1: conjuntos idénticos.
- Valor 0: conjuntos disjuntos.
- Valores intermedios: superposición parcial.

```python
from typing import Set

def alias_jaccard(aliases_gold: Set[str], aliases_pred: Set[str]) -> float:
    if not aliases_gold and not aliases_pred:
        return 1.0
    union = aliases_gold | aliases_pred
    if not union:
        return 0.0
    inter = aliases_gold & aliases_pred
    return len(inter) / len(union)
```

Construimos una **matriz de similitud** $S \in \mathbb{R}^{N \times M}$ donde $S_{ij} = \text{sim}(g_i, p_j)$.

---

## 4. Emparejamiento de entidades (matching gold–pred)

### 4.1. Problema

Necesitamos decidir qué entidad predicha corresponde a cada entidad gold. Esto es un matching bipartito:

- Si el modelo divide una entidad real en dos, solo una predicha debería emparejarse con la gold; la otra contará como falso positivo.
- Si el modelo fusiona dos entidades distintas, solo una gold se emparejará; la otra será falso negativo.

### 4.2. Umbral de similitud

Se define un umbral $\tau$ (por defecto $\tau = 0.3$):

- Si $S_{ij} < \tau$, se rechaza el match.
- Si $S_{ij} \ge \tau$, el par se considera candidato.

### 4.3. Algoritmo greedy de emparejamiento

Usamos un matching greedy ordenado por similitud (alternativa simple al algoritmo Húngaro):

```python
from typing import List, Tuple

def greedy_matching(
    sim_matrix: List[List[float]],
    sim_threshold: float
) -> List[Tuple[int, int, float]]:
    matches: List[Tuple[int, int, float]] = []
    num_gold = len(sim_matrix)
    num_pred = len(sim_matrix[0]) if num_gold > 0 else 0

    candidates = []
    for i in range(num_gold):
        for j in range(num_pred):
            sim = sim_matrix[i][j]
            if sim >= sim_threshold:
                candidates.append((sim, i, j))

    candidates.sort(reverse=True, key=lambda x: x[0])

    used_gold, used_pred = set(), set()
    for sim, i, j in candidates:
        if i in used_gold or j in used_pred:
            continue
        used_gold.add(i)
        used_pred.add(j)
        matches.append((i, j, sim))

    return matches
```

El resultado es una lista de triples $(i, j, \text{sim})$ con las parejas aceptadas.

---

## 5. Métrica de entidades: $F1_{\text{ent}}$

Sean:

- $\text{TP}$: número de pares emparejados.
- $\text{FN} = N - \text{TP}$: entidades gold sin match (perdidas).
- $\text{FP} = M - \text{TP}$: entidades pred sin match (inventadas o splits innecesarios).

```math
P_{\text{ent}} = \frac{\text{TP}}{\text{TP} + \text{FP}}, \qquad
R_{\text{ent}} = \frac{\text{TP}}{\text{TP} + \text{FN}}
```

```math
F1_{\text{ent}} =
\begin{cases}
\dfrac{2 P_{\text{ent}} R_{\text{ent}}}{P_{\text{ent}} + R_{\text{ent}}}, & \text{si } P_{\text{ent}} + R_{\text{ent}} > 0 \\
0, & \text{en otro caso}
\end{cases}
```

Interpretación: penaliza entidades faltantes, inventadas y los splits/merges incorrectos.

---

## 6. Métrica de aliases: $\text{AliasF1}_{\text{macro}}$

Para cada par emparejado $(g_i, p_j)$:

```math
A_g = \text{aliases}(g_i), \quad
A_p = \text{aliases}(p_j), \quad
I = |A_g \cap A_p|
```

```math
P_{\text{alias}}^{(i)} = \frac{I}{|A_p|}, \qquad
R_{\text{alias}}^{(i)} = \frac{I}{|A_g|}
```

```math
F1_{\text{alias}}^{(i)} =
\begin{cases}
\dfrac{2 P_{\text{alias}}^{(i)} R_{\text{alias}}^{(i)}}
      {P_{\text{alias}}^{(i)} + R_{\text{alias}}^{(i)}}, &
\text{si } P_{\text{alias}}^{(i)} + R_{\text{alias}}^{(i)} > 0 \\
0, & \text{en otro caso}
\end{cases}
```

Promediamos macro sobre los matches:

```math
\text{AliasF1}_\text{macro} =
\frac{1}{\text{TP}} \sum_{(i,j) \in M_{\text{match}}} F1_{\text{alias}}^{(i)}
```

- Falta de aliases relevantes → baja el recall.
- Aliases incorrectos → baja la precision.
- Splits se reflejan en menor $F1_{\text{alias}}$.

```python
alias_f1_sum = 0.0
for i, j, _ in matches:
    A_g = gold_aliases[i]
    A_p = pred_aliases[j]
    inter = len(A_g & A_p)

    P_alias = inter / len(A_p) if A_p else 0.0
    R_alias = inter / len(A_g) if A_g else 0.0
    if P_alias + R_alias > 0:
        F1_alias = 2 * P_alias * R_alias / (P_alias + R_alias)
    else:
        F1_alias = 0.0

    alias_f1_sum += F1_alias

AliasF1_macro = alias_f1_sum / TP if TP > 0 else 0.0
```

---

## 7. Exactitud de label y rol

Para cada match \((g_i, p_j)\):

```math
\text{correctLabel}^{(i)} =
\begin{cases}
1, & \text{si } \text{label}(g_i) = \text{label}(p_j) \\
0, & \text{en otro caso}
\end{cases}
```

```math
\text{correctRol}^{(i)} =
\begin{cases}
1, & \text{si } \text{rol}(g_i) = \text{rol}(p_j) \\
0, & \text{en otro caso}
\end{cases}
```

```math
Acc_{\text{label}} =
\frac{1}{\text{TP}} \sum_{(i,j) \in M_{\text{match}}} \text{correctLabel}^{(i)}, \quad
Acc_{\text{rol}} =
\frac{1}{\text{TP}} \sum_{(i,j) \in M_{\text{match}}} \text{correctRol}^{(i)}.
```

```python
label_correct = 0
role_correct = 0

for i, j, _ in matches:
    if gold_labels[i] == pred_labels[j]:
        label_correct += 1
    if gold_roles[i] == pred_roles[j]:
        role_correct += 1

Acc_label = label_correct / TP if TP > 0 else 0.0
Acc_role = role_correct / TP if TP > 0 else 0.0
```

Separar la calidad de la clusterización (aliases) de la del rotulado alinea la métrica con enfoques **entity-centric** en la literatura.

---

## 8. Función `compute_metrics_components`

Integra todos los pasos anteriores y devuelve un diccionario con los cuatro componentes:

```python
from typing import Any, Dict, List

def compute_metrics_components(
    gold_entities: List[Dict[str, Any]],
    pred_entities: List[Dict[str, Any]],
    sim_threshold: float = 0.3,
) -> Dict[str, float]:
    if not gold_entities and not pred_entities:
        return {
            "F1_ent": 1.0,
            "AliasF1_macro": 1.0,
            "Acc_label": 1.0,
            "Acc_role": 1.0,
        }

    gold_aliases = [get_alias_set(e) for e in gold_entities]
    pred_aliases = [get_alias_set(e) for e in pred_entities]

    gold_labels = [e.get("aymurai_label") for e in gold_entities]
    pred_labels = [e.get("aymurai_label") for e in pred_entities]

    gold_roles = [e.get("attributes", {}).get("rol") for e in gold_entities]
    pred_roles = [e.get("attributes", {}).get("rol") for e in pred_entities]

    sim_matrix = [
        [alias_jaccard(g_gold, g_pred) for g_pred in pred_aliases]
        for g_gold in gold_aliases
    ]

    matches = greedy_matching(sim_matrix, sim_threshold=sim_threshold)

    TP = len(matches)
    FN = len(gold_entities) - TP
    FP = len(pred_entities) - TP

    P_ent = TP / (TP + FP) if TP + FP > 0 else 0.0
    R_ent = TP / (TP + FN) if TP + FN > 0 else 0.0
    F1_ent = 2 * P_ent * R_ent / (P_ent + R_ent) if P_ent + R_ent > 0 else 0.0

    alias_f1_sum = 0.0
    label_correct = 0
    role_correct = 0

    for i, j, _ in matches:
        A_g = gold_aliases[i]
        A_p = pred_aliases[j]
        inter = len(A_g & A_p)

        P_alias = inter / len(A_p) if A_p else 0.0
        R_alias = inter / len(A_g) if A_g else 0.0
        if P_alias + R_alias > 0:
            F1_alias = 2 * P_alias * R_alias / (P_alias + R_alias)
        else:
            F1_alias = 0.0
        alias_f1_sum += F1_alias

        if gold_labels[i] == pred_labels[j]:
            label_correct += 1
        if gold_roles[i] == pred_roles[j]:
            role_correct += 1

    AliasF1_macro = alias_f1_sum / TP if TP > 0 else 0.0
    Acc_label = label_correct / TP if TP > 0 else 0.0
    Acc_role = role_correct / TP if TP > 0 else 0.0

    return {
        "F1_ent": F1_ent,
        "AliasF1_macro": AliasF1_macro,
        "Acc_label": Acc_label,
        "Acc_role": Acc_role,
    }
```

---

## 9. Métrica escalar final: `evaluate_disambiguation`

Función de alto nivel que combina los componentes con los pesos:

```python
import json
from typing import Any

def evaluate_disambiguation(
    gold_json: Any,
    pred_json: Any,
    w_ent: float = 0.4,
    w_alias: float = 0.35,
    w_label: float = 0.2,
    w_role: float = 0.05,
    sim_threshold: float = 0.3,
) -> Tuple[float, Dict[str, float]]:
    if isinstance(gold_json, str):
        gold_entities = json.loads(gold_json)
    else:
        gold_entities = gold_json

    if isinstance(pred_json, str):
        pred_entities = json.loads(pred_json)
    else:
        pred_entities = pred_json

    metrics = compute_metrics_components(
        gold_entities,
        pred_entities,
        sim_threshold=sim_threshold,
    )

    return (
        w_ent * metrics["F1_ent"]
        + w_alias * metrics["AliasF1_macro"]
        + w_label * metrics["Acc_label"]
        + w_role * metrics["Acc_role"]
    )
```

### Justificación de los pesos por defecto

- **$w_{\text{ent}} = 0.40$**: prioriza detectar todas las entidades canónicas sin inventarlas.
- **$w_{\text{alias}} = 0.35$**: agrupar aliases es crucial para preservar el anonimato.
- **$w_{\text{label}} = 0.20$**: el tipo de entidad importa, pero es secundario frente a la detección.
- **$w_{\text{rol}} = 0.05$**: el rol agrega contexto, pero tiene menor peso.

Los pesos pueden ajustarse según las necesidades del proyecto.

---

## 10. Ejemplo de uso

```python
gold = [
    {
        "entity_id": "GT_1",
        "aymurai_label": "PER",
        "canonical_text": "Juan Pérez",
        "aliases": ["Juan Pérez", "Pérez, Juan"],
        "attributes": {"role": "imputado"},
        "relations": []
    }
]

pred = [
    {
        "entity_id": "P_1",
        "aymurai_label": "PER",
        "canonical_text": "juan perez",
        "aliases": ["juan perez", "perez juan"],
        "attributes": {"role": "imputado"},
        "relations": []
    }
]

score, components = evaluate_disambiguation(gold, pred)
print("Score global:", score)
print(components)
```

---

## 11. Referencias y relación con la literatura

- Moosavi, N. S., & Strube, M. (2016). *Which coreference evaluation metric do you trust? A proposal for a link-based entity aware metric*. ACL.
- Menestrina, D., Whang, S. E., & Garcia-Molina, H. (2010). *Evaluating entity resolution results*. PVLDB.
- Binette, O., et al. (2024). *Comprehensive evaluation frameworks for entity resolution*.

La métrica propuesta toma conceptos de la evaluación de coreference y entity resolution y los adapta a nuestro contexto judicial:

- priorizando no perder entidades sensibles,
- evitando crear entidades inexistentes,
- y reforzando que los aliases de una misma persona no se mezclen con los de otra.
