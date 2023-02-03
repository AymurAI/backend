Annotation procedure
====================

In alliance with Criminal Court No. 10 of the Autonomous City of Buenos Aires, Argentina, we have developed a procedure to annotate court rulings.
We collect 1200 court rulings.
The annotations are made in a token classification task, where each token is annotated with the corresponding entity (27 in total, the complete list can be found [here](../data/en/entities-table.md)).
Also we subcategorize any entity that requires it.
These annotations were made using the [label studio](https://labelstud.io/) tool.
The configuration of the annotation task is available in the [label studio config file](../data/label-studio-config.xml).

We are very concerned with data security (see [SECURITY.md](../../docs/SECURITY.md)), and since the legal ruling contains sensible data, we cannot share the data. But a sample of annonimized annotations can be found [here](../../resources/data/sample).

The first step is to export the raw court rulings to a json that can reads label studio. Check out the [export](01-export-docs.ipynb) guide for details.

Assuming you already have annotated documents, you can check the visualization of the annotations in the [visualization](02-visualization.ipynb) example.

# Contributors
* Diego Scopetta
* Franny Rodriguez Gerzovich ([email](fraanyrodriguez@gmail.com)|[linkedin](https://www.linkedin.com/in/francescarg))
* Laura Barreiro
* Matías Sosa
* Maximiliano Sosa
* Patricia Sandoval
* Santiago Bezchinsky ([email](santibezchinsky@gmail.com)|[linkedin](https://www.linkedin.com/in/santiago-bezchinsky))
* Zoe Rodriguez Gerzovich
