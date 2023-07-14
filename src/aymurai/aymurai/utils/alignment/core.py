import os
import re
import zipfile
from difflib import Differ, SequenceMatcher

import textract
import xmltodict
import numpy as np
import pandas as pd
from unidecode import unidecode
from more_itertools import zip_offset

from aymurai.utils.misc import get_element


def mapping2conll(df, filename):
    dir = os.path.dirname(filename)
    os.makedirs(dir, exist_ok=True)
    with open(filename, "w") as file:
        print("-DOCSTART- -X- O", file=file)
        for _, row in df.iterrows():
            text = row["original"]
            label = row["conll_label"]
            print(f"{text} -X- _ {label}" if text != " " else "", file=file)


def load_styles_from_odt(odt_file_path):
    styles_content = ""

    with zipfile.ZipFile(odt_file_path, "r") as odt_zip:
        if "styles.xml" in odt_zip.namelist():
            with odt_zip.open("styles.xml") as styles_file:
                styles_content = styles_file.read().decode("utf-8")

    return styles_content


def get_header(path: str) -> list[str]:
    styles_xml_content = load_styles_from_odt(path)
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


def tokenize(text):
    tokens = []
    lines = text.splitlines()

    for line in lines:
        tokens.extend(line.split())

    return tokens


def norm_label(text) -> str | float:
    if not isinstance(text, str):
        return np.nan

    text = unidecode(text)
    text = re.sub(r"\W", "", text)
    return text


def aligner(anonymized: str, original: str):
    anon_lines = anonymized.splitlines()
    # orig_lines = original.splitlines()
    orig_lines = [line.strip() for line in original.splitlines()]

    seqmatcher = SequenceMatcher(None, anon_lines, orig_lines)
    matches = seqmatcher.get_matching_blocks()

    offset_lines = matches[0]

    anon_offset = "\n".join(anon_lines[: offset_lines.a])
    anon_offset = len(anon_offset)

    orig_offset = "\n".join(orig_lines[: offset_lines.b])
    orig_offset = len(orig_offset)

    mapping = pd.DataFrame(
        [
            {
                "original": t1 if t1 else "",
                "anonymized": t2 if t2 else "",
                "ia2_label": None,
                # "ia2_norm_label": None,
            }
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

        if len(label_candidate) > 1:
            # print(f"multiple labels:\n{text}\n{label_candidate}")
            label = "/".join(
                set([re.sub(",", "", candidate) for candidate in label_candidate])
            )
            _aux = [
                {
                    "original": t,
                    "anonymized": label,
                    "ia2_label": label,
                }
                for i, t in enumerate(text)
            ]

        else:
            label = "/".join(label_candidate)
            _aux = [
                {
                    "original": t,
                    "anonymized": label,
                    "ia2_label": label,
                }
                for i, t in enumerate(text)
            ]

        mapping = pd.concat([mapping, pd.DataFrame(_aux)], ignore_index=True)

    if "ia2_label" not in mapping:
        mapping["ia2_label"] = np.nan

    mapping["ia2_norm_label"] = mapping["ia2_label"].apply(norm_label)

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
                    processed.values, i, values=[" "] * len(processed.columns), axis=0
                ),
                columns=processed.columns,
            )
        except Exception:
            pass

    return processed


def aymurai_align(df: pd.DataFrame, conll: str) -> pd.DataFrame:
    df = df.copy()
    aymurai_conll = pd.DataFrame(
        [line.split() for line in conll.splitlines()],
        columns=["aymurai_v1", "aymurai_v1_label"],
    )

    # normalize labels to easy use
    def normalize(x):
        if not isinstance(x, str):
            return x
        return re.sub(r"[BI]-", "", x)

    aymurai_conll["aymurai_v1_label"] = aymurai_conll["aymurai_v1_label"].apply(
        normalize
    )
    aymurai_conll["aymurai_v1_label"] = aymurai_conll["aymurai_v1_label"].replace(
        "O", np.nan
    )

    seqmatcher = SequenceMatcher(None, df["original"], aymurai_conll["aymurai_v1"])
    matches = seqmatcher.get_matching_blocks()

    for match in matches:
        orig = df.iloc[match.a : match.a + match.size]
        aymu = aymurai_conll.iloc[match.b : match.b + match.size]

        # we assume that in this alignment the two dataframes have the same len and are aligned.
        df.loc[orig.index, aymu.columns] = aymu.values
    return df


def process(item):
    original = item["doc.text"]
    path = item["anonymized_path"]
    anonymized = textract.process(path, extension="odt", output_encoding="utf-8")
    anonymized = anonymized.decode("utf-8")

    # patch header loading in anonymized files
    anon_header = "\n".join(get_header(path))
    anonymized = anon_header + "\n" + anonymized

    processed = aligner(anonymized, original)
    processed = add_empty_lines_between_paragraphs(original, processed)

    return processed
