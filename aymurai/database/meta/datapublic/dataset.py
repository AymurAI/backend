import uuid
from typing import TYPE_CHECKING
from datetime import date, time, timedelta

from sqlmodel import Field, SQLModel, Relationship
from pydantic import field_validator, model_validator

from aymurai.text.normalize import document_normalize

from .categories import (
    Genero,
    Materia,
    Violencia,
    OralEscrita,
    TipoResolucion,
    ModalidadViolencia,
    FrecuenciaEpisodios,
)

if TYPE_CHECKING:
    from aymurai.database.meta.datapublic.document import DataPublicDocument


class DataPublicDatasetBase(SQLModel):
    id: uuid.UUID | None = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        description="Número único dentro del Set de Datos.",
    )
    nro_registro: int | None = Field(
        None, description="Número de registro interno del Juzgado para cada resolución."
    )
    fecha_resolucion: date | None = Field(
        None, description="Fecha en que se dictó la resolución."
    )
    n_expte_eje: int | None = Field(
        None, description="Número de expediente asignado en el sistema EJE."
    )
    cuij: str | None = Field(None, description="Número asignado por el sistema EJE.")
    firma: str | None = Field(None, description="Juez/a que firmó la resolución.")
    materia: Materia | None = Field(
        None, description="Competencia del Juzgado para intervenir en los casos."
    )
    art_infringido: str | None = Field(
        None, description="Artículo/s del código infringido en el caso."
    )
    codigo_o_ley: str | None = Field(
        None,
        description="Indica si el artículo pertenece a un código o ley específica.",
    )
    conducta: str | None = Field(
        None, description="Acción relativa al delito, contravención o falta."
    )
    conducta_descripcion: str | None = Field(
        None, description="Descripción detallada de la conducta, si aplica."
    )
    violencia_de_genero: bool | None = Field(
        None,
        description="Indica si el hecho está en un contexto de violencia de género.",
    )

    @field_validator("violencia_de_genero", mode="before")
    @classmethod
    def validate_violencia_de_genero(cls, v) -> bool:
        if isinstance(v, str):
            if v.lower() == "si":
                return True
            elif v.lower() == "no":
                return False

        return v

    v_fisica: Violencia | None = Field(
        None, description="Si hubo violencia física según la declaración de la víctima."
    )
    v_psic: Violencia | None = Field(
        None,
        description="Si hubo violencia psicológica según la declaración de la víctima.",
    )
    v_econ: Violencia | None = Field(
        None,
        description="Si hubo violencia económica o patrimonial según la declaración de la víctima.",
    )
    v_sex: Violencia | None = Field(
        None, description="Si hubo violencia sexual según la declaración de la víctima."
    )
    v_soc: Violencia | None = Field(
        None, description="Si hubo violencia social según la declaración de la víctima."
    )
    v_amb: Violencia | None = Field(
        None,
        description="Si hubo violencia ambiental según la declaración de la víctima.",
    )
    v_simb: Violencia | None = Field(
        None,
        description="Si hubo violencia simbólica según la declaración de la víctima.",
    )
    v_polit: Violencia | None = Field(
        None,
        description="Si hubo violencia política según la declaración de la víctima.",
    )
    modalidad_de_la_violencia: ModalidadViolencia | None = Field(
        None, description="Modalidad en que se manifiesta la violencia."
    )

    frases_agresion: str | None = Field(
        None, description="Transcripción de frases de agresión verbal reportadas."
    )
    genero_acusado_a: Genero | None = Field(
        None, description="Género de la persona acusada."
    )
    persona_acusada_no_determinada: str | None = Field(
        None,
        description="Indica si la persona acusada no está determinada o es una persona jurídica.",
    )
    nacionalidad_acusado_a: str | None = Field(
        None, description="Nacionalidad de la persona acusada."
    )
    edad_acusado_a_al_momento_del_hecho: int | None = Field(
        None, description="Edad de la persona acusada al momento del hecho."
    )
    nivel_de_instruccion_acusado_a: str | None = Field(
        None, description="Nivel educativo alcanzado por la persona acusada."
    )
    genero_denunciante: Genero | None = Field(
        None, description="Género de la persona denunciante."
    )
    nacionalidad_denunciante: str | None = Field(
        None, description="Nacionalidad de la persona denunciante."
    )
    edad_denunciante_al_momento_del_hecho: int | None = Field(
        None, description="Edad de la persona denunciante al momento del hecho."
    )
    nivel_de_instruccion_denunciante: str | None = Field(
        None, description="Nivel educativo alcanzado por la persona denunciante."
    )
    trabajo_remunerado_denunciante: bool | None = Field(
        None, description="Si la persona denunciante tiene trabajo remunerado."
    )
    nivel_de_ingresos_denunciante: float | None = Field(
        None, description="Nivel de ingresos mensuales de la persona denunciante."
    )
    domicilio_denunciante: str | None = Field(
        None, description="Zona de la ciudad donde reside la persona denunciante."
    )
    asentamiento_o_villa: bool | None = Field(
        None,
        description="Si la persona denunciante reside en un asentamiento o barrio popular.",
    )
    frecuencia_episodios: FrecuenciaEpisodios | None = Field(
        None, description="Frecuencia de los episodios de agresión."
    )
    relacion_y_tipo_entre_acusado_a_y_denunciante: str | None = Field(
        None, description="Relación o vínculo entre el acusado/a y el denunciante."
    )
    hijos_hijas_en_comun: bool | None = Field(
        None, description="Si el acusado/a y denunciante tienen hijos/as en común."
    )
    medidas_de_proteccion_vigentes_al_momento_del_hecho: bool | None = Field(
        None,
        description="Si había medidas de protección vigentes al momento del hecho.",
    )
    zona_del_hecho: str | None = Field(
        None, description="Zona geográfica donde ocurrieron los hechos."
    )
    lugar_del_hecho: str | None = Field(
        None, description="Lugar físico donde ocurrieron los hechos."
    )
    fecha_del_hecho: date | None = Field(
        None, description="Fecha en que se sucedió el primer hecho."
    )
    fecha_de_inicio_del_hecho: date | None = Field(
        None, description="Fecha de inicio del hecho en casos de delitos continuados."
    )
    fecha_de_finalizacion_de_hecho: date | None = Field(
        None,
        description="Fecha de finalización del hecho en casos de delitos continuados.",
    )
    tipo_de_resolucion: TipoResolucion | None = Field(
        None, description="Tipo de resolución emitida."
    )
    objeto_de_la_resolucion: str | None = Field(
        None, description="Objeto sobre el cual se resolvió."
    )
    detalle: str | None = Field(
        None, description="Detalle específico sobre la resolución."
    )
    decision: str | None = Field(None, description="Si se hizo lugar o no al planteo.")
    oral_escrita: OralEscrita | None = Field(
        None,
        description="Si la resolución fue dictada en audiencia (oral) o por escrito.",
    )
    hora_de_inicio: time | None = Field(
        None, description="Hora de inicio de la audiencia."
    )
    hora_de_cierre: time | None = Field(
        None, description="Hora de cierre de la audiencia."
    )
    duracion: timedelta | None = Field(
        None, description="Duración de la audiencia en horas."
    )
    link: str | None = Field(
        None, description="Enlace a la resolución en formato abierto."
    )

    @model_validator(mode="before")
    @classmethod
    def validate_fields(cls, data: dict) -> dict:
        for key, value in data.items():
            if isinstance(value, str):
                data[key] = document_normalize(value)

            if isinstance(value, str) and value in ["", "s/d", "no_corresponde"]:
                data[key] = None

        return data


class DataPublicDataset(DataPublicDatasetBase, table=True):
    __tablename__ = "datapublic_dataset"

    document_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="datapublic_document.id",
    )
    document: "DataPublicDocument" = Relationship(back_populates="dataset")


class DataPublicDatasetCreate(DataPublicDatasetBase):
    pass


class DataPublicDatasetRead(DataPublicDatasetBase):
    id: uuid.UUID | None


class DataPublicDatasetUpdate(DataPublicDatasetBase):
    pass
