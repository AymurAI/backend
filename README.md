# AymurAI Backend
Language: **English** | [Español](README.es.md)

AymurAI Backend provides the API and ML pipelines used to process judicial rulings for two main workflows:

- `anonymizer`: extract named entities and produce anonymized documents.
- `data-public`: extract structured information for public dataset curation.

This repository contains the FastAPI service, production pipeline configs, and database persistence used by both workflows.

## About AymurAI
AymurAI is a project focused on supporting the generation of anonymized and structured judicial data for gender-based violence (GBV) cases in Latin America. The backend service orchestrates document ingestion, ML inference, validation persistence, and document export for downstream operational and research uses.

This repository is backend-focused: it exposes APIs consumed by the frontend and runs the production pipelines for `anonymizer` and `data-public`.

## Documentation
- Technical docs index: [docs/README.md](docs/README.md)
- API reference: [docs/api/README.md](docs/api/README.md)
- Pipelines index: [docs/pipelines/README.md](docs/pipelines/README.md)
- Anonymizer flow: [docs/pipelines/anonymizer/README.md](docs/pipelines/anonymizer/README.md)
- Datapublic flow: [docs/pipelines/datapublic/README.md](docs/pipelines/datapublic/README.md)
- Internal database schema: [docs/database/README.md](docs/database/README.md)

## Quick Start (Docker Image)
Run the full API image (includes production resources):

```bash
docker run -d --name aymurai-backend -p 8899:8899 ghcr.io/aymurai/api:full
```

Optional: persist DB/cache outside the container (host volume mounted at `/resources/cache`):

```bash
mkdir -p ./aymurai-cache

docker run -d --name aymurai-backend -p 8899:8899 \
  -v "$(pwd)/aymurai-cache:/resources/cache" \
  ghcr.io/aymurai/api:full
```

Optional: GPU runtime (requires NVIDIA Container Toolkit):

```bash
docker run -d --name aymurai-backend-gpu --gpus all \
  -e TORCH_DEVICE=cuda \
  -p 8899:8899 \
  ghcr.io/aymurai/api:full
```

Open Swagger UI:

```text
http://localhost:8899/docs
```

## Quick Start (Docker Compose)
Use the services defined in `docker-compose.yml`:

```bash
# CPU, lightweight API profile
make api-up

# CPU, full API profile
make api-full-up

# GPU, lightweight API profile
API_SERVICE=aymurai-api-gpu make api-up

# GPU, full API profile
API_FULL_SERVICE=aymurai-api-full-gpu make api-full-up
```

Check logs:

```bash
make api-logs
# or make api-full-logs
```

## Runtime Overview
- Framework: `FastAPI`
- Default API port: `8899`
- DB engine: `SQLModel` + Alembic migrations on startup
- Default DB URI: `sqlite:////resources/cache/sqlite/database.db`
- Production pipeline configs:
  - `resources/pipelines/production/flair-anonymizer/pipeline.json`
  - `resources/pipelines/production/full-paragraph/pipeline.json`

## Main Public Endpoints
- `GET /server/healthcheck`
- `GET /server/stats/summary`
- `POST /misc/document-extract` (and deprecated alias `POST /document-extract`)
- `POST /anonymizer/predict`
- `POST /anonymizer/disambiguate`
- `POST /anonymizer/validation`
- `POST /anonymizer/anonymize-document`
- `POST /datapublic/predict/{document_id}`
- `GET /datapublic/validation/document/{document_id}`
- `POST /datapublic/validation/document/{document_id}`

For full request/response contracts and examples, see [docs/api/README.md](docs/api/README.md).

## Closed-Network Deployment
To move an image into a closed environment:

```bash
docker image save ghcr.io/aymurai/api:full -o aymurai-api-full.tar
docker load -i aymurai-api-full.tar
```

## Contributing
Contributions are welcome across documentation, API, and pipeline improvements.

