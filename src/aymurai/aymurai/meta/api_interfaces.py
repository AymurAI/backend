from typing import List, Optional

from pydantic import Field, BaseModel


class TextRequest(BaseModel):
    """Datatype for a text span request"""

    text: str = Field(
        ...,
        description="text field to run prediction",
    )


class DocLabelAttributes(BaseModel):
    """Datatype for a label's  attributes"""

    aymurai_label: str = Field(title="AymurAI label")
    aymurai_label_subclass: Optional[list[str]] = Field(
        description="AymurAI label subcategory"
    )
    aymurai_alt_text: Optional[str] = Field(
        description="alternative form for text formating (i.e. datetimes)"
    )
    aymurai_method: Optional[str] = Field("method used on the prediction label")
    aymurai_score: Optional[float] = Field("score for prediction")


class DocLabel(BaseModel):
    """Datatype for a document label"""

    text: str = Field(description="raw text of entity")
    start_char: int = Field(
        description="start character of the span in relation of the full text"
    )
    end_char: int = Field(
        description="last character of the span in relation of the full text"
    )
    attrs: DocLabelAttributes


class DocumentInformation(BaseModel):
    """Datatype for a document information with all labels"""

    document: str = Field(description="processed text")
    labels: List[DocLabel]


class Document(BaseModel):
    document: str


class AymuraiRecord(BaseModel):
    NRO_REGISTRO: str = Field("s/d")
    TOMO: str = Field("s/d")
    N_EXPTE_EJE: str = Field("s/d")
    FIRMA: str = Field("s/d")
    MATERIA: str = Field("s/d")
    ART_INFRINGIDO: str = Field("s/d")
    CODIGO_O_LEY: str = Field("s/d")
    CONDUCTA: str = Field("s/d")
    CONDUCTA_DESCRIPCION: str = Field("s/d")
    VIOLENCIA_DE_GENERO: str = Field("s/d")
    V_FISICA: str = Field("s/d")
    V_PSIC: str = Field("s/d")
    V_ECON: str = Field("s/d")
    V_SEX: str = Field("s/d")
    V_SOC: str = Field("s/d")
    V_AMB: str = Field("s/d")
    V_SIMB: str = Field("s/d")
    V_POLIT: str = Field("s/d")
    MODALIDAD_DE_LA_VIOLENCIA: str = Field("s/d")
    FRASES_AGRESION: str = Field("s/d")
    # GENERO_ACUSADO/A: str = Field('s/d')
    PERSONA_ACUSADA_NO_DETERMINADA: str = Field("s/d")
    # NACIONALIDAD_ACUSADO/A: str = Field('s/d')
    # EDAD_ACUSADO/A AL MOMENTO DEL HECHO: str = Field('s/d')
    # NIVEL_INSTRUCCION_ACUSADO/A: str = Field('s/d')
    GENERO_DENUNCIANTE: str = Field("s/d")
    NACIONALIDAD_DENUNCIANTE: str = Field("s/d")
    EDAD_DENUNCIANTE_AL_MOMENTO_DEL_HECHO: str = Field("s/d")
    NIVEL_INSTRUCCION_DENUNCIANTE: str = Field("s/d")
    FRECUENCIA_EPISODIOS: str = Field("s/d")
    # RELACION_Y_TIPO_ENTRE_ACUSADO/A_Y_DENUNCIANTE: str = Field('s/d')
    HIJOS_HIJAS_EN_COMUN: str = Field("s/d")
    MEDIDAD_DE_PROTECCION_VIGENTES_AL_MOMENTO_DEL_HECHO: str = Field("s/d")
    ZONA_DEL_HECHO: str = Field("s/d")
    LUGAR_DEL_HECHO: str = Field("s/d")
    TIPO_DE_RESOLUCION: str = Field("s/d")
    OBJETO_DE_LA_RESOLUCION: str = Field("s/d")
    DETALLE: str = Field("s/d")
    DECISION: str = Field("s/d")
    ORAL_ESCRITA: str = Field("s/d")
    HORA_DE_INICIO: str = Field("s/d")
    HORA_DE_CIERRE: str = Field("s/d")
    DURACION: str = Field("s/d")


class DocRecord(BaseModel):
    row: AymuraiRecord
