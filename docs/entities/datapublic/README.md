# Datapublic Entities
Language: **English** | [Español](../../es/entities/datapublic/README.md)

Catalog of entities used by the datapublic extraction flow.

## Scope
These entities correspond to the taxonomy extracted from judicial rulings by the production `datapublic` pipeline. They are used across the Flair NER model, decision post-processing, validation UI, and related dataset tooling.

## Entities
| Entity | Description |
|---|---|
| `ART_INFRINGIDO` | Article(s) or legal provision(s) infringed in the case. |
| `CONDUCTA` | Action associated with the offence, contravention, or misdemeanor described in the infringed article. |
| `CONDUCTA_DESCRIPCION` | Additional characterization of the conduct, such as aggravating circumstances or modality details. |
| `DECISION` | Text fragment denoting a judicial decision. In production this is a synthetic label emitted by the decision classifier. |
| `DETALLE` | Detail that specifies what was resolved within `OBJETO_DE_LA_RESOLUCION`. |
| `EDAD_AL_MOMENTO_DEL_HECHO` | Age of the person at the time of the event. |
| `FECHA_DE_NACIMIENTO` | Date of birth. |
| `FECHA_DEL_HECHO` | Date on which the reported event occurred. |
| `FECHA_RESOLUCION` | Date of the resolution; for oral hearings, the hearing start date. |
| `FRASES_AGRESION` | Quoted or paraphrased phrases described as verbal aggression within the facts of the case. |
| `GENERO` | Gender. |
| `HIJOS_HIJAS_EN_COMUN` | Whether the accused person and the complainant have children in common. |
| `HORA_DE_CIERRE` | End time of the hearing. |
| `HORA_DE_INICIO` | Start time of the hearing. |
| `LUGAR_DEL_HECHO` | Physical or mediated location where the facts occurred. |
| `MODALIDAD_DE_LA_VIOLENCIA` | Modality in which violence manifests, such as domestic, institutional, labor, media, or public-space violence. |
| `N_EXPTE_EJE` | Case or file identifier. |
| `NACIONALIDAD` | Nationality. |
| `NIVEL_INSTRUCCION` | Level of formal education attained by the person. |
| `NOMBRE` | Person name. |
| `OBJETO_DE_LA_RESOLUCION` | What the court resolved about. |
| `PERSONA_ACUSADA_NO_DETERMINADA` | Non-natural or undetermined accused party, such as a legal entity or online account. |
| `RELACION_Y_TIPO_ENTRE_ACUSADO/A_Y_DENUNCIANTE` | Relationship type between the accused person and the complainant. |
| `TIPO_DE_RESOLUCION` | Type of resolution, such as interlocutory or final resolution. |
| `VIOLENCIA_DE_GENERO` | Whether the investigated facts occur within a gender-violence context. |

## Subcategories and validation fields
- Many of these entities have subclassification or validation-specific controlled vocabularies.
- Historical validation options are captured in the Label Studio template: [../../../resources/annotations/label-studio/datapublic/label-studio-config.xml](../../../resources/annotations/label-studio/datapublic/label-studio-config.xml)
- A broader explanatory glossary is available here (Spanish): https://docs.google.com/document/d/123B9T2abCEqBaxxOl5c7HBJZRdIMtKDWo6IKHIVil04/edit

## Related docs
- Entities index: [../README.md](../README.md)
- Datapublic pipeline: [../../pipelines/datapublic/README.md](../../pipelines/datapublic/README.md)
- Decision model card: [../../models/decision-model-card.md](../../models/decision-model-card.md)
- Flair model card: [../../models/flair-model-card.md](../../models/flair-model-card.md)
