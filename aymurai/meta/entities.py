import uuid

from pydantic import BaseModel, Field, model_validator


class EntityAttributes(BaseModel):
    """Datatype for a label's  attributes"""

    aymurai_label: str = Field(title="AymurAI label")
    aymurai_label_subclass: list[str] | None = Field(
        default_factory=list,
        description="AymurAI label subcategory",
    )
    aymurai_alt_text: str | None = Field(
        None,
        description="Alternative form for text formating (i.e. datetimes)",
    )
    aymurai_alt_start_char: int | None = Field(
        None,
        description="Start character of the alternative span in relation of the full text",
    )
    aymurai_alt_end_char: int | None = Field(
        None,
        description="Last character of the alternative span in relation of the full text",
    )
    aymurai_method: str | None = Field(
        None,
        description="Method used on the prediction label",
    )
    aymurai_score: float | None = Field(None, description="Score for prediction")


class Entity(BaseModel):
    start: int
    end: int
    label: str | None = None
    text: str
    start_char: int
    end_char: int
    context_pre: str = ""
    context_post: str = ""
    attrs: EntityAttributes | None = None


class DocLabel(BaseModel):
    """Datatype for a document label"""

    id: str | None = None
    fk_paragraph: str | None = None

    text: str = Field(
        description="raw text of entity",
        # alias=AliasChoices(["text", "document"]),
    )
    start_char: int = Field(
        description="start character of the span in relation of the full text"
    )
    end_char: int = Field(
        description="last character of the span in relation of the full text"
    )
    attrs: EntityAttributes

    @model_validator(mode="after")
    def _(self) -> "DocLabel":
        """Validate the DocLabel attributes."""
        if not self.id:
            self.id = str(uuid.uuid5(uuid.NAMESPACE_DNS, self.attrs.model_dump_json()))
        return self
