import locale

# set locale to es_AR to handle month names
locale.setlocale(locale.LC_ALL, "es_AR.UTF-8")

DATES = [
    r"%-d/%-m/%Y",
    r"%-d/%-m/%y",
    r"%d/%m/%Y",
    r"%d/%m/%y",
    r"(?i)%-d de %B del? %Y",
    r"(?i)%-d de %B %Y",
]
HOURS = [
    r"%H[\.:]%M",
    r"(?i)%-H[\.:]%M horas",
    r"(?i)%-H.%M h(rs|r|s)\.?",
]

patterns = {
    "FECHA_RESOLUCION": DATES,
    "HORA_DE_INICIO": HOURS,
    "HORA_DE_CIERRE": HOURS,
}
