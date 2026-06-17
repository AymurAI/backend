# AymurAI Backend
This repository contains the backend API and machine learning models for [AymurAI](https://www.aymurai.info), a tool designed to generate anonymized datasets from judicial rulings related to gender-based violence (GBV).

AymurAI's backend is responsible for managing the interaction between the frontend and the machine learning models. It provides an API that handles data input, automates the extraction of information from court rulings, and document edition for anonymization purposes.


## Table of Contents
* [About AymurAI, its Uses and Limitations](#about-aymurai-its-uses-and-limitations)
* [Deployment](#deployment)
* [Pipeline](#pipeline)
* [Tutorials](#tutorials)
* [Contributing](#contributing)
* [Contributors](#contributors)
* [Citing AymurAI](#citing-aymurai)
* [License](#license)


## About AymurAI, its Uses and Limitations
AymurAI is a tool designed to address the lack of available data in the judicial system regarding gender-based violence (GBV) rulings in Latin America. Its goal is to increase report levels, build trust in the justice system, and improve access to justice for women and LGBTIQ+ people. AymurAI generates and maintains anonymized datasets from legal rulings to better understand GBV and support policy-making, while also contributing to campaigns run by feminist collectives.

AymurAI is still a prototype and is currently only implemented in Criminal Court N°10 in the City of Buenos Aires, Argentina. Its capabilities are limited to semi-automated data collection and analysis. The quality, consistency, and availability of the data, as well as cooperation from court officials and the broader cultural and political context, may affect its results.

The models were trained using closed datasets from an Argentine criminal court and are specifically tailored to extract relevant information from GBV-related rulings. The domain-specific training ensures the models' accuracy within this legal and cultural context, though they may not be applicable to other regions with different legal systems or cultural norms.


## Deployment
AymurAI's backend is deployed using [Docker](https://www.docker.com/). The Docker images are available at the following registry:

```bash
ghcr.io/aymurai/api:full
```

### Quick Start
To deploy a production-ready instance of the API, run:

```bash
docker run -d -p 8899:8899 ghcr.io/aymurai/api:full
```

This command will start the API on port `8899` on your local machine. You can access the API documentation through OpenAPI at:

```
http://localhost:8899/docs
```

Once it is deployed, it doesn't require an internet connection to work.

### Running on a Closed Network
If you need to deploy in an environment without internet access, export the Docker image by running:

```bash
docker image save ghcr.io/aymurai/api:full -o aymurai-api.tar
```

Transfer the image to the target machine and load it:

```bash
docker load -i aymurai-api.tar
```

For more information on Docker deployment, refer to the [Docker documentation](https://docs.docker.com/). If you need further assistance, feel free to contact us at [aymurai@datagenero.org](mailto:aymurai@datagenero.org).


## Running the ASR server (coro)
Audio transcription is handled by [coro](https://github.com/collectiveai-team/coro), an OpenAI-compatible ASR + speaker-diarization server. It runs as an isolated host process via `uv tool` (no dependency conflicts with the API), and the API talks to it over HTTP/SSE.

Prerequisites (both modes): `ffmpeg` on the host, [`uv`](https://docs.astral.sh/uv/) installed, and a real-disk `CORO_TRANSCRIPT_SPILL_DIR` (not a tmpfs path) so host RAM stays flat on long audio.

```bash
# GPU (NVIDIA): parakeet fp32 + NeMo diarization
./scripts/run-coro.sh gpu

# CPU: parakeet int8
./scripts/run-coro.sh cpu
```

Then point the API at it via the `TRANSCRIBE_BASE_URL` environment variable (see `.env`):

```
TRANSCRIBE_BASE_URL=http://localhost:8000/v1
```

The API connects over HTTP/SSE and is hardware-agnostic — coro's device is independent of the API container's `TORCH_DEVICE`. (`run-coro.sh` pins `uvx --python 3.12`, since NeMo/`kaldialign` lack wheels on newer Pythons.)

To verify the whole path end-to-end (start coro, transcribe a sample over SSE via both the OpenAI SDK and aymurai's client):

```bash
rtk uv run python scripts/smoke_coro.py cpu   # or: gpu
```


## Pipeline
AymurAI’s backend utilizes a structured data processing pipeline to handle anonymized legal rulings and extract relevant information. This data is processed and made accessible via the API. For more details, please refer to the [pipeline documentation](docs/pipeline/README.md).


## Tutorials
To get started with AymurAI, refer to our [tutorials](tutorials/GET_STARTED.md). These guides provide step-by-step instructions on setting up and using the AymurAI backend, including configuration, example queries, and more.


## Contributing
Thank you for your interest in contributing to AymurAI! There are many ways to get involved, from improving documentation to enhancing the codebase. To get started, please review our [contributor guidelines](docs/CONTRIBUTING.md) and our [code of conduct](docs/CODE_OF_CONDUCT.md). We welcome contributions in areas such as expanding the API and improving the data processing pipeline.


## Contributors
* **Julián Ansaldo** - [@jansaldo](https://github.com/jansaldo) at [collective.ai](https://collectiveai.io) ([email](mailto:juli@collectiveai.io))
* **Raúl Barriga** - [@jedzill4](https://github.com/jedzill4) at [collective.ai](https://collectiveai.io) ([email](mailto:r@collectiveai.io))


## Citing AymurAI
If you use AymurAI in your research or any publication, please cite the following paper to acknowledge our work:

```bibtex
@techreport{feldfeber2022,
    author      = "Feldfeber, Ivana and Quiroga, Yasmín Belén  and Guevara, Clarissa  and Ciolfi Felice, Marianela",
    title       = "Feminisms in Artificial Intelligence: Automation Tools towards a Feminist Judiciary Reform in Argentina and Mexico",
    institution = "DataGenero",
    year        = "2022",
    url         = "https://drive.google.com/file/d/1P-hW0JKXWZ44Fn94fDVIxQRTExkK6m4Y/view"
}
```
Proper citation helps us continue developing AymurAI and supporting the community.


## License
AymurAI is open-source software licensed under the [MIT License](LICENSE.md). This license allows for modification, distribution, and private use, provided that appropriate credit is given to the original authors.
