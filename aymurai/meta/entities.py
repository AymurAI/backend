from __future__ import annotations

import json
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

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
    aymurai_label_instance: int | None = Field(
        None,
        description="Label instance index assigned by order of appearance (e.g., 1, 2, 3).",
    )
    canonical_entity_id: UUID | None = Field(
        None, description="Reference to the canonical entity ID"
    )


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


class EntityRelation(BaseModel):
    """Semantic relation between canonical entities."""

    relation_id: UUID | None = Field(
        None, description="Unique identifier of the relation"
    )
    relation_type: str = Field(
        description="Type of relation (e.g. identifies, resides_in)"
    )
    subject_entity_id: UUID = Field(
        description="Identifier of the subject entity participating in the relation"
    )
    object_entity_id: UUID = Field(
        description="Identifier of the object entity participating in the relation"
    )
    attributes: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional attributes captured for the relation",
    )

    @model_validator(mode="after")
    def assign_relation_id(self) -> EntityRelation:
        """Populate relation_id deterministically when not provided."""

        if self.relation_id is not None:
            return self

        payload = {
            "relation_type": self.relation_type,
            "subject_entity_id": str(self.subject_entity_id),
            "object_entity_id": str(self.object_entity_id),
            "attributes": self.attributes,
        }
        seed = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        object.__setattr__(self, "relation_id", uuid5(NAMESPACE_URL, seed))

        return self


class CanonicalEntity(BaseModel):
    """Canonical representation of an entity cluster."""

    entity_id: UUID | None = Field(
        None, description="Unique identifier for the canonical entity"
    )
    aymurai_label: str = Field(title="AymurAI label")
    canonical_text: str = Field(description="Preferred textual form for the entity")
    aliases: list[str] = Field(
        default_factory=list,
        description="Alternative surface forms observed for the entity",
    )
    attributes: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata for the entity"
    )

    @model_validator(mode="after")
    def validate_entity_id(self) -> CanonicalEntity:
        """
        Ensure the canonical entity has an entity_id; if missing, create a surrogate UUID and set it.

        Returns:
            CanonicalEntity: the validated model instance (self).
        """
        # If entity_id is already set, nothing to do.
        if self.entity_id is not None:
            return self

        payload = {
            "aymurai_label": self.aymurai_label,
            "canonical_text": self.canonical_text,
            "aliases": sorted(self.aliases),
            "attributes": self.attributes,
        }
        seed = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        object.__setattr__(self, "entity_id", uuid5(NAMESPACE_URL, seed))

        return self


class CanonicalEntities(BaseModel):
    """Collection of canonical entities."""

    canonical_entities: list[CanonicalEntity]
