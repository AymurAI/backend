# Entidades de Datapublic
Idioma: [English](../../../entities/datapublic/README.md) | **Español**

Catálogo de entidades utilizadas por el flujo de extracción de datapublic.

## Alcance
Estas entidades corresponden a la taxonomía extraída de resoluciones judiciales por el pipeline de producción `datapublic`. Se usan a lo largo del modelo Flair NER, el postprocesamiento de decisiones, la UI de validación y el tooling relacionado con el dataset.

## Entidades
| Entidad | Descripción |
|---|---|
| `ART_INFRINGIDO` | Artículo(s) o norma(s) legal(es) infringida(s) en el caso. |
| `CONDUCTA` | Acción asociada al delito, contravención o falta descripta en el artículo infringido. |
| `CONDUCTA_DESCRIPCION` | Caracterización adicional de la conducta, como agravantes o detalles de modalidad. |
| `DECISION` | Fragmento de texto que denota una decisión judicial. En producción es una label sintética emitida por el clasificador de decisiones. |
| `DETALLE` | Detalle que especifica qué se resolvió dentro de `OBJETO_DE_LA_RESOLUCION`. |
| `EDAD_AL_MOMENTO_DEL_HECHO` | Edad de la persona al momento del hecho. |
| `FECHA_DE_NACIMIENTO` | Fecha de nacimiento. |
| `FECHA_DEL_HECHO` | Fecha en que ocurrió el hecho denunciado. |
| `FECHA_RESOLUCION` | Fecha de la resolución; en audiencias orales, la fecha de inicio de la audiencia. |
| `FRASES_AGRESION` | Frases citadas o parafraseadas como agresión verbal dentro de los hechos del caso. |
| `GENERO` | Género. |
| `HIJOS_HIJAS_EN_COMUN` | Si la persona acusada y la denunciante tienen hijos/as en común. |
| `HORA_DE_CIERRE` | Hora de finalización de la audiencia. |
| `HORA_DE_INICIO` | Hora de inicio de la audiencia. |
| `LUGAR_DEL_HECHO` | Lugar físico o mediado donde ocurrieron los hechos. |
| `MODALIDAD_DE_LA_VIOLENCIA` | Modalidad en la que se manifiesta la violencia, como violencia doméstica, institucional, laboral, mediática o en espacio público. |
| `N_EXPTE_EJE` | Identificador del expediente o caso. |
| `NACIONALIDAD` | Nacionalidad. |
| `NIVEL_INSTRUCCION` | Nivel de estudios formales alcanzado por la persona. |
| `NOMBRE` | Nombre de persona. |
| `OBJETO_DE_LA_RESOLUCION` | Sobre qué resolvió el juzgado. |
| `PERSONA_ACUSADA_NO_DETERMINADA` | Parte acusada no determinada o no humana, como una persona jurídica o una cuenta en línea. |
| `RELACION_Y_TIPO_ENTRE_ACUSADO/A_Y_DENUNCIANTE` | Tipo de vínculo entre la persona acusada y la denunciante. |
| `TIPO_DE_RESOLUCION` | Tipo de resolución, como interlocutoria o definitiva. |
| `VIOLENCIA_DE_GENERO` | Si los hechos investigados ocurren en un contexto de violencia de género. |

## Subcategorías y campos de validación
- Muchas de estas entidades tienen subclasificaciones o vocabularios controlados específicos para validación.
- Las opciones históricas de validación están capturadas en el template de Label Studio: [../../../../resources/annotations/label-studio/datapublic/label-studio-config.xml](../../../../resources/annotations/label-studio/datapublic/label-studio-config.xml)
- Un glosario explicativo más amplio está disponible aquí: https://docs.google.com/document/d/123B9T2abCEqBaxxOl5c7HBJZRdIMtKDWo6IKHIVil04/edit

## Documentación relacionada
- Índice de entidades: [../README.md](../README.md)
- Pipeline datapublic: [../../pipelines/datapublic/README.md](../../pipelines/datapublic/README.md)
- Model card de Decision: [../../models/decision-model-card.md](../../models/decision-model-card.md)
- Model card de Flair: [../../models/flair-model-card.md](../../models/flair-model-card.md)
