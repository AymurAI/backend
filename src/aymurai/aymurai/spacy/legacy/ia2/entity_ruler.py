lista_de_marcas_de_autos = [
    "audi",
    "baic",
    "bmw",
    "changan",
    "chery",
    "chevrolet",
    "chrysler",
    "citroen",
    "dodge",
    "ds",
    "ferrari",
    "fiat",
    "ford",
    "foton",
    "geely",
    "haval",
    "heibao",
    "honda",
    "hyundai",
    "isuzu",
    "jac",
    "jaguar",
    "jeep",
    "kia",
    "lexus",
    "lifan",
    "maserati",
    "mclaren",
    "mini",
    "mitsubishi",
    "nissan",
    "peugeot",
    "porsche",
    "ram",
    "renault",
    "saab",
    "seat",
    "shineray",
    "smart",
    "soueast",
    "ssangyong",
    "subaru",
    "suzuki",
    "swm",
    "toyota",
    "volkswagen",
    "volvo",
]

# Fuente https://www.acara.org.ar/guia-oficial-de-precios.php?tipo=AUTOS
marcas_autos = [
    {
        "label": "MARCA_AUTOMÓVIL",
        "pattern": [{"ORTH": "marca"}, {"LOWER": {"IN": lista_de_marcas_de_autos}}],
    },
    {
        "label": "MARCA_AUTOMÓVIL",
        "pattern": [{"ORTH": "marca"}, {"LOWER": "alfa"}, {"LOWER": "romeo"}],
    },
    {
        "label": "MARCA_AUTOMÓVIL",
        "pattern": [{"ORTH": "marca"}, {"LOWER": "mercedes"}, {"LOWER": "benz"}],
    },
    {
        "label": "MARCA_AUTOMÓVIL",
        "pattern": [{"ORTH": "marca"}, {"LOWER": "land"}, {"LOWER": "rover"}],
    },
    {
        "label": "MARCA_AUTOMÓVIL",
        "pattern": [{"ORTH": "marca"}, {"LOWER": "great"}, {"LOWER": "wall"}],
    },
]

