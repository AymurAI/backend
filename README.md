AymurAI backend
===================
This repository contains the backend API and ML models for AymurAI.

# Table of contents
* [About AymurAI, its uses and limitations](#about-aymurai-its-uses-and-limitations)
* [Deployment](#deployment)
* [Pipeline](#pipeline)
* [Tutorials](#tutorials)
* [Contributing](#contributing)
* [Citing AymurAI](#citing-aymurai)
* [License](#license)


# About AymurAI, its uses and limitations

[AymurAI](https://www.aymurai.info) is intended to be used as a tool to address the lack of available data in the judicial system on gender-based violence (GBV) rulings in Latin America. The goal is to increase report levels, build trust in the justice system, and improve access to justice for women and LGBTIQ+ people. AymurAI will generate and maintain anonymized datasets from legal rulings to understand GBV and support policy making, and also contribute to feminist collectives' campaigns.

AymurAI is still a prototype and is only being implemented in Criminal Court N°10 in the City of Buenos Aires, Argentina. Its capabilities are limited to semi-automated data collection and analysis, and the results may be subject to limitations such as the quality and consistency of the data, and the availability of the data. Additionally, the effectiveness of AymurAI in addressing the lack of transparency in the judicial system and improving access to justice may also depend on other factors such as the level of cooperation from court officials and the broader cultural and political context.

This model was trained with a closed dataset from an Argentine criminal court. It's is designed to identify and extract relevant information from court rulings related to GBV cases. The use of a domain specific dataset from an Argentine criminal court ensures that the model is tailored to the specific legal and cultural context, allowing for more accurate results. However, it also means that the model may not be applicable or effective in other countries or regions with different legal systems or cultural norms.

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

# Pipeline
A detailed description of the pipeline can be found in the [pipeline documentation](docs/pipeline/README.md).


# Tutorials
Check our [tutorials](tutorials/GET_STARTED.md) to learn how to use AymurAI.


# Contributing
Thanks for your interest in contributing! There are many ways to get involved; start with our [contributor guidelines](docs/CONTRIBUTING.md) and [code of conduct](docs/CODE_OF_CONDUCT.md).

# Contributors
* Julian Ansaldo - [@jansaldo](https://github.com/jansaldo) at [collective.ai](https://collectiveai.io) ([email](julian@collectiveai.io))
* Raúl Barriga - [@jedzill4](https://github.com/jedzill4) at [collective.ai](https://collectiveai.io) ([email](r@collectiveai.io))


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
