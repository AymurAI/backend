# AymurAI
Idioma: [English](README.md) | **Español**

AymurAI provee una aplicación integrada, una API y pipelines de ML para procesar resoluciones judiciales mediante dos flujos principales:

- `anonymizer`: extracción de entidades y generación de documentos anonimizados.
- `data-public`: extracción de información estructurada para curación de dataset público.

Este repositorio contiene el frontend React/Electron, el servicio FastAPI, las configuraciones de pipelines de producción y la persistencia en base de datos para ambos flujos.

## Qué es AymurAI
AymurAI es un proyecto orientado a facilitar la generación de datos judiciales anonimizados y estructurados para casos de violencia de género (VG) en América Latina. La aplicación guía la ingesta de documentos, la inferencia de modelos, la revisión manual, la validación y la exportación de resultados para usos operativos y de investigación.

El frontend puede ejecutarse como aplicación web servida por FastAPI o como aplicación de escritorio Electron. Permite cargar y previsualizar documentos, revisar anotaciones, configurar políticas de entidades, exportar documentos anonimizados y validar datasets estructurados.

## Documentación
- Índice técnico: [docs/es/README.md](docs/es/README.md)
- Referencia de API: [docs/es/api/README.md](docs/es/api/README.md)
- Índice de pipelines: [docs/es/pipelines/README.md](docs/es/pipelines/README.md)
- Flujo anonymizer: [docs/es/pipelines/anonymizer/README.md](docs/es/pipelines/anonymizer/README.md)
- Flujo datapublic: [docs/es/pipelines/datapublic/README.md](docs/es/pipelines/datapublic/README.md)
- Esquema de base de datos interna: [docs/es/database/README.md](docs/es/database/README.md)
- Desarrollo y empaquetado del frontend: [frontend/README.md](frontend/README.md)

## Inicio Rápido (imagen Docker)
Ejecutar la imagen full de la API (incluye recursos de producción):

```bash
docker run -d --name aymurai-backend -p 8899:8899 ghcr.io/aymurai/api:full
```

Opcional: persistir DB/cache fuera del container (volumen host montado en `/resources/cache`):

```bash
mkdir -p ./aymurai-cache

docker run -d --name aymurai-backend -p 8899:8899 \
  -v "$(pwd)/aymurai-cache:/resources/cache" \
  ghcr.io/aymurai/api:full
```

Opcional: runtime con GPU (requiere NVIDIA Container Toolkit):

```bash
docker run -d --name aymurai-backend-gpu --gpus all \
  -e TORCH_DEVICE=cuda \
  -p 8899:8899 \
  ghcr.io/aymurai/api:full
```

Abrir Swagger UI:

```text
http://localhost:8899/api/docs
```

Abrir el frontend integrado:

```text
http://localhost:8899/
```

## Inicio Rápido (Docker Compose)
Usar los servicios definidos en `docker-compose.yml`:

```bash
# CPU, perfil liviano
make api-up

# CPU, perfil full
make api-full-up

# GPU, perfil liviano
API_SERVICE=aymurai-api-gpu make api-up

# GPU, perfil full
API_FULL_SERVICE=aymurai-api-full-gpu make api-full-up
```

Ver logs:

```bash
make api-logs
# o make api-full-logs
```

## Resumen de runtime
- Framework: `FastAPI`
- Puerto por defecto: `8899`
- Ruta del frontend integrado: `GET /`
- Implementaciones del frontend: navegador y Electron
- Motor de DB: `SQLModel` + migraciones Alembic al iniciar
- URI de DB por defecto: `sqlite:////resources/cache/sqlite/database.db`
- Configs de pipeline de producción:
  - `resources/pipelines/production/flair-anonymizer/pipeline.json`
  - `resources/pipelines/production/datapublic/pipeline.json`

## Endpoints públicos principales
- `GET /api/server/healthcheck`
- `GET /api/server/stats/summary`
- `POST /api/misc/document-extract` (y alias deprecado `POST /api/document-extract`)
- `POST /api/anonymizer/predict`
- `POST /api/anonymizer/disambiguate`
- `POST /api/anonymizer/validation`
- `POST /api/anonymizer/anonymize-document`
- `POST /api/datapublic/predict/{document_id}`
- `GET /api/datapublic/validation/document/{document_id}`
- `POST /api/datapublic/validation/document/{document_id}`

Para contratos request/response y ejemplos completos, ver [docs/es/api/README.md](docs/es/api/README.md).

## Despliegue en red cerrada
Para mover una imagen a un entorno sin internet:

```bash
docker image save ghcr.io/aymurai/api:full -o aymurai-api-full.tar
docker load -i aymurai-api-full.tar
```

## Contribución
Las contribuciones son bienvenidas en documentación, API y mejoras de pipelines.

- Guía de contribución: [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md)
- Seguridad y ética: [docs/SECURITY.md](docs/SECURITY.md)
- Código de conducta: [docs/CODE_OF_CONDUCT.md](docs/CODE_OF_CONDUCT.md)

## Contribuidores
- **Julián Ansaldo** - [@jansaldo](https://github.com/jansaldo) at [collective.ai](https://collectiveai.io) ([email](mailto:juli@collectiveai.io))
- **Raúl Barriga** - [@jedzill4](https://github.com/jedzill4) at [collective.ai](https://collectiveai.io) ([email](mailto:r@collectiveai.io))
- **Sofía del Pozo** - [@sofiadelpozo](https://github.com/sofiadelpozo) at [collective.ai](https://collectiveai.io) ([email](mailto:sofia.delpozo@collectiveai.io))
- **Paolo Donizetti** - [@padonizetti](https://github.com/padonizetti) at [collective.ai](https://collectiveai.io) ([email](mailto:paolo@collectiveai.io))
- **Conrado Beatriz** - [@conrabeatriz](https://github.com/conrabeatriz) at [collective.ai](https://collectiveai.io) ([email](mailto:conrado@collectiveai.io))
- **Lionel Chamorro** - [@lionelchamorro](https://github.com/lionelchamorro) at [collective.ai](https://collectiveai.io) ([email](mailto:lio@collectiveai.io))
- **Damián Mazzini** - [@
dmazzini](https://github.com/dmazzini) at [collective.ai](https://collectiveai.io) ([email](mailto:dami@collectiveai.io))

## Citar AymurAI
Si usás AymurAI en investigación o publicaciones, por favor citá:

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

Para usar la cita más actualizada, consulta la referencia del proyecto en el repositorio de la organización: [github.com/aymurai](https://github.com/aymurai).

## Licencia
AymurAI es software de código abierto bajo licencia [MIT](LICENSE.md). Esta licencia permite modificar, distribuir y usar de forma privada el software, siempre que se mantenga el crédito correspondiente a la autoría original.
