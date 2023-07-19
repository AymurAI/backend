import os
import re
import zipfile
from difflib import Differ, SequenceMatcher

import textract
import xmltodict
import numpy as np
import pandas as pd
from unidecode import unidecode
from more_itertools import flatten, zip_offset

from aymurai.utils.misc import get_element
from aymurai.text.extraction import extract_document

IA2_LABELS = [
    "SECRETARIX",
    "EDAD",
    "NER",
    "NUM",
    "CBU",
    "DIRECCION",
    "JUEZX",
    "PASAPORTE",
    "FECHA",
    "ESTUDIOS",
    "IP",
    "PERIODO",
    "USUARIX",
    "ARTICULO",
    "FISCAL",
    "LOC",
    "LEY",
    "CUIT",
    "BANCO",
    "DEFENSORX",
    "PER",
    "LINK",
    "NACIONALIDAD",
    "DNI",
    "CUIJ",
]


def norm_ia2_label(text) -> str | float:
    if not isinstance(text, str):
        return np.nan

    text = unidecode(text)
    text = re.sub(r"\W", "", text)

    return text if text in IA2_LABELS else np.nan


def label_to_conll_format(labels: pd.Series) -> pd.Series:
    labels = labels.copy()

    if len(labels.dropna()) == 0:
        return labels

    # tag the labels
    labels = "B-" + labels
    mask = labels.values[1:] == labels.values[:-1]
    mask = np.insert(mask, 0, False)
    labels.loc[mask] = labels.loc[mask].str.replace("B-", "I-")
    labels.fillna("O", inplace=True)

    return labels


def mapping2conll(
    df: pd.DataFrame,
    filename: str,
    text_column: str = "original",
    label_column: str = "label",
):
    dir = os.path.dirname(filename)
    os.makedirs(dir, exist_ok=True)
    with open(filename, "w") as file:
        print("-DOCSTART- -X- O", file=file)
        for _, row in df.iterrows():
            text = row[text_column]
            label = row[label_column]
            print(f"{text} -X- _ {label}" if text != " " else "", file=file)


def _load_xml_from_odt(path: str, xmlfile: str = "styles.xml") -> str:
    """load xml file inside an odt

    Args:
        path (str): path to odt file
        xmlfile (str, optional): xml to open. Defaults to 'styles.xml'.

    Returns:
        str: xml content
    """
    with zipfile.ZipFile(path, "r") as odt:
        if xmlfile not in odt.namelist():
            return ""
        with odt.open(xmlfile) as file:
            content = file.read().decode("utf-8")

    return content


def get_header(path: str) -> list[str]:
    """Extract header from styles.xml inside a ODT file

    Args:
        path (str): path to odt file

    Returns:
        list[str]: header lines
    """
    styles_xml_content = _load_xml_from_odt(path)
    styles_dict = xmltodict.parse(styles_xml_content)
    header_root = get_element(
        styles_dict,
        levels=[
            "office:document-styles",
            "office:master-styles",
            "style:master-page",
            1,
            "style:header",
            "text:p",
        ],
    )

    if not isinstance(header_root, list):
        return []

    return [element.get("#text") for element in header_root if element.get("#text")]


def tokenize(text: str) -> list[str]:
    tokens = map(str.split, text.splitlines())
    tokens = flatten(tokens)
    return list(tokens)


def norm_label(text) -> str | float:
    if not isinstance(text, str):
        return np.nan

    text = unidecode(text)
    text = re.sub(r"\W", "", text)
    return text


def aligner(anonymized: str, original: str):
    anon_lines = list(map(str.strip, anonymized.splitlines()))
    orig_lines = list(map(str.strip, original.splitlines()))

    seqmatcher = SequenceMatcher(None, anon_lines, orig_lines)
    matches = seqmatcher.get_matching_blocks()

    offset_lines = matches[0]

    anon_offset = "\n".join(anon_lines[: offset_lines.a])
    anon_offset = len(anon_offset)

    orig_offset = "\n".join(orig_lines[: offset_lines.b])
    orig_offset = len(orig_offset)

    mapping = pd.DataFrame(
        [
            {"original": t1 or "", "anonymized": t2 or ""}
            for t1, t2 in zip_offset(
                reversed(tokenize(original[:orig_offset])),
                reversed(tokenize(anonymized[:anon_offset])),
                offsets=(0, 0),
                longest=True,
            )
        ]
    ).iloc[::-1]

    anon_tokens = [t.strip() for t in tokenize(anonymized[anon_offset:])]
    orig_tokens = [t.strip() for t in tokenize(original[orig_offset:])]

    seqmatcher = SequenceMatcher(None, anon_tokens, orig_tokens)
    matches = seqmatcher.get_matching_blocks()

    for match1, match2 in zip(matches, matches[1:]):
        _aux = {
            "original": orig_tokens[match1.b : match1.b + match1.size],
            "anonymized": anon_tokens[match1.a : match1.a + match1.size],
        }
        mapping = pd.concat([mapping, pd.DataFrame(_aux)], ignore_index=True)

        diff = Differ().compare(
            anon_tokens[match1.a + match1.size : match2.a],
            orig_tokens[match1.b + match1.size : match2.b],
        )
        diff = list(diff)
        label_candidate = [t[2:].strip() for t in diff if t.startswith("-")]
        text = [t[2:].strip() for t in diff if t.startswith(("+", " "))]

        if not label_candidate:
            continue

        label = "/".join(label_candidate)
        _aux = [{"original": t, "anonymized": label} for i, t in enumerate(text)]

        mapping = pd.concat([mapping, pd.DataFrame(_aux)], ignore_index=True)

    return mapping.reset_index(drop=True)


def add_empty_lines_between_paragraphs(
    original: str, processed: pd.DataFrame
) -> pd.DataFrame:
    splitted = original.splitlines()
    n_tokens = [len(line.split()) for line in splitted if line.split()]
    idx = [idx + i for i, idx in enumerate(np.cumsum(n_tokens))]

    for i in idx:
        try:
            processed = pd.DataFrame(
                np.insert(
                    processed.values,
                    i,
                    values=[""] * len(processed.columns),
                    axis=0,
                ),
                columns=processed.columns,
            )
        except Exception:
            pass

    return processed


def process(item: dict) -> pd.DataFrame:
    original = item["doc.text"]
    path = item["anonymized_path"]
    anonymized = textract.process(path, extension="odt", output_encoding="utf-8")
    anonymized = anonymized.decode("utf-8")

    # patch header loading in anonymized files
    anon_header = "\n".join(get_header(path))
    anonymized = anon_header + "\n" + anonymized

    mapping = aligner(anonymized, original)
    mapping = add_empty_lines_between_paragraphs(original, mapping)

    # set labels
    mask = mapping["original"] != mapping["anonymized"]
    if len(mask) == 0:
        mapping["label"] = "O"
        return mapping

    labels = mapping.loc[mask, "anonymized"]
    labels = labels.apply(norm_ia2_label).dropna()
    mapping["label"] = labels
    mapping["label"] = label_to_conll_format(mapping["label"])
    return mapping