# Fuente del BCRA: http://www.bcra.gov.ar/pdfs/comytexord/b9195.pdf
bancos = [
    {"label": "BANCO", "pattern": [{"LOWER": "banco"}, {"LOWER": "columbia"}]},
    {
        "label": "BANCO",
        "pattern": [{"LOWER": "nuevo"}, {"LOWER": "banco"}, {"LOWER": "bisel"}],
    },
    {
        "label": "BANCO",
        "pattern": [
            {"LOWER": "nuevo"},
            {"LOWER": "banco"},
            {"LOWER": "de"},
            {"LOWER": "entre"},
            {"LOWER": "ríos"},
        ],
    },
    {"label": "BANCO", "pattern": [{"LOWER": "icbc"}, {"LOWER": "argentina"}]},
    {"label": "BANCO", "pattern": [{"LOWER": "citibank"}]},
    {"label": "BANCO", "pattern": [{"LOWER": "banco"}, {"LOWER": "masventas"}]},
    {"label": "BANCO", "pattern": [{"LOWER": "rci"}, {"LOWER": "Banque"}]},
    {
        "label": "BANCO",
        "pattern": [{"LOWER": "a.b.n."}, {"LOWER": "amro"}, {"LOWER": "bank"}],
    },
    {
        "label": "BANCO",
        "pattern": [{"LOWER": "bbva"}, {"LOWER": "banco"}, {"LOWER": "francés"}],
    },
    {
        "label": "BANCO",
        "pattern": [
            {"LOWER": "bank"},
            {"LOWER": "of"},
            {"LOWER": "america"},
            {"LOWER": "national"},
            {"LOWER": "association"},
        ],
    },
    {"label": "BANCO", "pattern": [{"LOWER": "bnp"}, {"LOWER": "paribas"}]},
    {
        "label": "BANCO",
        "pattern": [
            {"LOWER": "the"},
            {"LOWER": "bank"},
            {"LOWER": "of"},
            {"LOWER": "tokyo"},
            {"ORTH": "-", "OP": "?"},
            {"LOWER": "mitsubishi"},
            {"LOWER": "Ufj"},
            {"IS_PUNCT": True, "OP": "?"},
            {"LOWER": "ltd"},
            {"IS_PUNCT": True, "OP": "?"},
        ],
    },
    {
        "label": "BANCO",
        "pattern": [
            {"LOWER": "banco"},
            {"LOWER": "b"},
            {"IS_PUNCT": True, "OP": "?"},
            {"LOWER": "i"},
            {"IS_PUNCT": True, "OP": "?"},
            {"LOWER": "creditanstalt"},
        ],
    },
    {
        "label": "BANCO",
        "pattern": [{"LOWER": "hsbc"}, {"LOWER": "Bank"}, {"LOWER": "argentina"}],
    },
    {
        "label": "BANCO",
        "pattern": [
            {"LOWER": "j"},
            {"LOWER": "p"},
            {"LOWER": "Morgan"},
            {"LOWER": "Chase"},
            {"LOWER": "bank"},
            {"LOWER": "national"},
            {"LOWER": "association"},
            {"ORTH": "(", "OP": "?"},
            {"LOWER": "sucursal"},
            {"LOWER": "buenos"},
            {"LOWER": "Aires"},
            {"ORTH": ")", "OP": "?"},
        ],
    },
    {
        "label": "BANCO",
        "pattern": [
            {"LOWER": "american"},
            {"LOWER": "express"},
            {"LOWER": "bank"},
            {"LOWER": "ltd"},
        ],
    },
    {
        "label": "BANCO",
        "pattern": [
            {"LOWER": "M.B.A."},
            {"LOWER": "banco"},
            {"LOWER": "de"},
            {"LOWER": "inversiones"},
        ],
    },
    {"label": "BANCO", "pattern": [{"LOWER": "deutsche"}, {"LOWER": "bank"}]},
    {
        "label": "BANCO",
        "pattern": [
            {"LOWER": "bacs"},
            {"LOWER": "banco"},
            {"LOWER": "de"},
            {"LOWER": "credito"},
            {"LOWER": "y"},
            {"LOWER": "securitizacion"},
        ],
    },
    {
        "label": "BANCO",
        "pattern": [
            {"LOWER": "banco"},
            {"LOWER": "de"},
            {"LOWER": "galicia"},
            {"LOWER": "y"},
            {"LOWER": "buenos"},
            {"LOWER": "aires"},
        ],
    },
    {
        "label": "BANCO",
        "pattern": [
            {"LOWER": "banco"},
            {"LOWER": "de"},
            {"LOWER": "la"},
            {"LOWER": "nación"},
            {"LOWER": "argentina"},
        ],
    },
    {
        "label": "BANCO",
        "pattern": [
            {"LOWER": "banco"},
            {"LOWER": "de"},
            {"LOWER": "la"},
            {"LOWER": "provincia"},
            {"LOWER": "de"},
            {"LOWER": "buenos"},
            {"LOWER": "aires"},
        ],
    },
    {
        "label": "BANCO",
        "pattern": [
            {"LOWER": "banco"},
            {"LOWER": "de"},
            {"LOWER": "la"},
            {"LOWER": "provincia"},
            {"LOWER": "de"},
            {"LOWER": "cordoba"},
        ],
    },
    {"label": "BANCO", "pattern": [{"LOWER": "banco"}, {"LOWER": "supervielle"}]},
    {
        "label": "BANCO",
        "pattern": [
            {"LOWER": "banco"},
            {"LOWER": "de"},
            {"LOWER": "la"},
            {"LOWER": "ciudad"},
            {"LOWER": "de"},
            {"LOWER": "buenos"},
            {"LOWER": "aires"},
        ],
    },
    {"label": "BANCO", "pattern": [{"LOWER": "banco"}, {"LOWER": "patagonia"}]},
    {"label": "BANCO", "pattern": [{"LOWER": "banco"}, {"LOWER": "hipotecario"}]},
    {
        "label": "BANCO",
        "pattern": [
            {"LOWER": "banco"},
            {"LOWER": "de"},
            {"LOWER": "san"},
            {"LOWER": "juan"},
        ],
    },
    {
        "label": "BANCO",
        "pattern": [{"LOWER": "banco"}, {"LOWER": "do"}, {"LOWER": "brasil"}],
    },
    {
        "label": "BANCO",
        "pattern": [{"LOWER": "banco"}, {"LOWER": "del"}, {"LOWER": "tucuman"}],
    },
    {
        "label": "BANCO",
        "pattern": [
            {"LOWER": "banco"},
            {"LOWER": "municipal"},
            {"LOWER": "de"},
            {"LOWER": "rosario"},
        ],
    },
    {
        "label": "BANCO",
        "pattern": [{"LOWER": "banco"}, {"LOWER": "santander"}, {"LOWER": "rio"}],
    },
    {
        "label": "BANCO",
        "pattern": [
            {"LOWER": "banco"},
            {"LOWER": "regional"},
            {"LOWER": "de"},
            {"LOWER": "cuyo"},
        ],
    },
    {
        "label": "BANCO",
        "pattern": [{"LOWER": "banco"}, {"LOWER": "del"}, {"LOWER": "chubut"}],
    },
    {
        "label": "BANCO",
        "pattern": [
            {"LOWER": "banco"},
            {"LOWER": "de"},
            {"LOWER": "Santa"},
            {"LOWER": "cruz"},
        ],
    },
    {
        "label": "BANCO",
        "pattern": [
            {"LOWER": "banco"},
            {"LOWER": "de"},
            {"LOWER": "la"},
            {"LOWER": "pampa"},
            {"LOWER": "sociedad"},
            {"LOWER": "de"},
            {"LOWER": "economía"},
            {"LOWER": "mixta"},
        ],
    },
    {
        "label": "BANCO",
        "pattern": [{"LOWER": "banco"}, {"LOWER": "de"}, {"LOWER": "corrientes"}],
    },
    {
        "label": "BANCO",
        "pattern": [
            {"LOWER": "banco"},
            {"LOWER": "provincia"},
            {"LOWER": "del"},
            {"LOWER": "neuquén"},
        ],
    },
    {
        "label": "BANCO",
        "pattern": [
            {"LOWER": "banco"},
            {"LOWER": "credicoop"},
            {"LOWER": "cooperativo"},
            {"LOWER": "limitado"},
        ],
    },
    {
        "label": "BANCO",
        "pattern": [{"LOWER": "banco"}, {"LOWER": "de"}, {"LOWER": "valores"}],
    },
    {"label": "BANCO", "pattern": [{"LOWER": "banco"}, {"LOWER": "roela"}]},
    {"label": "BANCO", "pattern": [{"LOWER": "banco"}, {"LOWER": "mariva"}]},
    {
        "label": "BANCO",
        "pattern": [
            {"LOWER": "banco"},
            {"LOWER": "itau"},
            {"LOWER": "buen"},
            {"LOWER": "ayre"},
        ],
    },
    {
        "label": "BANCO",
        "pattern": [
            {"LOWER": "banco"},
            {"LOWER": "provincia"},
            {"LOWER": "de"},
            {"LOWER": "tierra"},
            {"LOWER": "del"},
            {"LOWER": "fuego"},
        ],
    },
    {
        "label": "BANCO",
        "pattern": [
            {"LOWER": "banco"},
            {"LOWER": "de"},
            {"LOWER": "la"},
            {"LOWER": "republica"},
            {"LOWER": "oriental"},
            {"LOWER": "del"},
            {"LOWER": "uruguay"},
        ],
    },
    {"label": "BANCO", "pattern": [{"LOWER": "banco"}, {"LOWER": "saenz"}]},
    {"label": "BANCO", "pattern": [{"LOWER": "banco"}, {"LOWER": "meridian"}]},
    {"label": "BANCO", "pattern": [{"LOWER": "banco"}, {"LOWER": "macro"}]},
    {"label": "BANCO", "pattern": [{"LOWER": "banco"}, {"LOWER": "mercurio"}]},
    {"label": "BANCO", "pattern": [{"LOWER": "banco"}, {"LOWER": "comafi"}]},
    {
        "label": "BANCO",
        "pattern": [
            {"LOWER": "banco"},
            {"LOWER": "de"},
            {"LOWER": "inversion"},
            {"LOWER": "y"},
            {"LOWER": "comercio"},
            {"LOWER": "exterior"},
        ],
    },
    {"label": "BANCO", "pattern": [{"LOWER": "banco"}, {"LOWER": "piano"}]},
    {"label": "BANCO", "pattern": [{"LOWER": "banco"}, {"LOWER": "finansur"}]},
    {"label": "BANCO", "pattern": [{"LOWER": "banco"}, {"LOWER": "julio"}]},
    {
        "label": "BANCO",
        "pattern": [
            {"LOWER": "banco"},
            {"LOWER": "privado"},
            {"LOWER": "de"},
            {"LOWER": "inversiones"},
        ],
    },
    {
        "label": "BANCO",
        "pattern": [
            {"LOWER": "nuevo"},
            {"LOWER": "banco"},
            {"LOWER": "de"},
            {"LOWER": "la"},
            {"LOWER": "rioja"},
        ],
    },
    {
        "label": "BANCO",
        "pattern": [{"LOWER": "banco"}, {"LOWER": "del"}, {"LOWER": "sol"}],
    },
    {
        "label": "BANCO",
        "pattern": [
            {"LOWER": "nuevo"},
            {"LOWER": "banco"},
            {"LOWER": "del"},
            {"LOWER": "chaco"},
        ],
    },
    {
        "label": "BANCO",
        "pattern": [{"LOWER": "banco"}, {"LOWER": "de"}, {"LOWER": "formosa"}],
    },
    {"label": "BANCO", "pattern": [{"LOWER": "banco"}, {"LOWER": "cmf"}]},
    {
        "label": "BANCO",
        "pattern": [
            {"LOWER": "banco"},
            {"LOWER": "de"},
            {"LOWER": "santiago"},
            {"LOWER": "del"},
            {"LOWER": "estero"},
        ],
    },
    {
        "label": "BANCO",
        "pattern": [
            {"LOWER": "nuevo"},
            {"LOWER": "banco"},
            {"LOWER": "industrial"},
            {"LOWER": "de"},
            {"LOWER": "azul"},
        ],
    },
    {
        "label": "BANCO",
        "pattern": [
            {"LOWER": "nuevo"},
            {"LOWER": "banco"},
            {"LOWER": "de"},
            {"LOWER": "santa"},
            {"LOWER": "fe"},
        ],
    },
    {
        "label": "BANCO",
        "pattern": [{"LOWER": "banco"}, {"LOWER": "cetelem"}, {"LOWER": "argentina"}],
    },
    {
        "label": "BANCO",
        "pattern": [
            {"LOWER": "banco"},
            {"LOWER": "de"},
            {"LOWER": "servicios"},
            {"LOWER": "financieros"},
        ],
    },
    {"label": "BANCO", "pattern": [{"LOWER": "banco"}, {"LOWER": "cofidis"}]},
    {
        "label": "BANCO",
        "pattern": [{"LOWER": "banco"}, {"LOWER": "bradesco"}, {"LOWER": "argentina"}],
    },
    {
        "label": "BANCO",
        "pattern": [
            {"LOWER": "banco"},
            {"LOWER": "de"},
            {"LOWER": "servicios"},
            {"LOWER": "y"},
            {"LOWER": "transacciones"},
        ],
    },
]

