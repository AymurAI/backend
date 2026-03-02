# Anonymizer Entities
Language: **English** | [Español](../../es/entities/anonymizer/README.md)

Catalog of labels currently used by the anonymization flow.

## Scope
These labels represent the entity types recognized and transformed by the production `flair-anonymizer` pipeline. They are the labels on which disambiguation, anonymization policies, and render policies operate.

## Labels
| Label | Description |
|---|---|
| `PER` | Person name or person mention. |
| `EDAD` | Age. |
| `DNI` | Argentine national identity document number. |
| `NACIONALIDAD` | Nationality. |
| `ESTUDIOS` | Education or level of studies. |
| `DIRECCION` | Postal or street address. |
| `LOC` | Geographic location or place reference. |
| `TELEFONO` | Phone number. |
| `CORREO_ELECTRONICO` | Email address. |
| `FECHA` | Calendar date. |
| `NUM_EXPEDIENTE` | Case or file number. |
| `CUIJ` | Judicial unique case identifier. |
| `NUM_ACTUACION` | Proceeding or action number. |
| `NUM_MATRICULA` | Registration or professional license number. |
| `NOMBRE_ARCHIVO` | File name. |
| `TEXTO_ANONIMIZAR` | Free-form text span explicitly marked for anonymization when it does not fit a more specific structured label. |
| `USUARIX` | Username, account handle, or user identifier. |
| `LINK` | URL or web link. |
| `IP` | IP address. |
| `CUIT_CUIL` | Argentine tax or labor identifier. |
| `BANCO` | Bank name. |
| `CBU` | Argentine bank account CBU. |
| `NUM_CAJA_AHORRO` | Savings account number. |
| `MARCA_AUTOMOVIL` | Vehicle make or model reference. |
| `PATENTE_DOMINIO` | Vehicle license plate. |

## Notes
- This catalog reflects the current anonymization token set used by the backend replacement utilities.
- Individual labels may be configured with per-label anonymization or disambiguation policies through `LabelPolicy`.

## Related docs
- Entities index: [../README.md](../README.md)
- Anonymizer pipeline: [../../pipelines/anonymizer/README.md](../../pipelines/anonymizer/README.md)
- API reference: [../../api/README.md](../../api/README.md)
