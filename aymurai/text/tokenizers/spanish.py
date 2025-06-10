"""
A simplified clone of spaCy’s Spanish tokenizer (and related components)
without any dependency on spaCy. This module provides:
  • TOKENIZER_EXCEPTIONS – a mapping for known exceptions.
  • STOP_WORDS – Spanish stop words.
  • TOKENIZER_SUFFIXES and TOKENIZER_INFIXES – basic regex rules.
  • Lexical attribute getter for “like_num”.
  • SpanishTokenizer – a class that tokenizes text using the above rules.

Note: This is a “simple but close” clone. spaCy’s internal rules are very
comprehensive; here we implement only some of the core ideas.
"""

import re

# --- Definitions used in spaCy’s internals, simplified ---
ORTH = "ORTH"
NORM = "NORM"


def update_exc(base, new_exc):
    base.update(new_exc)
    return base


# A base (empty) exceptions dict
BASE_EXCEPTIONS = {}

# --- Tokenizer Exceptions (from spacy.lang.es.tokenizer_exceptions) ---
_exc = {
    "pal": [{ORTH: "pa"}, {ORTH: "l", NORM: "el"}],
}

for exc_data in [
    {ORTH: "n°"},
    {ORTH: "°C"},
    {ORTH: "aprox."},
    {ORTH: "dna."},
    {ORTH: "dpto."},
    {ORTH: "ej."},
    {ORTH: "esq."},
    {ORTH: "pág."},
    {ORTH: "p.ej."},
    {ORTH: "Ud.", NORM: "usted"},
    {ORTH: "Vd.", NORM: "usted"},
    {ORTH: "Uds.", NORM: "ustedes"},
    {ORTH: "Vds.", NORM: "ustedes"},
    {ORTH: "vol.", NORM: "volúmen"},
]:
    _exc[exc_data[ORTH]] = [exc_data]

# Times exceptions: “12m.” splits into “12” and “m.”, and also the h+a.m./p.m. forms.
_exc["12m."] = [{ORTH: "12"}, {ORTH: "m."}]

for h in range(1, 13):
    for period in ["a.m.", "am"]:
        _exc[f"{h}{period}"] = [{ORTH: f"{h}"}, {ORTH: period}]
    for period in ["p.m.", "pm"]:
        _exc[f"{h}{period}"] = [{ORTH: f"{h}"}, {ORTH: period}]

for orth in [
    "a.C.",
    "a.J.C.",
    "d.C.",
    "d.J.C.",
    "apdo.",
    "Av.",
    "Avda.",
    "Cía.",
    "Dr.",
    "Dra.",
    "EE.UU.",
    "Ee.Uu.",
    "EE. UU.",
    "Ee. Uu.",
    "etc.",
    "fig.",
    "Gob.",
    "Gral.",
    "Ing.",
    "J.C.",
    "km/h",
    "Lic.",
    "m.n.",
    "núm.",
    "P.D.",
    "Prof.",
    "Profa.",
    "q.e.p.d.",
    "Q.E.P.D.",
    "S.A.",
    "S.L.",
    "S.R.L.",
    "s.s.s.",
    "Sr.",
    "Sra.",
    "Srta.",
]:
    _exc[orth] = [{ORTH: orth}]

TOKENIZER_EXCEPTIONS = update_exc(BASE_EXCEPTIONS.copy(), _exc)