patentes = [
    {"label": "PATENTE_DOMINIO", "pattern": [{"SHAPE": "XXX ddd"}]},
    {"label": "PATENTE_DOMINIO", "pattern": [{"SHAPE": "XXX-ddd"}]},
    {"label": "PATENTE_DOMINIO", "pattern": [{"SHAPE": "XXXddd"}]},
    {"label": "PATENTE_DOMINIO", "pattern": [{"SHAPE": "ddd XXX"}]},
    {"label": "PATENTE_DOMINIO", "pattern": [{"SHAPE": "ddd-XXX"}]},
    {"label": "PATENTE_DOMINIO", "pattern": [{"SHAPE": "dddXXX"}]},
    {"label": "PATENTE_DOMINIO", "pattern": [{"SHAPE": "XX-ddd-XX"}]},
    {"label": "PATENTE_DOMINIO", "pattern": [{"SHAPE": "XXdddXX"}]},
    {"label": "PATENTE_DOMINIO", "pattern": [{"SHAPE": "xxx ddd"}]},
    {"label": "PATENTE_DOMINIO", "pattern": [{"SHAPE": "xxx-ddd"}]},
    {"label": "PATENTE_DOMINIO", "pattern": [{"SHAPE": "xxxddd"}]},
    {"label": "PATENTE_DOMINIO", "pattern": [{"SHAPE": "ddd xxx"}]},
    {"label": "PATENTE_DOMINIO", "pattern": [{"SHAPE": "ddd-xxx"}]},
    {"label": "PATENTE_DOMINIO", "pattern": [{"SHAPE": "dddxxx"}]},
    {"label": "PATENTE_DOMINIO", "pattern": [{"SHAPE": "xx-ddd-xx"}]},
    {"label": "PATENTE_DOMINIO", "pattern": [{"SHAPE": "xxdddxx"}]},
]


