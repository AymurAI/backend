import re
from functools import reduce, partial

from spacy.tokens import Span
from spacy.util import filter_spans

period_rules = [
    "segundo",
    "segundos",
    "minuto",
    "minutos",
    "hr",
    "hs",
    "hora",
    "horas",
    "año",
    "años",
    "dia",
    "día",
    "dias",
    "días",
    "mes",
    "meses",
]

law_left_nbors = [
    "ley",
    "leyes",
]

address_first_left_nbors = [
    "calle",
    "Calle",
    "dirección",
    "Dirección",
    "avenida",
    "av.",
    "Avenida",
    "Av.",
    "pasaje",
    "Pasaje",
    "Parcela",
    "parcela",
]

address_second_left_nbors = [
    "instalación",
    "contramano",
    "sita",
    "sitas",
    "sito",
    "sitos",
    "real",
    "domiciliado",
    "domiciliada",
    "constituido",
    "constituida",
    "contramano",
    "intersección",
    "domicilio",
    "ubicado",
    "registrado",
    "ubicada",
    "real",
]

address_connector = "en"

license_plate_left_nbor = [
    "patente",
    "dominio",
]

age_right_token = "años"
age_text_in_token = "edad"
number_abreviated_indicator = "nº"
case_first_left_token = "caso"
case_second_left_token = "causa"
cuij_indicator = "cuij"
actuacion_number_indicator = "nro"
actuacion_nbor_token = "actuación"
expediente_indicator = "expediente"

judge_lemma = ["juez", "jueza", "Juez", "Jueza"]
secretarix_lemma = [
    "secretario",
    "secretaria",
    "prosecretario",
    "prosecretaria",
    "Prosecretario",
    "Prosecretaria",
    "Secretario",
    "Secretaria",
]
prosecutor_lemma = ["fiscal", "fiscalía", "Fiscal", "Fiscalía"]
ombuds_person_lemma = ["defensor", "defensora", "Defensora", "Defensor"]
accused_lemma = [
    "acusado",
    "acusada",
    "imputado",
    "imputada",
    "infractor",
    "infractora",
    "Acusado",
    "Acusada",
    "Imputado",
    "Imputada",
    "Infractor",
    "Infractora",
]
advisor_lemma = ["asesor", "asesora", "Asesor", "Asesora"]
phone_lemma = ["teléfono", "tel", "celular", "número", "numerar", "telefónico"]
phone_text = ["telefono", "tel", "cel"]


def is_age(token):
    return (
        token.like_num
        and token.nbor(1).text == age_right_token
        and age_text_in_token in token.sent.text
    )


def is_caseNumber(token):
    return token.like_num and (
        (
            token.nbor(-1).lower_ == number_abreviated_indicator
            and token.nbor(-2).lower_ == case_second_left_token
        )
        or token.nbor(-1).lower_ == case_first_left_token
    )


def is_cuijNumber(token):
    return (token.is_ascii and token.nbor(-3).lower_ == cuij_indicator) or (
        token.like_num and token.nbor(-3).lower_ == cuij_indicator
    )


def is_actuacionNumber(token):
    return (
        token.nbor(-1).lower_ == ":"
        and token.nbor(-2).lower_ == actuacion_number_indicator
        and token.nbor(-3).lower_ == actuacion_nbor_token
    )


def is_expedienteNumber(token):
    return (
        token.nbor(-1).lower_ == number_abreviated_indicator
        and (
            token.nbor(-3).lower_ == expediente_indicator
            or token.nbor(-2).lower_ == expediente_indicator
        )
    ) or (token.like_num and token.nbor(-2).lower_ == expediente_indicator)


def is_place_token(token):
    # TODO Este enfoque puede generar falsos positivos
    first_left_nbors = [
        "asentamiento",
        "paraje",
        "localidad",
        "country",
        "distrito",
    ]

    return token.nbor(-1).lower_ in first_left_nbors


def is_law(ent):
    first_token = ent[0]
    return ent.label_ == "NUM" and (
        first_token.nbor(-1).lower_ in law_left_nbors
        or first_token.nbor(-2).lower_ in law_left_nbors
        or first_token.nbor(-3).lower_ in law_left_nbors
    )


def is_last(doc, token_id):
    return token_id == len(doc) - 1


