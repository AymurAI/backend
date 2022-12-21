from transformers import T5Tokenizer

from aymurai.meta.types import DataItem
from aymurai.spacy.utils import load_base
from aymurai.meta.pipeline_interfaces import Transform


class LenghtCounter(Transform):
    def __init__(
        self,
        use_spacy: bool = True,
        use_hf: bool = True,
        spacy_model: str = "es",
        hf_tokenizer: str = "google/long-t5-local-base",
    ):
        self.use_spacy = use_spacy
        self.use_hf = use_hf

        self._spacy_model = spacy_model
        self._hf_tokenizer = hf_tokenizer

        self.spacy_model = load_base(spacy_model) if self.use_spacy else None
        self.hf_tokenizer = (
            T5Tokenizer.from_pretrained(hf_tokenizer) if self.use_hf else None
        )

    def __call__(self, item: DataItem) -> DataItem:
        text = item["data"]["doc.text"]
        length = {}
        length["char"] = {"len": len(text), "model": None}
        length["words"] = {"len": len(text.split(" ")), "model": None}

        if self.use_spacy:
            doc = self.spacy_model.make_doc(text)
            length["spacy"] = {"len": len(doc), "model": self._spacy_model}

        if self.use_hf:
            input_ids = self.hf_tokenizer(text, return_tensors="pt").input_ids
            length["hf"] = {"len": len(input_ids[0]), "model": self._hf_tokenizer}

        item["metadata"]["length"] = length

        return item