lista_de_estudios = ["secundarios", "primarios", "terciarios", "universitarios"]

lista_de_estado = ["completos", "incompletos"]

estudios = [
    {
        "label": "ESTUDIOS",
        "pattern": [
            {"LOWER": "estudios"},
            {"LOWER": {"IN": lista_de_estudios}},
            {"LOWER": {"IN": lista_de_estado}},
        ],
    },
]

dni = [
    {"label": "NUM_DNI", "pattern": [{"SHAPE": "d.ddd.ddd"}]},
    {"label": "NUM_DNI", "pattern": [{"SHAPE": "dd.ddd.ddd"}]},
    {"label": "NUM_DNI", "pattern": [{"SHAPE": "ddd.ddd.ddd"}]},
]

telefonos = [
    {"label": "NUM_TELÉFONO", "pattern": [{"SHAPE": "dd-dddd-dddd"}]},
    {"label": "NUM_TELÉFONO", "pattern": [{"SHAPE": "dddddddddd"}]},
    {"label": "NUM_TELÉFONO", "pattern": [{"SHAPE": "dddd-dddd"}]},
    {"label": "NUM_TELÉFONO", "pattern": [{"SHAPE": "dddd-ddd-dddd"}]},
]

ips = [
    {"label": "NUM_IP", "pattern": [{"SHAPE": "ddd.ddd.ddd.ddd"}]},
    {"label": "NUM_IP", "pattern": [{"SHAPE": "ddd.dd.ddd.d"}]},
    {"label": "NUM_IP", "pattern": [{"SHAPE": "ddd.dd.ddd.dd"}]},
]