def is_between_tokens(token_id, left=0, right=0):
    return token_id < right and token_id >= left


is_from_first_tokens = partial(is_between_tokens, left=0, right=3)


def is_judge(ent):
    first_token = ent[0]
    return ent.label_ in ["PER", "LOC"] and (
        first_token.nbor(-1).lemma_ in judge_lemma
        or first_token.nbor(-2).lemma_ in judge_lemma
        or first_token.nbor(-3).lemma_ in judge_lemma
    )


def is_period(ent):
    last_token = ent[len(ent) - 1]
    return ent.label_ in ["NUM"] and last_token.nbor(1).text in period_rules


def is_secretary(ent):
    first_token = ent[0]
    return ent.label_ in ["PER", "LOC"] and (
        first_token.nbor(-1).lemma_ in secretarix_lemma
        or first_token.nbor(-2).lemma_ in secretarix_lemma
        or first_token.nbor(-3).lemma_ in secretarix_lemma
    )


def is_prosecutor(ent):
    first_token = ent[0]
    return ent.label_ in ["PER", "LOC"] and (
        first_token.nbor(-1).lemma_ in prosecutor_lemma
        or first_token.nbor(-2).lemma_ in prosecutor_lemma
        or first_token.nbor(-3).lemma_ in prosecutor_lemma
    )


def is_ombuds_person(ent):
    first_token = ent[0]
    return ent.label_ in ["PER", "LOC"] and (
        first_token.nbor(-1).lemma_ in ombuds_person_lemma
        or first_token.nbor(-2).lemma_ in ombuds_person_lemma
        or first_token.nbor(-3).lemma_ in ombuds_person_lemma
    )


def is_accused(ent):
    first_token = ent[0]
    return ent.label_ in ["PER", "LOC"] and (
        first_token.nbor(-1).lemma_ in accused_lemma
        or first_token.nbor(-2).lemma_ in accused_lemma
        or first_token.nbor(-3).lemma_ in accused_lemma
    )


def is_advisor(ent):
    first_token = ent[0]
    return ent.label_ in ["PER", "LOC"] and (
        first_token.nbor(-1).lemma_ in advisor_lemma
        or first_token.nbor(-2).lemma_ in advisor_lemma
        or first_token.nbor(-3).lemma_ in advisor_lemma
    )


def is_ip_address(ent):
    octet_rx = r"(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)"
    pattern = re.compile(r"^{0}(?:\.{0}){{3}}$".format(octet_rx))
    is_ip = pattern.match(str(ent))
    return ent.label_ in ["NUM", "NUM_IP"] and is_ip


def is_phone(ent):
    first_token = ent[0]
    return ent.label_ == "NUM" and (
        first_token.nbor(-1).lemma_ in phone_lemma
        or first_token.nbor(-2).lemma_ in phone_lemma
        or first_token.nbor(-3).lemma_ in phone_lemma
        or first_token.nbor(-1).text in phone_text
        or first_token.nbor(-2).text in phone_text
        or (first_token.nbor(-1).text == "(" and first_token.nbor(1).text == ")")
    )


# TODO this function could be used in many methods, check it!
def is_token_in_x_left_pos(token, pos, nbors):
    try:
        return token.nbor(-pos).lower_ in nbors
    except Exception:
        return False


def is_address(ent):
    first_token = ent[0]
    last_token = ent[-1]
    address_1_tokens_to_left = is_token_in_x_left_pos(
        first_token, 1, address_first_left_nbors
    )
    address_2_tokens_to_left_first_nbors = is_token_in_x_left_pos(
        first_token, 2, address_first_left_nbors
    )
    address_2_tokens_to_left_second_nbors = is_token_in_x_left_pos(
        first_token, 2, address_second_left_nbors
    )
    address_3_tokens_to_left_first_nbors = is_token_in_x_left_pos(
        first_token, 3, address_first_left_nbors
    )
    address_3_tokens_to_left_second_nbors = is_token_in_x_left_pos(
        first_token, 3, address_second_left_nbors
    )
    address_4_tokens_to_left_first_nbors = is_token_in_x_left_pos(
        first_token, 4, address_first_left_nbors
    )
    address_4_tokens_to_left_second_nbors = is_token_in_x_left_pos(
        first_token, 4, address_second_left_nbors
    )

    is_address_from_PER = ent.label_ in ["PER"] and (
        address_1_tokens_to_left
        or address_2_tokens_to_left_second_nbors
        or last_token.like_num
        or last_token.nbor().like_num
    )

    is_address_from_NUM = ent.label_ in ["NUM"] and (
        address_1_tokens_to_left
        or address_2_tokens_to_left_first_nbors
        or address_2_tokens_to_left_second_nbors
        or address_3_tokens_to_left_first_nbors
        or address_3_tokens_to_left_second_nbors
        or address_4_tokens_to_left_first_nbors
        or address_4_tokens_to_left_second_nbors
    )

    return is_address_from_PER or is_address_from_NUM


