from typing import List, Optional

from pydantic import BaseModel, Field, validator

from aymurai.utils.misc import get_sort_key


class TextRequest(BaseModel):
    """Datatype for a text span request"""

    text: str = Field(
        ...,
        description="text field to run prediction",
    )


class DocLabelAttributes(BaseModel):
    """Datatype for a label's  attributes"""

    aymurai_label: str = Field(title="AymurAI label")
    aymurai_label_subclass: Optional[list[str]] = Field(
        description="AymurAI label subcategory"
    )
    aymurai_alt_text: Optional[str] = Field(
        description="alternative form for text formating (i.e. datetimes)"
    )
    aymurai_method: Optional[str] = Field("method used on the prediction label")
    aymurai_score: Optional[float] = Field("score for prediction")


class DocLabel(BaseModel):
    """Datatype for a document label"""

    text: str = Field(description="raw text of entity")
    start_char: int = Field(
        description="start character of the span in relation of the full text"
    )
    end_char: int = Field(
        description="last character of the span in relation of the full text"
    )
    attrs: DocLabelAttributes


class DocumentInformation(BaseModel):
    """Datatype for a document information with all labels"""

    document: str = Field(description="processed text")
    labels: List[DocLabel]


class ParagraphFragment(BaseModel):
    """Datatype for a document paragraph fragment"""

    text: str
    normalized_text: str
    start: int
    end: int
    fragment_index: int
    paragraph_index: int


class ParagraphMetadata(BaseModel):
    """Datatype for a document paragraph metadata"""

    start: int
    end: int
    fragments: List[ParagraphFragment]
    xml_file: str


class DocumentParagraph(BaseModel):
    """Datatype for a document paragraph"""

    plain_text: str
    metadata: ParagraphMetadata


class Document(BaseModel):
    """Datatype for a document"""

    paragraphs: List[DocumentParagraph]

    @validator("paragraphs")
    def paragraphs_validator(
        cls, paragraphs: List[DocumentParagraph]
    ) -> List[DocumentParagraph]:
        # Filter out empty paragraphs
        non_empty_paragraphs = [
            paragraph for paragraph in paragraphs if paragraph.plain_text.strip()
        ]

        # Sort paragraphs based on the xml_file type
        sorted_paragraphs = sorted(non_empty_paragraphs, key=get_sort_key)

        return sorted_paragraphs
