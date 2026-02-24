# Guía breve: experimentos de NER para anonimización

Esta guía resume cómo ejecutar y usar los experimentos de NER incluidos para anonimización de documentos judiciales.

## 1) Qué experimentos tenemos

### A. NER + LangExtract alignment
- Runner: `aymurai.experiments.ner_langextract_alignment.runner`
- Objetivo: comparar predicciones del backend NER (`/anonymizer/predict`) contra LangExtract sobre los mismos párrafos.
- Salidas clave:
  - `samples.jsonl`
  - `train_candidates.jsonl`
  - `review_required.jsonl`
  - `llm_traces/*`
  - exports para Label Studio

### B. NER/LangExtract test set evaluation
- Runner: `aymurai.experiments.ner_testset_evaluation.runner`
- Objetivo: evaluar un backend (`ner_api` o `langextract`) contra un test set (CoNLL, HF token classification, o spans JSONL).
- Salidas clave:
  - `predictions.jsonl`
  - `per_sample_scores.jsonl`
  - `metrics_summary.json`
  - `reports/label_metrics.csv`
  - `reports/token_relaxed_confusion.csv`

## 2) Configuración YAML (ejemplos mínimos)

### A. Alignment (extraer documentos + comparar)

```yaml
experiment:
  name: "ner-langextract-alignment"

data:
  input_documents_dir: "/resources/data/pjn"
  include_extensions: [".pdf"]
  max_documents: 100

api:
  base_url: "http://localhost:8899"
  document_extract_path: "/misc/document-extract"
  anonymizer_predict_path: "/anonymizer/predict"
  use_cache: false

langextract:
  provider: "ollama"
  model_id: "qwen3:8b"
  base_url: "http://localhost:11434/v1"
  prompt_description: "Extraé entidades sensibles de textos judiciales."
  examples_yaml_path: "resources/langextract/ner_alignment_examples.yaml"

mapping:
  labels_yaml_path: "resources/experiments/ner-langextract-alignment/label_mapping.yml"

labelstudio:
  enabled: true
  export_dir: "outputs/ner-langextract-alignment/labelstudio"

logging:
  mlflow:
    enabled: true
    tracking_uri: "http://localhost:5000"

outputs:
  base_dir: "outputs/ner-langextract-alignment"
```

### B. Test set evaluation (modo `ner_api`)

```yaml
experiment:
  name: "ner-testset-evaluation"

data:
  format: "conll_bio"
  input_path: "/resources/data/restricted/anonymization/test.txt"

backend:
  mode: "ner_api"

api:
  base_url: "http://localhost:8899"
  anonymizer_predict_path: "/anonymizer/predict"
  use_cache: false

logging:
  mlflow:
    enabled: true
    tracking_uri: "http://localhost:5000"

outputs:
  base_dir: "outputs/ner-testset-evaluation"
```

### C. Test set evaluation (modo `langextract`)

```yaml
backend:
  mode: "langextract"

langextract:
  provider: "ollama"
  model_id: "qwen3:8b"
  base_url: "http://localhost:11434/v1"
  prompt_description: "Extraé entidades sensibles de textos judiciales."
  examples_yaml_path: "resources/langextract/ner_alignment_examples.yml"

mapping:
  labels_yaml_path: "resources/experiments/ner-langextract-alignment/label_mapping.yml"
```

## 3) Comandos para correrlos

```bash
# Alignment
uv run --group mlops -- python -m aymurai.experiments.ner_langextract_alignment.runner \
  --config resources/experiments/ner-langextract-alignment/exp-langextract.yml

# Test set evaluation (template)
uv run --group mlops -- python -m aymurai.experiments.ner_testset_evaluation.runner \
  --config resources/experiments/ner-testset-evaluation/exp-template.yml

# Test set evaluation (LangExtract)
uv run --group mlops -- python -m aymurai.experiments.ner_testset_evaluation.runner \
  --config resources/experiments/ner-testset-evaluation/langextract-qwen3:8b.yml
```

## 4) Pasos sugeridos para explorar datasets públicos (ej. PJN)

1. **Inventario inicial**
   - Identificar carpetas fuente (ej. `/resources/data/pjn`).
   - Relevar formatos (`.pdf`, `.docx`) y volumen total.

2. **Muestra piloto**
   - Seleccionar un subconjunto manejable (por fuero/tipo de documento/longitud).
   - Ejecutar alignment con `max_documents` bajo (20–100) para validar pipeline.

3. **Criterios de calidad de extracción**
   - Medir cuántos documentos quedan con 0 párrafos o con errores de extracción.
   - Definir umbral mínimo de calidad documental antes de anotar.

4. **Definición de estrategia de anonimización**
   - Confirmar taxonomía de etiquetas (`label_mapping.yml`).
   - Marcar qué etiquetas son críticas (ej. `PER`, `DNI`, `CUIT_CUIL`, `CUIJ`).
   - Acordar reglas de desempate ante diferencias NER vs LangExtract.

5. **Revisión humana enfocada**
   - Exportar discrepancias a Label Studio.
   - Resolver primero casos `mixed` y `langextract_only`/`ner_only` de etiquetas críticas.

6. **Consolidación para entrenamiento/evaluación**
   - Usar `train_candidates.jsonl` como base.
   - Mantener `review_required.jsonl` como cola activa de curación.

7. **Iteración controlada**
   - Repetir corrida con cambios de prompt/modelo/mapping de a un factor por vez.
   - Comparar resultados en MLflow y conservar la mejor configuración reproducible.

## 5) Recomendación operativa

- Para arrancar equipo: usar primero el template de `ner-langextract-alignment` con `max_documents` bajo.
- Luego pasar a `ner-testset-evaluation` para medir impacto en un set de referencia estable.