def get_aditional_left_tokens_for_address(ent):
    if ent.label_ in ["PER"] and ent[-1].nbor().like_num:
        return 1
    if ent.label_ in ["NUM"]:
        token = ent[0]
        if token.nbor(-1).lower_ in address_first_left_nbors:
            return 1
        if (
            token.nbor(-2).lower_ in address_first_left_nbors
            or token.nbor(-2).lower_ in address_second_left_nbors
        ):
            return 2
        if token.nbor(-3).lower_ in address_first_left_nbors:
            return 3
        if token.nbor(-3).lower_ in address_second_left_nbors:
            return 2 - 1 if token.nbor(-2).lower_ == address_connector else 0
        if token.nbor(-4).lower_ in address_first_left_nbors:
            return 4
        if token.nbor(-4).lower_ in address_second_left_nbors:
            return 3 - 1 if token.nbor(-3).lower_ == address_connector else 0
    return 0


def get_entity_to_remove_if_contained_by(ent_start, ent_end, list_entities):
    for i, ent_from_list in enumerate(list_entities):
        if (
            ent_start >= ent_from_list.start
            and ent_start <= ent_from_list.end
            or ent_end >= ent_from_list.start
            and ent_end <= ent_from_list.end
        ):
            return ent_from_list
    return None


def generate_address_span(ent, new_ents, doc):
    address_token = get_aditional_left_tokens_for_address(ent)
    ent_start = ent.start - address_token
    ent_to_remove = get_entity_to_remove_if_contained_by(ent_start, ent.end, new_ents)
    if ent_to_remove:
        if (ent.end - ent_start) > (ent_to_remove.end - ent_to_remove.start):
            new_ents = remove_wrong_labeled_entity_span(new_ents, ent_to_remove)
            return Span(doc, ent_start, ent.end, label="DIRECCIÓN")

    return Span(doc, ent_start, ent.end, label="DIRECCIÓN")


def could_be_an_article(ent):
    token = ent[0]
    first_left_token = token.nbor(-1).lower_
    second_left_token = token.nbor(-2).lower_
    third_left_token = token.nbor(-3).lower_
    dont_consider = "bis"

    return (
        ent.label_ == "PATENTE_DOMINIO"
        and token.lower_.find(dont_consider) != -1
        and first_left_token not in license_plate_left_nbor
        and second_left_token not in license_plate_left_nbor
        and third_left_token not in license_plate_left_nbor
    )


def is_license_plate(ent):
    token = ent[0]
    first_left_token = token.nbor(-1).lower_
    second_left_token = token.nbor(-2).lower_
    third_left_token = token.nbor(-3).lower_

    return token.like_num and (
        first_left_token in license_plate_left_nbor
        or second_left_token in license_plate_left_nbor
        or third_left_token in license_plate_left_nbor
    )


def is_accused_or_advisor(ent):
    return is_accused(ent) or is_advisor(ent)


def get_start_end_license_plate(ent):
    token = ent[0]
    first_left_token = token.nbor(-1).lower_
    first_right_token = token.nbor(1).lower_
    if len(ent.text) != 3:  # this means it is not an "incomplete" license plate
        return ent.start, ent.end
    if len(first_left_token) == 3 and isinstance(first_left_token, str):
        # 3 letras - 3 núm
        return ent.start - 1, ent.end
    if (
        len(first_left_token) == 2
        and len(first_right_token) == 2
        and isinstance(first_left_token, str)
        and isinstance(first_right_token, str)
    ):
        # 2 letras - 3 núm - 2 letras
        return ent.start - 1, ent.end + 1
    if len(first_right_token) == 3 and isinstance(first_right_token, str):
        # 3 núm - 3 letras
        return ent.start, ent.end + 1


