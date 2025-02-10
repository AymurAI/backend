import re
from glob import glob
from copy import deepcopy
from itertools import groupby

from numpy import cumsum
from more_itertools import unzip, collapse

from aymurai.meta.types import DataItem
from aymurai.meta.entities import Entity
from aymurai.utils.json_data import load_json


def join_label_category(spans: list[dict]) -> dict:
    """join entity & entity-category (labelstudio) on one object"""
    span = {}
    for s in spans:
        span.update(s)
    return span


def reformat_entity(text: str, span: dict) -> dict:
    """
    reformat labelstudio entity to aymurai

    Args:
        text (str): text containing the entity to reformat
        span (dict): span to reformat

    Returns:
        dict: aymurai formatted entity
    """
    context_offset = 10

    # start/end tokens (do not confuse with start/end characters)
    start, end = span["start"], span["end"]

    soffset = max(0, start - context_offset)
    eoffset = min(len(text), end + context_offset)

    entity = Entity(
        start=span["start"],
        end=span["end"],
        label=span["labels"][0],
        text=text[span["start"] : span["end"]],
        context_pre=text[soffset : span["start"]],
        context_post=text[span["end"] : eoffset],
        attrs={"aymurai_label": span["labels"][0]},
    )
    return entity.model_dump()


def parse_annots(data: dict) -> dict:
    """
    parse annotations from labelstudio-data

    Args:
        data (dict): labelstudio-json export

    Returns:
        dict: categories & entities (aymurai format)
    """
    doc_text = data["data"]["text"]

    annotations = data["annotations"][0]["result"]
    annotations = list(annotations)

    # filter span entities
    spans = filter(lambda x: x["type"] in ["labels", "choices"], annotations)
    spans = map(lambda x: x["value"], spans)
    spans = sorted(spans, key=lambda x: x["start"])

    _, group = unzip(groupby(spans, key=lambda x: (x["start"], x["end"], x["text"])))
    group = map(join_label_category, group)

    spans = list(group)
    spans = map(lambda span: reformat_entity(doc_text, span), spans)
    spans = list(spans)

    # categories
    categories = filter(lambda x: x.get("type") == "textarea", annotations)
    categories = {cat["from_name"]: cat["value"]["text"][0] for cat in categories}

    return {
        "categories": categories,
        "entities": spans,
    }


def load_conll_annots(basepath: str) -> list[str]:
    """
    load annotations (CoNLL format)

    Args:
        basepath (dict): path where to look the annotations (conll file)

    Returns:
        list[str]: list containing the annotations of different docs
    """
    # read annotations
    conll_path = glob(f"{basepath}/*.conll")[0]
    with open(conll_path) as file:
        annotations = file.read()

    # remove header
    annotations = annotations.replace("-DOCSTART- -X- O\n", "")

    # remove unuseful tags
    annotations = annotations.replace(" -X- _", "")

    # split annotations corresponding to different documents
    annotations = annotations.split("\n\n")

    # pop empty element
    if "" in annotations:
        _ = annotations.pop(annotations.index(""))

    return annotations


def parse_conll_annots(item: DataItem, annotation: str) -> DataItem:
    """
    parse CoNLL annotations and document to split the text by paragraphs

    Args:
        item (DataItem): aymurai dataitem
        annotation (str): CoNLL annotation corresponding to item

    Returns:
        DataItem: aymurai dataitem with CoNLL annotation
    """
    item = deepcopy(item)

    # document text
    doc = item["data"]["doc.text"]

    # NOTE this should be donde as part of the preprocessing
    # replace '\t' and '\xa0' for white space
    doc = re.sub(r"(?:\t|\xa0)+", " ", doc)

    # remove multiple spaces except new lines
    doc = re.sub(r"[^\S\r\n]+", " ", doc)

    # replace multiple new lines with just one break
    doc = re.sub(r"\n+", "\n", doc)

    # split document by line
    splitted_doc = doc.splitlines()

    # number of tokens per line
    n_tokens = [len(line.split()) for line in splitted_doc]

    # indexes where a new line character must be inserted to separate paragraph
    idx = [idx + i for i, idx in enumerate(cumsum(n_tokens))]

    # split annotations by line
    splitted_annotation = annotation.splitlines()

    # insert new line character where needed
    for i in idx:
        splitted_annotation.insert(i, "\n")

    # join the new annotations
    joined_annotation = "\n".join(splitted_annotation)
    joined_annotation = re.sub("\n{3,}", "\n\n", joined_annotation)

    # add CoNLL annotation to dataitem
    item["annotations"]["conll"] = joined_annotation

    return item


def annotation_to_dataitem(annotation: dict) -> DataItem:
    """
    format a whole labelstudio document into the aymurai format

    Args:
        annotation (dict): labelstudio document

    Returns:
        DataItem: aymurai dataitem
    """
    item = {}
    item["path"] = annotation["data"]["meta_info"]["path"]
    item["data"] = {"doc.text": annotation["data"]["text"]}
    annots = parse_annots(annotation)
    item["metadata"] = annots["categories"]
    item["annotations"] = {"entities": annots["entities"]}
    return item


def load_annotations(basepath: str) -> list[DataItem]:
    """
    load all annotations from `basepath`. this directory must contain
    the annotations both in json and conll formats.
    internally, use glob to look for all the annotation files files inside `basepath`.

    Args:
        basepath (str): path where to look for the annotations (json and conll files)

    Returns:
        list[DataItem]: list of dataitems (aymurai format)
    """
    paths = glob(f"{basepath}/*.json")
    items = map(load_json, paths)
    items = collapse(items, base_type=dict)
    items = map(annotation_to_dataitem, items)
    coll_annots = load_conll_annots(basepath)
    items = map(parse_conll_annots, items, coll_annots)
    return list(items)
