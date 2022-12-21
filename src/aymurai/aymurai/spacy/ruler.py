from functools import partial

from aymurai.meta.types import DataItem
from aymurai.meta.pipeline_interfaces import Transform

from .utils import load_base, format_entity


class SpacyRulerPipeline(Transform):
    def __init__(
        self,
        base: str,
        steps: list[tuple[str, dict]],
        context_offset: int = 10,
    ):
        global __nlp
        __nlp = load_base(base)
        self.nlp = __nlp

        for pipe, kwargs in steps:
            __nlp.add_pipe(pipe, config=kwargs)

        self.offset = context_offset

    def __call__(self, item: DataItem) -> DataItem:
        doc = __nlp.pipe([item["data"]["doc.text"]])
        doc = list(doc)[0]

        _format_entity = partial(format_entity, offset=self.offset)
        formatted_ents = map(_format_entity, doc.ents)
        item["data"]["entities"] = list(formatted_ents)

        return item