def remove_wrong_labeled_entity_span(ent_list, ent_to_remove):
    return [
        ent
        for ent in ent_list
        if not (ent_to_remove.start == ent.start and ent_to_remove.end == ent.end)
    ]


def process_fns(acc, data):
    # from 3.9 We can use functools.cache on some functions
    fn1, fn2, fn3 = data
    if not fn1() and fn2():
        acc.append(fn3())
    return acc


class EntityCustom(object):
    name = "entity_custom"

    def __init__(self, nlp, tag="todas"):
        self.nlp = nlp
        self.tag = tag
        self.tagged_fns_token = [
            self.tag_fn(self.num_causa, ["judicial", "argentina"]),
            self.tag_fn(self.edad, ["español"]),
            self.tag_fn(self.num_cuij, ["judicial", "argentina"]),
            self.tag_fn(self.num_actuacion, ["judicial", "argentina"]),
            self.tag_fn(self.num_expediente, ["judicial", "argentina"]),
            self.tag_fn(self.loc, ["lugar"]),
        ]
        self.tagged_fns_ent = [
            self.tag_fn(self.fecha_resolucion, ["judicial"]),
            self.tag_fn(self.ley, ["judicial", "argentina"]),
            self.tag_fn(self.periodo, ["español"]),
            self.tag_fn(self.juezx, ["judicial", "argentina"]),
            self.tag_fn(self.secretarix, ["judicial", "argentina"]),
            self.tag_fn(self.fiscal, ["judicial", "argentina"]),
            self.tag_fn(self.defensorx, ["judicial", "argentina"]),
            self.tag_fn(self.num_ip, ["internet"]),
            self.tag_fn(self.num_telefono, ["argentina"]),
            self.tag_fn(self.per, ["persona"]),
            self.tag_fn(self.direccion, ["español"]),
            self.tag_fn(self.patente_dominio, ["argentina"]),
        ]

    @staticmethod
    def tag_fn(fn, tags):
        return dict(fn=fn, tags=tags)

    @staticmethod
    def fetch_fn_by_tag(tagged_fns, tag):
        fns = []
        for tagged_fn in tagged_fns:
            if tag == "todas" or tag in tagged_fn["tags"]:
                fns.append(tagged_fn["fn"])
        return fns

    def num_causa(self, token):
        return process_fns(
            [],
            (
                partial(is_from_first_tokens, token.i),
                partial(is_caseNumber, token),
                partial(Span, self.doc, token.i + 0, token.i + 1, label="NUM_CAUSA"),
            ),
        )

    def edad(self, token):
        return process_fns(
            [],
            (
                partial(is_last, self.doc, token.i),
                partial(is_age, token),
                partial(Span, self.doc, token.i + 0, token.i + 1, label="EDAD"),
            ),
        )

    def num_cuij(self, token):
        return process_fns(
            [],
            (
                partial(is_from_first_tokens, token.i),
                partial(is_cuijNumber, token),
                partial(Span, self.doc, token.i + 0, token.i + 1, label="NUM_CUIJ"),
            ),
        )

    def num_actuacion(self, token):
        return process_fns(
            [],
            (
                partial(is_from_first_tokens, token.i),
                partial(is_actuacionNumber, token),
                partial(
                    Span, self.doc, token.i + 0, token.i + 1, label="NUM_ACTUACIÓN"
                ),
            ),
        )

    def num_expediente(self, token):
        return process_fns(
            [],
            (
                partial(is_from_first_tokens, token.i),
                partial(is_expedienteNumber, token),
                partial(
                    Span, self.doc, token.i + 0, token.i + 1, label="NUM_EXPEDIENTE"
                ),
            ),
        )

    def loc(self, token):
        return process_fns(
            [],
            (
                partial(is_from_first_tokens, token.i),
                partial(is_place_token, token),
                partial(Span, self.doc, token.i - 1, token.i + 1, label="LOC"),
            ),
        )

    def ley(self, ent):
        return process_fns(
            [],
            (
                partial(is_from_first_tokens, ent.start),
                partial(is_law, ent),
                partial(Span, self.doc, ent.start + 0, ent.end + 0, label="LEY"),
            ),
        )

    def periodo(self, ent):
        return process_fns(
            [],
            (
                partial(partial(is_last, self.doc, ent.start)),
                partial(is_period, ent),
                partial(Span, self.doc, ent.start + 0, ent.end + 1, label="PERIODO"),
            ),
        )

    def juezx(self, ent):
        return process_fns(
            [],
            (
                partial(is_from_first_tokens, ent.start),
                partial(is_judge, ent),
                partial(Span, self.doc, ent.start + 0, ent.end + 0, label="JUEZX"),
            ),
        )

    def secretarix(self, ent):
        return process_fns(
            [],
            (
                partial(is_from_first_tokens, ent.start),
                partial(is_secretary, ent),
                partial(Span, self.doc, ent.start + 0, ent.end + 0, label="SECRETARIX"),
            ),
        )

    def fiscal(self, ent):
        return process_fns(
            [],
            (
                partial(is_from_first_tokens, ent.start),
                partial(is_prosecutor, ent),
                partial(Span, self.doc, ent.start + 0, ent.end + 0, label="FISCAL"),
            ),
        )

    def defensorx(self, ent):
        return process_fns(
            [],
            (
                partial(is_from_first_tokens, ent.start),
                partial(is_ombuds_person, ent),
                partial(Span, self.doc, ent.start + 0, ent.end + 0, label="DEFENSORX"),
            ),
        )

    def num_ip(self, ent):
        return process_fns(
            [],
            (
                partial(is_from_first_tokens, ent.start),
                partial(is_ip_address, ent),
                partial(Span, self.doc, ent.start + 0, ent.end + 0, label="NUM_IP"),
            ),
        )

    def num_telefono(self, ent):
        return process_fns(
            [],
            (
                partial(is_from_first_tokens, ent.start),
                partial(is_phone, ent),
                partial(
                    Span, self.doc, ent.start + 0, ent.end + 0, label="NUM_TELÉFONO"
                ),
            ),
        )

    def per(self, ent):
        return process_fns(
            [],
            (
                partial(is_from_first_tokens, ent.start),
                partial(is_accused_or_advisor, ent),
                partial(Span, self.doc, ent.start + 0, ent.end + 0, label="PER"),
            ),
        )

    def direccion(self, ent):
        if not is_from_first_tokens(ent.start) and is_address(ent):
            self.new_ents.append(generate_address_span(ent, self.new_ents, self.doc))
        return []

    def patente_dominio(self, ent):
        new_ents = []
        if (
            not is_from_first_tokens(ent.start)
            and could_be_an_article(ent)
            and ent.label_ == "PATENTE_DOMINIO"
        ):
            self.doc.ents = remove_wrong_labeled_entity_span(self.doc.ents, ent)

        if not is_from_first_tokens(ent.start) and is_license_plate(ent):
            start, end = get_start_end_license_plate(ent)
            new_ents.append(Span(self.doc, start, end, label="PATENTE_DOMINIO"))
        return new_ents

    def fecha_resolucion(self, ent):
        new_ents = []
        # Modifica FECHA a FECHA_RESOLUCION: solo la primera vez, si esta el token entre 3 y 100
        if (
            not self.find_fecha_resolucion
            and ent.label_ in ["FECHA"]
            and is_between_tokens(ent.start, 3, 100)
        ):
            self.find_fecha_resolucion = True
            new_ents.append(
                Span(self.doc, ent.start, ent.end, label="FECHA_RESOLUCION")
            )
        return new_ents

    def new_ents_by_ents(self):
        self.find_fecha_resolucion = False
        for i, ent in enumerate(self.doc.ents):
            for fn in self.fetch_fn_by_tag(self.tagged_fns_ent, self.tag):
                self.new_ents.extend(fn(ent))

    def new_ents_by_token(self):
        for token in self.doc:
            for fn in self.fetch_fn_by_tag(self.tagged_fns_token, self.tag):
                self.new_ents.extend(fn(token))

    def __call__(self, doc):
        self.new_ents = []
        self.doc = doc
        self.new_ents_by_token()
        self.new_ents_by_ents()
        if self.new_ents:
            # We'd always want the new entities to be appended first because
            # filter_spans prioritizes the first occurrences on overlapping
            self.doc.ents = filter_spans(self.new_ents + list(self.doc.ents))

        return self.doc
