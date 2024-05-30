from typing import List, Optional

from pydantic import Field, BaseModel, validator


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
        default=[], description="AymurAI label subcategory"
    )
    aymurai_alt_text: Optional[str] = Field(
        default=None, description="alternative form for text formating (i.e. datetimes)"
    )
    aymurai_method: Optional[str] = Field(
        default=None, description="method used on the prediction label"
    )
    aymurai_score: Optional[float] = Field(
        default=None, description="score for prediction"
    )


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


class DocumentAnnotations(BaseModel):
    """Datatype for document annotations"""

    data: List[DocumentInformation]


class Document(BaseModel):
    document: list[str]
    header: list[str] | None
    footer: list[str] | None


class XMLParagraphFragment(BaseModel):
    """Datatype for a XML document paragraph fragment"""

    text: str
    normalized_text: str
    start: int
    end: int
    fragment_index: int
    paragraph_index: int


class XMLParagraphMetadata(BaseModel):
    """Datatype for a XML document paragraph metadata"""

    start: int
    end: int
    fragments: List[XMLParagraphFragment]
    xml_file: str


class XMLDocumentParagraph(BaseModel):
    """Datatype for a XML docx paragraph"""

    plain_text: str
    metadata: XMLParagraphMetadata


class XMLDocument(BaseModel):
    """Datatype for a document"""

    paragraphs: List[XMLDocumentParagraph]

    @validator("paragraphs")
    def paragraphs_validator(
        cls, paragraphs: List[XMLDocumentParagraph]
    ) -> List[XMLDocumentParagraph]:
        # Filter out empty paragraphs
        non_empty_paragraphs = [
            paragraph for paragraph in paragraphs if paragraph.plain_text.strip()
        ]

        return non_empty_paragraphs
