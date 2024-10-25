from enum import Enum


class Materia(str, Enum):
    PENAL = "penal"
    CONTRAVENCIONAL = "contravencional"
    FALTAS = "faltas"
    AMPARO = "amparo"
    HABEAS_CORPUS = "habeas corpus"
    EJECUCIONES_DE_MULTA = "ejecuciones de multa"


class Violencia(str, Enum):
    SI = "si"
    NO = "no"
    SD = "s/d"
    NO_CORRESPONDE = "no_corresponde"


class ModalidadViolencia(str, Enum):
    DOMESTICA = "doméstica"
    INSTITUCIONAL = "institucional"
    MEDIATICA = "mediática"
    LABORAL = "laboral"
    CONTRA_LIBERTAD_REPRODUCTIVA = "contra la libertad reproductiva"
    OBSTETRICA = "obstétrica"
    ESPACIO_PUBLICO_PRIVADO = "en espacio público o privado"
    POLITICA_PUBLICA = "política y pública"
    DIGITAL = "digital"


class Genero(str, Enum):
    VARON_CIS = "varon_cis"
    MUJER_CIS = "mujer_cis"
    MUJER_TRANS = "mujer_trans"
    TRAVESTI = "travesti"
    VARON_TRANS = "varon_trans"
    NO_BINARIA = "no_binaria"
    NO_CORRESPONDE = "no_corresponde"
    NO_RESPONDE = "no_responde"


class FrecuenciaEpisodios(str, Enum):
    ESPORADICO = "esporádico"
    DIARIO = "diario"
    HABITUAL = "habitual"
    EVENTUAL = "eventual"
    PRIMERA_AGRESION = "primera agresión"


class TipoResolucion(str, Enum):
    INTERLOCUTORIA = "interlocutoria"
    DEFINITIVA = "definitiva"


class OralEscrita(str, Enum):
    ORAL = "oral"
    ESCRITA = "escrita"
