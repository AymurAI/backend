# NER model experiments

# Overview
Flair token classification model for Spanish judicial text.

The model card can be found [here](../../../../docs/pipeline/flair-model-card.md)

75% of the total 1200 documents (court rulings) is used for training and 12.5% for validation and 12.5% for testing.
Each document is split into paragrpahs. The data representation follows the CONLL-2003 format.

# Notebooks
- [00-flair-direct-finetuning.ipynb](00-flair-direct-finetuning.ipynb): fine-tune a pretrained Flair model on the annotated data
- [01-flair-indirect-finetuning.ipynb](00-flair-indirect-finetuning.ipynb): fine-tune a pretrained Flair model on the annotated data
- [02-prediction-formatting.ipynb](02-prediction-formatting.ipynb): format the predictions to the AymurAI pipeline format
- [03-pipeline-integration.ipynb](03-pipeline-integration.ipynb): build the pipeline
- [04-flair-no-finetuning-no-decision.ipynb](04-flair-no-finetuning-no-decision.ipynb): train a Flair model excluding decisions from the data