- Contributing guide: [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md)
- Security and ethics: [docs/SECURITY.md](docs/SECURITY.md)
- Code of conduct: [docs/CODE_OF_CONDUCT.md](docs/CODE_OF_CONDUCT.md)

## Contributors
- **Julián Ansaldo** - [@jansaldo](https://github.com/jansaldo) at [collective.ai](https://collectiveai.io) ([email](mailto:juli@collectiveai.io))
- **Raúl Barriga** - [@jedzill4](https://github.com/jedzill4) at [collective.ai](https://collectiveai.io) ([email](mailto:r@collectiveai.io))
- **Sofía del Pozo** - [@sofiadelpozo](https://github.com/sofiadelpozo) at [collective.ai](https://collectiveai.io) ([email](mailto:sofia.delpozo@collectiveai.io))
- **Paolo Donizetti** - [@padonizetti](https://github.com/padonizetti) at [collective.ai](https://collectiveai.io) ([email](mailto:paolo@collectiveai.io))
- **Conrado Beatriz** - [@conrabeatriz](https://github.com/conrabeatriz) at [collective.ai](https://collectiveai.io) ([email](mailto:conrado@collectiveai.io))


## Citing AymurAI
If you use AymurAI in research or publications, please cite:

```bibtex
@techreport{feldfeber2022,
  author      = {Feldfeber, Ivana and Quiroga, Yasm\'{\i}n Bel\'{e}n and Guevara, Clarissa and Ciolfi Felice, Marianela},
  title       = {Feminisms in Artificial Intelligence: Automation Tools towards a Feminist Judiciary Reform in Argentina and Mexico},
  institution = {DataGenero},
  year        = {2022},
  url         = {https://drive.google.com/file/d/1P-hW0JKXWZ44Fn94fDVIxQRTExkK6m4Y/view}
}
```

```
@inproceedings{10.1145/3706598.3713681,
  author    = {Ciolfi Felice, Marianela and Feldfeber, Ivana and Glasserman Apicella, Carolina and Quiroga, Yasm\'{\i}n Bel\'{e}n and Ansaldo, Juli\'{a}n and Lapenna, Luciano and Bezchinsky, Santiago and Barriga Rubio, Ra\'{u}l and Garc\'{\i}a, Mail\'{e}n},
  title     = {Doing the Feminist Work in AI: Reflections from an AI Project in Latin America},
  booktitle = {Proceedings of the 2025 CHI Conference on Human Factors in Computing Systems},
  series    = {CHI '25},
  year      = {2025},
  isbn      = {9798400713941},
  publisher = {Association for Computing Machinery},
  address   = {New York, NY, USA},
  doi       = {10.1145/3706598.3713681},
  url       = {https://doi.org/10.1145/3706598.3713681},
  abstract  = {The contemporary AI development landscape is dominated by big corporations, lacks diversity, and mostly centres the Global North, or applies extractivist logics in the South. This paper showcases a feminist process of AI development from Latin America, where we created an interactive, AI-powered tool that helps criminal court officers open justice data, addressing a data gap on gender-based violence. Through a collaborative autoethnography, drawing from Latin American feminisms, we unpack and visibilize the feminist work that was required, as a crucial step to counter hegemonic narratives. Foregrounding the subjugated knowledges of our experiences, we offer a concrete example of a feminist approach to AI development grounded in practice. With this, we aim to critically inspire those who consider building technology in service of social justice causes, or who choose to build AI systems otherwise.},
  articleno = {998},
  numpages  = {18},
  keywords  = {Global South, NGO, activism, critical HCI, critical computing, duoethnography, feminist AI, feminist research},
  location  = {},
}
```

For the most up-to-date citation, please use the project-level reference in the organization repository: [github.com/aymurai](https://github.com/aymurai).

## License
AymurAI is open-source software licensed under the [MIT License](LICENSE.md). This license allows modification, distribution, and private use, provided that appropriate credit is given to the original authors.
