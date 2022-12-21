AymurAI development
===================

# Run API
to run production api
```
docker run -p 8899:8000 --hostname=aymurai-api -d registry.gitlab.com/collective.ai/datagenero-public/aymurai-api:prod
```

# Setup
# Contenedores Docker
Este repositorio esta pensado para ser levantado dentro de un contenedor de desarrollo

## Jupyter
Para iniciar el ambiente de desarrollo con `gpu` a traves de Jupyter correr:
```bash
make jupyter-run
```
o equivalentemente
```bash
make jupyter-run-cpu
```
para correr en modo `cpu`


## Devcontainer (Recomendado)
Adicionalmente un `devcontainer`. Este puede ser levantado directamente desde Visual Studio Code.


## Ambiente de desarrollo
<div class="alert alert-danger">
    Para evitar subir datos sensibles en las notebooks por favor configurar pre-commits
</div>

***Inicializar la herramienta*** `precommit` ***para el control de sintaxis.***

```bash
pre-commit install
```

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
Estos documentos y sus anotaciones correspondientes no estan disponibles para el publico y se asumen presentes en formatos pdf y doc/docx en las carpetas seteadas por las variables de entorno `$AYMURAI_RESTRICTED_DOCUMENT_PDFS_PATH` y `$AYMURAI_RESTRICTED_DOCUMENT_PDFS_PATH` (ver `common.env` para ver los valores por defecto)