fecha_numerica = [
    {"label": "FECHA_NUMÉRICA", "pattern": [{"SHAPE": "dd/dd/dd"}]},
    #    Es problematica con otros casos
    #    {"label": "FECHA_NUMÉRICA", "pattern": [{"SHAPE": "dd/dd"}]},
    {"label": "FECHA_NUMÉRICA", "pattern": [{"SHAPE": "dd/dd/dddd"}]},
    {"label": "FECHA_NUMÉRICA", "pattern": [{"SHAPE": "d/d/dd"}]},
    {"label": "FECHA_NUMÉRICA", "pattern": [{"SHAPE": "d/d/dddd"}]},
    {"label": "FECHA_NUMÉRICA", "pattern": [{"SHAPE": "d/dd/dddd"}]},
]

cuij = [
    {"label": "NUM_CUIJ", "pattern": [{"ORTH": "CAU"}, {"IS_ASCII": True}]},
    {"label": "NUM_CUIJ", "pattern": [{"ORTH": "ICN"}, {"IS_ASCII": True}]},
    {"label": "NUM_CUIJ", "pattern": [{"ORTH": "IPP"}, {"IS_ASCII": True}]},
    {"label": "NUM_CUIJ", "pattern": [{"ORTH": "CAU"}, {"LIKE_NUM": True}]},
    {"label": "NUM_CUIJ", "pattern": [{"ORTH": "ICN"}, {"LIKE_NUM": True}]},
    {"label": "NUM_CUIJ", "pattern": [{"ORTH": "IPP"}, {"LIKE_NUM": True}]},
]

