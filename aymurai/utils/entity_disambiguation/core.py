import copy
import uuid

from aymurai.meta.api_interfaces import DocumentAnnotations
from aymurai.meta.entities import CanonicalEntities


def assign_label_instances(
    predictions: DocumentAnnotations,
) -> DocumentAnnotations:
    """
    Assigns ordered label instance indices (e.g., 1, 2) by appearance.

    Args:
        predictions (DocumentAnnotations): Predictions with canonical IDs assigned.

    Returns:
        DocumentAnnotations: Updated predictions with `aymurai_label_instance`.
    """
    predictions_with_instances = copy.deepcopy(predictions)

    next_index_by_label: dict[str, int] = {}
    instance_by_label_and_id: dict[tuple[str, str], int] = {}

    for document in predictions_with_instances:
        if not document.labels:
            continue

        for label in document.labels:
            label_name = label.attrs.aymurai_label
            entity_id = label.attrs.canonical_entity_id

            if not label_name or entity_id is None:
                continue

            key = (label_name, str(entity_id))
            if key not in instance_by_label_and_id:
                next_index_by_label[label_name] = (
                    next_index_by_label.get(label_name, 0) + 1
                )
                instance_by_label_and_id[key] = next_index_by_label[label_name]

            label.attrs.aymurai_label_instance = instance_by_label_and_id[key]

    return predictions_with_instances


def map_canonical_entities_ner_preds(
    predictions: DocumentAnnotations,
    canonical_entities: CanonicalEntities,
    *,
    include_label_instances: bool = True,
    force_labels: set[str] | None = None,
) -> DocumentAnnotations:
    """
    Applies canonical entity IDs and roles back onto NER predictions.

    Args:
        predictions (DocumentAnnotations): Original predictions to update.
        canonical_entities (CanonicalEntities): Canonical entities with IDs/roles.
        include_label_instances (bool): Whether to assign ordered label instance
            indices (e.g., 1, 2). Defaults to True.
        force_labels (set[str] | None): Labels to remap even if a canonical ID
            already exists.

    Returns:
        DocumentAnnotations: Updated predictions with canonical IDs, roles, and
            optionally `aymurai_label_instance`.
    """
    predictions_mapped = copy.deepcopy(predictions)
    force_labels = force_labels or set()

    new_ids_map = {}

    for document in predictions_mapped:
        if not document.labels:
            continue

        for label in document.labels:
            if not label.attrs:
                continue

            if label.attrs.aymurai_label_subclass is None:
                label.attrs.aymurai_label_subclass = []

            force_remap = label.attrs.aymurai_label in force_labels
            if force_remap:
                label.attrs.canonical_entity_id = None
                label.attrs.aymurai_label_subclass = []

            if (
                label.attrs.canonical_entity_id is None
                and len(label.attrs.aymurai_label_subclass) == 0
            ):
                for ce in canonical_entities:
                    if label.attrs.aymurai_label == ce.aymurai_label:
                        entity_id = ce.entity_id
                        attributes = ce.attributes or {}
                        role = attributes.get("role")
                        aliases = ce.aliases

                        clean_aliases = [str(a).strip().lower() for a in aliases]
                        label_text = (
                            str(label.attrs.aymurai_alt_text or label.text)
                            .strip()
                            .lower()
                        )

                        if label_text in clean_aliases:
                            label.attrs.canonical_entity_id = entity_id
                            if ce.aymurai_label == "PER" and role is not None:
                                label.attrs.aymurai_label_subclass.append(role)
                            break

            elif label.attrs.canonical_entity_id is None:
                key = (
                    label.attrs.aymurai_label,
                    str(label.attrs.aymurai_alt_text).strip(),
                )
                if key not in new_ids_map:
                    new_ids_map[key] = uuid.uuid4()

                label.attrs.canonical_entity_id = new_ids_map[key]

    if include_label_instances:
        return assign_label_instances(predictions_mapped)

    return predictions_mapped
