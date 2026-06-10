# Entidades de Anonymizer
Idioma: [English](../../../entities/anonymizer/README.md) | **Español**

Catálogo de labels usadas actualmente por el flujo de anonimización.

## Alcance
Estas labels representan los tipos de entidad reconocidos y transformados por el pipeline de producción `flair-anonymizer`. Son las labels sobre las que operan la desambiguación, las políticas de anonimización y las políticas de renderizado.

## Labels
| Label | Descripción |
|---|---|
| `PER` | Nombre de persona o mención de persona. |
| `EDAD` | Edad. |
| `DNI` | Número de documento nacional de identidad argentino. |
| `NACIONALIDAD` | Nacionalidad. |
| `ESTUDIOS` | Estudios o nivel educativo. |
| `DIRECCION` | Dirección postal o calle. |
| `LOC` | Ubicación geográfica o referencia de lugar. |
| `TELEFONO` | Número de teléfono. |
| `CORREO_ELECTRONICO` | Dirección de correo electrónico. |
| `FECHA` | Fecha calendario. |
| `NUM_EXPEDIENTE` | Número de expediente o causa. |
| `CUIJ` | Identificador judicial único de causa. |
| `NUM_ACTUACION` | Número de actuación. |
| `NUM_MATRICULA` | Número de matrícula o licencia profesional. |
| `NOMBRE_ARCHIVO` | Nombre de archivo. |
| `TEXTO_ANONIMIZAR` | Fragmento de texto libre marcado explícitamente para anonimización cuando no encaja en una label estructurada más específica. |
| `USUARIX` | Nombre de usuario, handle o identificador de cuenta. |
| `LINK` | URL o enlace web. |
| `IP` | Dirección IP. |
| `CUIT_CUIL` | Identificador tributario o laboral argentino. |
| `BANCO` | Nombre de entidad bancaria. |
| `CBU` | Clave Bancaria Uniforme argentina. |
| `NUM_CAJA_AHORRO` | Número de caja de ahorro. |
| `MARCA_AUTOMOVIL` | Referencia a marca o modelo de vehículo. |
| `PATENTE_DOMINIO` | Patente o dominio vehicular. |

## Notas
- Este catálogo refleja el conjunto actual de tokens de anonimización usado por las utilidades de reemplazo del backend.
- Cada label puede configurarse con políticas específicas de anonimización o desambiguación mediante `LabelPolicy`.

## Documentación relacionada
- Índice de entidades: [../README.md](../README.md)
- Pipeline anonymizer: [../../pipelines/anonymizer/README.md](../../pipelines/anonymizer/README.md)
- Referencia API: [../../api/README.md](../../api/README.md)