# --- Stop words (from spacy.lang.es.stop_words) ---
STOP_WORDS = set(
    """
a acuerdo adelante ademas además afirmó agregó ahi ahora ahí al algo alguna
algunas alguno algunos algún alli allí alrededor ambos ante anterior antes
apenas aproximadamente aquel aquella aquellas aquello aquellos aqui aquél
aquélla aquéllas aquéllos aquí arriba aseguró asi así atras aun aunque añadió
aún

bajo bastante bien breve buen buena buenas bueno buenos

cada casi cierta ciertas cierto ciertos cinco claro comentó como con conmigo
conocer conseguimos conseguir considera consideró consigo consigue consiguen
consigues contigo contra creo cual cuales cualquier cuando cuanta cuantas
cuanto cuantos cuatro cuenta cuál cuáles cuándo cuánta cuántas cuánto cuántos
cómo

da dado dan dar de debajo debe deben debido decir dejó del delante demasiado
demás dentro deprisa desde despacio despues después detras detrás dia dias dice
dicen dicho dieron diez diferente diferentes dijeron dijo dio doce donde dos
durante día días dónde

e el ella ellas ello ellos embargo en encima encuentra enfrente enseguida
entonces entre era eramos eran eras eres es esa esas ese eso esos esta estaba
estaban estado estados estais estamos estan estar estará estas este esto estos
estoy estuvo está están excepto existe existen explicó expresó él ésa ésas ése
ésos ésta éstas éste éstos

fin final fue fuera fueron fui fuimos

gran grande grandes

ha haber habia habla hablan habrá había habían hace haceis hacemos hacen hacer
hacerlo haces hacia haciendo hago han hasta hay haya he hecho hemos hicieron
hizo hoy hubo

igual incluso indicó informo informó ir

junto

la lado largo las le les llegó lleva llevar lo los luego

mal manera manifestó mas mayor me mediante medio mejor mencionó menos menudo mi
mia mias mientras mio mios mis misma mismas mismo mismos modo mucha muchas
mucho muchos muy más mí mía mías mío míos

nada nadie ni ninguna ningunas ninguno ningunos ningún no nos nosotras nosotros
nuestra nuestras nuestro nuestros nueva nuevas nueve nuevo nuevos nunca

o ocho once os otra otras otro otros

para parece parte partir pasada pasado paìs peor pero pesar poca pocas poco
pocos podeis podemos poder podria podriais podriamos podrian podrias podrá
podrán podría podrían poner por porque posible primer primera primero primeros
pronto propia propias propio propios proximo próximo próximos pudo pueda puede
pueden puedo pues

qeu que quedó queremos quien quienes quiere quiza quizas quizá quizás quién
quiénes qué

realizado realizar realizó repente respecto

sabe sabeis sabemos saben saber sabes salvo se sea sean segun segunda segundo
según seis ser sera será serán sería señaló si sido siempre siendo siete sigue
siguiente sin sino sobre sois sola solamente solas solo solos somos son soy su
supuesto sus suya suyas suyo suyos sé sí sólo

tal tambien también tampoco tan tanto tarde te temprano tendrá tendrán teneis
tenemos tener tenga tengo tenido tenía tercera tercero ti tiene tienen toda
todas todavia todavía todo todos total tras trata través tres tu tus tuvo tuya
tuyas tuyo tuyos tú

u ultimo un una unas uno unos usa usais usamos usan usar usas uso usted ustedes
última últimas último últimos

va vais vamos van varias varios vaya veces ver verdad verdadera verdadero vez
vosotras vosotros voy vuestra vuestras vuestro vuestros

y ya yo
""".split()
)

# --- Punctuation-related rules (a simplified version of spacy.lang.es.punctuation) ---
# Here we provide basic suffix and infix patterns.
TOKENIZER_SUFFIXES = [
    r"[—–]",  # dashes
    r"[.,!?;:%]",  # common punctuation
    r"['\"“”‘’]",  # quotes
]
# Infixes that split on, for example, hyphens between digits.
TOKENIZER_INFIXES = [
    r"(?<=[0-9])[-/](?=[0-9])",
]

