# API
The connection between AymurAI's frontend and backend occurs through an Application Programming Interface (API). There are several endpoints that allow communication between the different parts of the software. Calls to these endpoints are made from the frontend to execute different subroutines.

# Endpoints
* `/document-extract`: plain text extraction from .doc or .docx documents
* `/predict`: prediction over a single paragraph
* `/predict-batch`: run prediction over a batch of paragraphs

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


# Source
The api source code is written in top of FastAPI and can be found in [here](../../api/).

Please follow the [code of conduct](../CODE_OF_CONDUCT.md) and [contributing guidelines](../CONTRIBUTING.md).