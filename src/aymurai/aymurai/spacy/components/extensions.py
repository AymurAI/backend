from spacy.tokens import Span

# aymurai attrs:
# key: default_value
AYMURAI_SPAN_ATTRS = {
    "aymurai_score": 0,  # ruler/matcher/model entity/span score
    "aymurai_method": "",  # method used to match (class name)
    "aymurai_date": None,  # datetime when possible
}

for attr, default in AYMURAI_SPAN_ATTRS.items():
    Span.set_extension(attr, default=default)
