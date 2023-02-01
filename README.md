AymurAI backend
===================

# Intro

# Table of contents

# Intended uses & limitations
AymurAI is intended to be used as a tool to address the lack of transparency in the judicial system regarding gender-based violence (GBV) cases in Latin America. The goal is to increase report levels, build trust in the justice system, and improve access to justice for women and LGBTIQ+ people. AymurAI will generate and maintain anonymized datasets from legal rulings to understand GBV and support policy making, and also contribute to feminist collectives' campaigns.

AymurAI is still a prototype and is only being implemented in Argentina and Mexico. Its capabilities are limited to semi-automated data collection and analysis, and the results may be subject to limitations such as the quality and consistency of the data, potential biases in the AI model, and the availability of the data. Additionally, the effectiveness of AymurAI in addressing the lack of transparency in the judicial system and improving access to justice may also depend on other factors such as the level of cooperation from court officials and the broader cultural and political context.

# Deployment
This project is deployed using [Docker](https://www.docker.com/) , and the images are available in the following registry:
```bash
registry.gitlab.com/collective.ai/datagenero-public/aymurai-api:prod
```
You can a production ready instance of the API by running:
```bash
docker run -d --rm -p 8899:8899 \
    registry.gitlab.com/collective.ai/datagenero-public/aymurai-api:prod
```
this will start a container with the API running on port 8899 on your localhost. The API is documented using OpenAPI and can be accessed at `http://localhost:8899/docs`
Once it is deployed, it doesn't requere a internet connection to work. If you need to deployed in a closed network you can port the image using
```bash
docker image save registry.gitlab.com/collective.ai/datagenero-public/aymurai-api:prod -o aymurai-api.tar
```
and then transfer the image to the target machine and load it using
```bash
docker load -i aymurai-api.tar
```
For more information about docker deployment please refer to the [docker documentation](https://docs.docker.com/).
You also can contact us at aymurai@datagenero.org and we will be happy to help you.

# Repository structure
* developed with docker
*

# Data origin
##
# Pipeline

# Models
## NER
## Decision

# Tutorials


# Contributing
Thanks for your interest in contributing! There are many ways to get involved; start with our [contributor guidelines](docs/CONTRIBUTING.md) and [code of conduct](docs/CODE_OF_CONDUCT.md).


# Citing AymurAI
Please cite [the following paper](https://drive.google.com/file/d/1P-hW0JKXWZ44Fn94fDVIxQRTExkK6m4Y/view) when using AymurAI:

```bibtex
@techreport{feldfeber2022,
    author      = "Feldfeber, Ivana and Quiroga, Yasmín Belén  and Guevara, Clarissa  and Ciolfi Felice, Marianela",
    title       = "Feminisms in Artificial Intelligence:  Automation Tools towards a Feminist Judiciary Reform in Argentina and Mexico",
    institution = "DataGenero",
    year        = "2022",
    url         = "https://drive.google.com/file/d/1P-hW0JKXWZ44Fn94fDVIxQRTExkK6m4Y/view"
}
```

# License
AymurAI is licensed under the [MIT License](LICENSE.md).



<!--
## Variables de entorno
El set de variables de entorno pueden encontrarse en `common.env` (Son cargadas automaticamente en el devcontainer o image de jupyter)
## Data
Este repositorio cuenta con un dataset preconfigurado del Juzgado PCyF 10 de la Ciudad Autonoma de Bueno Aires, Argentina.
Un ejemplo de pipeline puede ser encontrado en
```
notebooks/dev/pipeline-unificado/00-pipeline-public.ipynb
```
Nota: La descarga de los documentos de la base publica puede tardar.

### Data privada
La mayor parte del desarrollo ha sido teniendo encuenta datos privados del Juzgado.
Estos documentos y sus anotaciones correspondientes no estan disponibles para el publico y se asumen presentes en formatos pdf y doc/docx en las carpetas seteadas por las variables de entorno `$AYMURAI_RESTRICTED_DOCUMENT_PDFS_PATH` y `$AYMURAI_RESTRICTED_DOCUMENT_PDFS_PATH` (ver `common.env` para ver los valores por defecto) -->