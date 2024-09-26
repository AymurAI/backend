from copy import deepcopy

from spacy import displacy

from aymurai.meta.types import DataItem
from aymurai.utils.misc import get_element
from aymurai.meta.pipeline_interfaces import Transform
from aymurai.utils.entities import load_base, load_ents


def add_score_to_label(ent, add_subclass: bool = True):
    ent = deepcopy(ent)
    score = get_element(ent, ["attrs", "aymurai_score"]) or None
    cats = get_element(ent, ["attrs", "aymurai_label_subclass"]) or None
    label = get_element(ent, ["attrs", "aymurai_label"]) or ""

    if cats and add_subclass:
        element = get_element(cats, [0]) or ""
        label += f"|{element}"
    label += f"|{score or '':1.2f}"

    ent["label"] = label
    return ent


def set_color(ent, mapping: dict):
    ent = deepcopy(ent)
    label = ent["label"]
    color = mapping.get(label)
    ent["attrs"]["render_color"] = color
    return ent


class DocRender(Transform):
    """
    Render a document with displacy
    """

    def __init__(
        self, base: str = "es", config: dict = {}, ents_field: str = "predictions"
    ):
        """
        Args:
            base (str, optional): spacy model. Defaults to "es".
            config (dict, optional): displacy config. Defaults to {}.
            ents_field (str, optional): field with entities. Defaults to "predictions".

        """
        self.nlp = load_base(base)
        self.ents_field = ents_field
        self.config = config

    def __call__(
        self,
        item: DataItem,
        style: str = "ent",
        spans_key: str = "sc",
        limit: int = None,
        paragraphs: int = None,
        config: dict = {},
    ):
        """
        Render a document with displacy

        Args:
            item (DataItem): data item
            style (str, optional): displacy style. Defaults to "ent".
            spans_key (str, optional): spans key. Defaults to "sc".
            limit (int, optional): limit text length. Defaults to None.
            paragraphs (int, optional): limit paragraphs. Defaults to None.
            config (dict, optional): displacy config. Defaults to {}.

        Returns:
            dict: displacy data
        """
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

        colors = {ent["label"]: ent["attrs"].get("render_color") for ent in spans}
        colors = {k: v for k, v in colors.items() if v}

        config_colors = get_element(config, ["colors"]) or {}
        config["colors"] = config_colors | colors

        return displacy.render(doc, style=style, options=config)
