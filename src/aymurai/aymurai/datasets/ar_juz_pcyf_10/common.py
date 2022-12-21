# BASE = "https://docs.google.com/spreadsheets/d/1uAi-Yfq-rJl_cqQaVe9Fv1rLlBJcmEtDpUB0NTOrLAs/export?format=csv"
# VALIDATION_FIELDS = "https://docs.google.com/spreadsheets/d/1uAi-Yfq-rJl_cqQaVe9Fv1rLlBJcmEtDpUB0NTOrLAs/gviz/tq?tqx=out:csv&sheet=Listados%20de%20Validaci%C3%B3n"
BASE = (
    "/resources/data/dump-20221027/set_de_datos_con_perspectiva_de_genero-database.csv"
)
VALIDATION_FIELDS = "/resources/data/dump-20221027/set_de_datos_con_perspectiva_de_genero-listado_validacion.csv"


NAMED_DATASETS = ["latest", "08-2022", "private"]


FIELDS = {
    "nro_registro": "string",
    "tomo": "int32",
    # "date": "date",
    "date": "string",
    # "fecha_resolucion": "string",
    "n_expte_eje": "string",
    "firma": "string",
    "materia": "string",
    "art_infringido": "string",
    "codigo_o_ley": "string",
    "conducta": "string",
    "conducta_descripcion": "string",
    "violencia_de_genero": "bool",
    "v_fisica": "bool",
    "v_psic": "bool",
    "v_econ": "bool",
    "v_sex": "bool",
    "v_soc": "bool",
    "v_amb": "bool",
    "v_simb": "bool",
    "v_polit": "bool",
    "modalidad_de_la_violencia": "string",
    "frases_agresion": "string",
    "genero_acusado/a": "string",
    "persona_acusada_no_determinada": "string",
    "nacionalidad_acusado/a": "string",
    "edad_acusado/a al momento del hecho": "string",
    "nivel_instruccion_acusado/a": "string",
    "genero_denunciante": "string",
    "nacionalidad_denunciante": "string",
    "edad_denunciante_al_momento_del_hecho": "string",
    "nivel_instruccion_denunciante": "string",
    # "domicilio_denunciante": "string",
    # "asentamiento_o_villa": "string",
    "frecuencia_episodios": "string",
    "relacion_y_tipo_entre_acusado/a_y_denunciante": "string",
    "hijos_hijas_en_comun": "string",
    "medidad_de_proteccion_vigentes_al_momento_del_hecho": "string",
    "zona_del_hecho": "string",
    "lugar_del_hecho": "string",
    "tipo_de_resolucion": "string",
    "objeto_de_la_resolucion": "string",
    "detalle": "string",
    "decision": "string",
    "oral_escrita": "string",
    "hora_de_inicio": "string",
    "hora_de_cierre": "string",
    "duracion": "string",
    "link": "string",
}
