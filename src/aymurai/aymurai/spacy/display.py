from copy import deepcopy

from spacy import displacy

from aymurai.meta.types import DataItem
from aymurai.spacy.utils import load_base, load_ents
from aymurai.meta.pipeline_interfaces import Transform

AYMURAI_ENTITY_COLORS = {
    # "AYMURAI_ARTICLE": "linear-gradient(90deg, rgba(0,135,162,1) 0%, rgba(0,73,162,1) 100%)",
    # "AYMURAI_CODE_OR_LAW": "linear-gradient(90deg, rgba(0,162,4,1) 0%, rgba(0,143,162,1) 100%)",
    # "AYMURAI_VIOLENCE_QUOTE": "linear-gradient(90deg, rgba(162,77,0,1) 0%, rgba(162,0,0,1) 100%)",
    # "PER": "linear-gradient(90deg, rgba(0,162,4,1) 0%, rgba(0,143,162,1) 100%)",
}


class DocRender(Transform):
    def __init__(
        self, base: str = "es", config: dict = None, ents_field: str = "predictions"
    ):
        self.nlp = load_base(base)
        self.ents_field = ents_field
        self.config = config
        if not self.config:
            self.config = {"colors": AYMURAI_ENTITY_COLORS}

    def __call__(
        self,
        item: DataItem,
        style: str = "ent",
        spans_key: str = "sc",
        limit: int = None,
        paragraphs: int = None,
        config: dict = {},
    ):
        text = item["data"]["doc.text"]
        if limit:
            text = text[:limit]
        if paragraphs:
            pars = text.split("\n")
            paragraphs = min(len(pars), paragraphs)
            text = "\n".join(pars[:paragraphs])
            limit = len(text)

        doc = self.nlp(text)
        doc_len = len(doc)

        config = deepcopy(self.config) | config
        if style == "span":
            config |= {"spans_key": spans_key}

        spans = item[self.ents_field].get("entities", [])
        if style == "span":
            spancats = item[self.ents_field].get("spans", {})
            spans += spancats.get(spans_key, [])

        if limit:
            spans = filter(lambda x: x["start"] < doc_len, spans)
            spans = list(spans)
            ends = map(lambda x: min(x["end"], doc_len), spans)
            spans = [span | {"end": end} for span, end in zip(spans, ends)]

        doc = load_ents(
            doc,
            spans,
            field=f"{style}s",
            spans_key=spans_key,
        )

        return displacy.render(doc, style=style, options=config)