# --- Lexical attribute getter (from spacy.lang.es.lex_attrs) ---
_num_words = {
    "cero",
    "uno",
    "dos",
    "tres",
    "cuatro",
    "cinco",
    "seis",
    "siete",
    "ocho",
    "nueve",
    "diez",
    "once",
    "doce",
    "trece",
    "catorce",
    "quince",
    "dieciséis",
    "diecisiete",
    "dieciocho",
    "diecinueve",
    "veinte",
    "veintiuno",
    "veintidós",
    "veintitrés",
    "veinticuatro",
    "veinticinco",
    "veintiséis",
    "veintisiete",
    "veintiocho",
    "veintinueve",
    "treinta",
    "cuarenta",
    "cincuenta",
    "sesenta",
    "setenta",
    "ochenta",
    "noventa",
    "cien",
    "mil",
    "millón",
    "billón",
    "trillón",
}
_ordinal_words = {
    "primero",
    "segundo",
    "tercero",
    "cuarto",
    "quinto",
    "sexto",
    "séptimo",
    "octavo",
    "noveno",
    "décimo",
    "undécimo",
    "duodécimo",
    "decimotercero",
    "decimocuarto",
    "decimoquinto",
    "decimosexto",
    "decimoséptimo",
    "decimoctavo",
    "decimonoveno",
    "vigésimo",
    "trigésimo",
    "cuadragésimo",
    "quincuagésimo",
    "sexagésimo",
    "septuagésimo",
    "octogésima",
    "nonagésima",
    "centésima",
    "milésima",
    "millonésima",
    "billonésima",
}


def like_num(text):
    # Remove a leading +, -, ±, or ~ if present.
    if text.startswith(("+", "-", "±", "~")):
        text = text[1:]
    # Remove commas and periods for a digit check.
    text_clean = text.replace(",", "").replace(".", "")
    if text_clean.isdigit():
        return True
    if text.count("/") == 1:
        num, denom = text.split("/")
        if num.isdigit() and denom.isdigit():
            return True
    text_lower = text.lower()
    if text_lower in _num_words:
        return True
    if text_lower in _ordinal_words:
        return True
    return False


LEX_ATTRS = {"LIKE_NUM": like_num}


# --- Spanish Tokenizer Implementation ---
class SpanishTokenizer:
    """
    Spacy spanish tokenizer clone
    Source: https://github.com/explosion/spaCy/tree/b3c46c315eb16ce644bddd106d31c3dd349f6bb2/spacy/lang/es
    """

    def __init__(self):
        # A basic regex for “words” and “non-space” characters.
        self.word_re = re.compile(r"\w+|[^\w\s]", re.UNICODE)
        # Combine infix patterns into one regex.
        self.infix_re = re.compile("|".join(TOKENIZER_INFIXES))

    def apply_exceptions(self, text: str):
        """
        If the given text exactly matches a tokenizer exception,
        return the corresponding token list.
        """
        if text in TOKENIZER_EXCEPTIONS:
            # For each exception item (a dict), return the ORTH value,
            # falling back to NORM if available.
            return [
                item.get(ORTH, item.get(NORM, item))
                for item in TOKENIZER_EXCEPTIONS[text]
            ]
        return None

    def tokenize(self, text: str):
        """
        Tokenizes the input text into a list of tokens.
        The algorithm first splits on whitespace, checks for exceptions,
        and otherwise applies regex-based splitting and infix splitting.
        """
        tokens = []
        for word in text.split():
            exc = self.apply_exceptions(word)
            if exc is not None:
                tokens.extend(exc)
            else:
                # First, use regex to split word into basic tokens.
                sub_tokens = self.word_re.findall(word)
                final_tokens = []
                for token in sub_tokens:
                    # Apply infix splitting if applicable.
                    splits = self.infix_re.split(token)
                    if len(splits) > 1:
                        last_end = 0
                        # Re-find infix matches to capture separators.
                        for m in self.infix_re.finditer(token):
                            pre = token[last_end : m.start()]
                            sep = token[m.start() : m.end()]
                            if pre:
                                final_tokens.append(pre)
                            final_tokens.append(sep)
                            last_end = m.end()
                        remainder = token[last_end:]
                        if remainder:
                            final_tokens.append(remainder)
                    else:
                        final_tokens.append(token)
                tokens.extend(final_tokens)
        return tokens

    def __call__(self, text: str):
        return self.tokenize(text)


# --- Example Usage ---
if __name__ == "__main__":
    sample_text = "El Sr. habló con 12a.m. y 3pm en la reunión. ¡Increíble, verdad?"
    tokenizer = SpanishTokenizer()
    tokens = tokenizer(sample_text)
    print("Tokens:", tokens)
