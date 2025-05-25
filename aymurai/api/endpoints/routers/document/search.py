import unicodedata
import uuid

import numpy as np
import pandas as pd
import regex
from fastapi import Depends, HTTPException
from fastapi.routing import APIRouter
from more_itertools import flatten
from pydantic import UUID4, UUID5
from sklearn.cluster import DBSCAN
from sklearn.feature_extraction.text import CountVectorizer
from sqlmodel import Session

from aymurai.database.crud.prediction import read_document_prediction_paragraphs
from aymurai.database.schema import Document, ModelType
from aymurai.database.session import get_session
from aymurai.logger import get_logger
from aymurai.meta.entities import DocLabel

logger = get_logger(__name__)

router = APIRouter()


# Normalize helper
def normalize_text(text):
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = regex.sub(r"\s+", " ", text)
    text = regex.sub(r"\p{P}", "", text)
    return text.lower()


def cluster_entities(entities: list[DocLabel], eps: float = 0.01, min_samples: int = 2):
    """
    Cluster entity texts in a group and return a DataFrame with columns:
    text, norm_text, index, cluster. Uses binary vectorization and Jaccard-DBSCAN.
    """

    indexed_entities = [(i, entity) for i, entity in enumerate(entities)]
    indexed_entities = sorted(indexed_entities, key=lambda x: x[1].attrs.aymurai_label)

    # Prepare raw and normalized texts
    texts = [ent[1].text for ent in indexed_entities]
    norm_texts = [normalize_text(t) for t in texts]

    # --------- Binary vectorization of words ----------------
    vectorizer = CountVectorizer(binary=True, token_pattern=r"\b\w+\b")
    matrix = vectorizer.fit_transform(
        norm_texts
    )  # sparse matrix (n_samples x n_features)

    # --------- Jaccard distance matrix ----------------
    ints = (matrix @ matrix.T).toarray()
    row_sums = matrix.sum(axis=1).A1
    union = row_sums[:, None] + row_sums[None, :] - ints
    # Avoid division by zero and compute distances
    with np.errstate(divide="ignore", invalid="ignore"):
        X = 1 - (ints / union)
    X[union == 0] = 1.0

    # -------- DBSCAN ----------------------------------------------------
    db = DBSCAN(eps=eps, min_samples=min_samples, metric="precomputed")
    labels = db.fit_predict(X)

    # Merge clusters by overlapping centroids
    unique_lbls = sorted(set(labels) - {-1})
    if unique_lbls:
        # build centroid binary vectors
        centroid_vectors = []
        for lbl in unique_lbls:
            mat = matrix[labels == lbl]
            centroid = (mat.sum(axis=0) > 0).A1  # boolean mask
            centroid_vectors.append(centroid)

        C = np.vstack(centroid_vectors).astype(bool)
        sim = (C.astype(int) @ C.T.astype(int)) > 0
        mapping = {
            lbl: unique_lbls[int(np.argmax(sim[idx]))]
            for idx, lbl in enumerate(unique_lbls)
        }
        labels = [mapping.get(lbl, -1) for lbl in labels]

    # Build results DataFrame
    df = (
        pd.DataFrame(
            {
                "id": [ent[1].id for ent in indexed_entities],
                "index": [ent[0] for ent in indexed_entities],
                "paragraph_id": [ent[1].fk_paragraph for ent in indexed_entities],
                "label": [ent[1].attrs.aymurai_label for ent in indexed_entities],
                "text": texts,
                "norm_text": norm_texts,
                "cluster": labels,
            }
        )
        .sort_values("cluster")
        .reset_index(drop=True)
    )
    df["id"] = df["id"].astype(uuid.UUID)
    df["paragraph_id"] = df["paragraph_id"].astype(uuid.UUID)
    df.set_index("id", inplace=True)
    df.sort_values(by=["cluster", "index"], inplace=True)

    return df


@router.get("/pipeline/{pipeline_type}/document/{document_id}/search")
async def search(
    pipeline_type: ModelType,
    document_id: UUID4 | UUID5,
    query: str | None = None,
    label_id: UUID4 | UUID5 | None = None,
    session: Session = Depends(get_session),
) -> list[DocLabel] | None:
    # ———————— Sanity check ————————————————————————————————————————————————————————
    if (not query and not label_id) or (query and label_id):
        raise HTTPException(
            status_code=400,
            detail="Either query or label_id must be provided",
        )

    document = session.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # ———————— Get annotations ————————————————————————————————————————————————————————
    annotations = read_document_prediction_paragraphs(
        session=session,
        document_id=document_id,
        model_type=pipeline_type,
    )

    labels = [para.prediction.labels for para in annotations if para.prediction]
    entities = list(flatten(labels))

    clusters_df = cluster_entities(entities)

    if label_id:
        label_cluster = clusters_df.loc[label_id, "cluster"]
        cluster = clusters_df[clusters_df["cluster"] == label_cluster]

    elif query:
        query = normalize_text(query)
        cluster = cluster[cluster["norm_text"].str.contains(query, na=False)]

    if cluster.empty:
        return None

    indices = cluster.index.tolist()
    entities = [entities[i] for i in indices]

    return entities