fecha = [
    {
        "label": "FECHA",
        "pattern": [
            {
                "LOWER": {
                    "IN": [
                        "enero",
                        "febrero",
                        "marzo",
                        "abril",
                        "mayo",
                        "junio",
                        "julio",
                        "agosto",
                        "septiembre",
                        "octubre",
                        "noviembre",
                        "diciembre",
                    ]
                }
            },
            {"POS": "ADP", "OP": "?"},
            {"LIKE_NUM": True, "OP": "?"},
        ],
    },
    {
        "label": "FECHA",
        "pattern": [
            {"LOWER": "a"},
            {"LOWER": "los"},
            {"LIKE_NUM": True},
            {"LOWER": "días"},
            {"LOWER": "del", "OP": "?"},
            {"LOWER": "mes", "OP": "?"},
            {"LOWER": "de"},
            {
                "LOWER": {
                    "IN": [
                        "enero",
                        "febrero",
                        "marzo",
                        "abril",
                        "mayo",
                        "junio",
                        "julio",
                        "agosto",
                        "septiembre",
                        "octubre",
                        "noviembre",
                        "diciembre",
                    ]
                }
            },
            {"POS": "ADP", "OP": "?"},
            {"LIKE_NUM": True, "OP": "?"},
        ],
    },
    {
        "label": "FECHA",
        "pattern": [
            {"LIKE_NUM": True},
            {"POS": "ADP"},
            {
                "LOWER": {
                    "IN": [
                        "enero",
                        "febrero",
                        "marzo",
                        "abril",
                        "mayo",
                        "junio",
                        "julio",
                        "agosto",
                        "septiembre",
                        "octubre",
                        "noviembre",
                        "diciembre",
                    ]
                }
            },
            {"POS": "ADP", "OP": "?"},
            {"LOWER": "año", "OP": "?"},
            {"LIKE_NUM": True, "OP": "?"},
        ],
    },
]

nacionalidad = [
    {
        "label": "NACIONALIDAD",
        "pattern": [
            {
                "LEMMA": {
                    "IN": [
                        "argentino",
                        "boliviano",
                        "paraguayo",
                        "colombiano",
                        "chileno",
                        "brasileño",
                        "panameño",
                        "italiano",
                        "español",
                        "mexicano",
                        "ruso",
                        "francés",
                        "inglés",
                        "venezolano",
                        "estadounidense",
                        "alemán",
                        "chino",
                        "indio",
                        "cubano",
                        "nigeriano",
                        "polaco",
                        "sueco",
                        "turco",
                        "japonés",
                        "portugués",
                        "iraní",
                        "paquistaní",
                        "costarricense",
                        "canadiense",
                        "marroquí",
                        "griego",
                        "egipcio",
                        "coreano",
                        "ecuatoriano",
                        "peruano",
                        "guatemalteco",
                        "salvadoreño",
                        "holandés",
                        "dominicano",
                    ]
                }
            }
        ],
    },
    {
        "label": "NACIONALIDAD",
        "pattern": [
            {
                "LEMMA": {
                    "IN": [
                        "argentino",
                        "boliviano",
                        "paraguayo",
                        "colombiano",
                        "chileno",
                        "brasileño",
                        "panameño",
                        "italiano",
                        "español",
                        "mexicano",
                        "ruso",
                        "francés",
                        "inglés",
                        "venezolano",
                        "estadounidense",
                        "alemán",
                        "chino",
                        "indio",
                        "cubano",
                        "nigeriano",
                        "polaco",
                        "sueco",
                        "turco",
                        "japonés",
                        "portugués",
                        "iraní",
                        "paquistaní",
                        "costarricense",
                        "canadiense",
                        "marroquí",
                        "griego",
                        "egipcio",
                        "coreano",
                        "ecuatoriano",
                        "peruano",
                        "guatemalteco",
                        "salvadoreño",
                        "holandés",
                        "dominicano",
                    ]
                }
            }
        ],
    },
]


