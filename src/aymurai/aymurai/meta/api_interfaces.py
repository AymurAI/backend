from typing import List, Optional

from pydantic import Field, BaseModel


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
        default=[],
        description="AymurAI label subcategory",
    )
    aymurai_alt_text: Optional[str] = Field(
        default=None,
        description="alternative form for text formating (i.e. datetimes)",
    )
    aymurai_method: Optional[str] = Field(
        default=None,
        description="method used on the prediction label",
    )
    aymurai_score: Optional[float] = Field(
        default=None,
        description="score for prediction",
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
