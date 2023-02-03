# Decision model experiments

# Overview
The decision model is a two-class text classifier (multi-class approach) model that predicts if a paragraph is a decision or not.

The model card can be found [here](../../../docs/pipeline/decision-model-card.md)

The training data takes directly the paragraphs and split is 80% train and 10% validation and 10% test.

# notebooks
- [00-data-generation.ipynb](00-data-generation.ipynb): generate the data for the model from the annotated data
- [01-training-2class-conv1d.ipynb](01-training-2class-conv1d.ipynb): train the model using a custom word embedding and a 1D convolutional neural network as feature extractor. then a simple dense layer is used to predict the class.
- [02-evaluation-2class-conv1d.ipynb](02-evaluation-2class-conv1d.ipynb): evaluate the model
- [03-pipeline-build.ipynb](03-pipeline-build.ipynb): build the pipeline