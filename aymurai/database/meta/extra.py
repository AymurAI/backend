from aymurai.database.schema import PredictionPublic, ParagraphPublic, DocumentPublic


class ParagraphPredictionPublic(ParagraphPublic):
    prediction: PredictionPublic | None = None


class DocumentPredictionPublic(DocumentPublic):
    paragraphs: list[ParagraphPredictionPublic] | None = None