correo_electronico = [
    {"label": "CORREO_ELECTRÓNICO", "pattern": [{"LIKE_EMAIL": True}]}
]

ley = [{"label": "LEY", "pattern": [{"LOWER": "ley"}, {"LIKE_NUM": True}]}]

cuit = [
    {
        "label": "NUM_CUIT_CUIL",
        "pattern": [
            {"TEXT": {"REGEX": "^(20|23|27|30|33)([0-9]{9}|-[0-9]{8}-[0-9]{1})$"}}
        ],
    }
]

archivos = [
    {
        "label": "NOMBRE_ARCHIVO",
        "pattern": [
            {
                "TEXT": {
                    "REGEX": r"^[\w]+\.(jpg|png|gif|bmp|tiff|svg|doc|docx|odt|txt|pdf|mp3|avi|mp4|mkv|mpg|mpeg|mov|asf|webm|3gp|3g2|m4v)$"
                }
            }
        ],
    },
]

pasaporte = [
    {"label": "PASAPORTE", "pattern": [{"TEXT": {"REGEX": "^([a-zA-Z]{3}[0-9]{6})$"}}]}
]

link = [{"label": "LINK", "pattern": [{"LIKE_URL": True}]}]

cbu = [
    {
        "label": "CBU",
        "pattern": [
            {"ORTH": "CBU"},
            {"ORTH": ":", "OP": "?"},
            {"IS_DIGIT": True, "LENGTH": 22},
        ],
    }
]

usuarix = [
    {
        "label": "USUARIX",
        "pattern": [
            {"ORTH": "del"},
            {"ORTH": "usuario"},
            {"ORTH": '"'},
            {"IS_ALPHA": True, "OP": "+"},
            {"ORTH": '"'},
        ],
    }
]


def tag_array(arr, tags):
    return dict(arr=arr, tags=tags)


def fetch_ruler_patterns_by_tag(tag):
    ruler_patterns = []
    for tagged_pattern in tagged_patterns:
        if tag == "todas" or tag in tagged_pattern["tags"]:
            ruler_patterns.extend(tagged_pattern["arr"])
    return ruler_patterns


tagged_patterns = [
    tag_array(dni, ["argentina", "juzgado10"]),
    tag_array(telefonos, ["argentina", "juzgado10"]),
    tag_array(ips, ["internet", "juzgado10"]),
    tag_array(fecha_numerica, ["español", "juzgado10"]),
    tag_array(cuij, ["judicial", "juzgado10"]),
    tag_array(fecha, ["español", "juzgado10"]),
    tag_array(nacionalidad, ["español", "juzgado10"]),
    tag_array(bancos, ["argentina", "juzgado10"]),
    tag_array(patentes, ["argentina", "juzgado10"]),
    tag_array(estudios, ["argentina", "juzgado10"]),
    tag_array(marcas_autos, ["argentina", "juzgado10"]),
    tag_array(correo_electronico, ["internet", "juzgado10"]),
    tag_array(ley, ["judicial", "juzgado10"]),
    tag_array(cuit, ["argentina", "juzgado10"]),
    tag_array(archivos, ["internet", "juzgado10"]),
    tag_array(pasaporte, ["argentina", "juzgado10"]),
    tag_array(link, ["internet", "juzgado10"]),
    tag_array(cbu, ["argentina", "juzgado10"]),
    tag_array(usuarix, ["internet", "juzgado10"]),
]
