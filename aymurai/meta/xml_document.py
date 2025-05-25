from pydantic import BaseModel

from aymurai.database.meta.extra import ParagraphPredictionPublic


class XMLTextFragment(BaseModel):
    text: str
    normalized_text: str
    start: int
    end: int
    fragment_index: int
    paragraph_index: int


class ParagraphMetadata(BaseModel):
    start: int
    end: int
    fragments: list[XMLTextFragment]
    xml_file: str


class XMLParagraph(BaseModel):
    plain_text: str
    metadata: ParagraphMetadata
    hash: str | int | None = None
    __pred_indices: list[int] = []


class XMLParagraphWithParagraphPrediction(XMLParagraph):
    paragraph_prediction: ParagraphPredictionPublic
