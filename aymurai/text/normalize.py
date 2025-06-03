import re
import unicodedata


def document_normalize(text: str) -> str:
    """Normalize extracted text from documents
    * join invalid newlines
    * remove continous whitespaces

    Args:
        text (str): document

    Returns:
        str: normalized
    """

    # normalize character encodings
    # text = unicodedata.normalize("NFKD", text)
    text = unicodedata.normalize("NFKC", text)

    # remove continous whitespace
    text = re.sub(r" {2,}", r" ", text)

    # delete newline if NEXT char is:
    # - lower character or a number
    # - punctuanion
    text = re.sub(r"\n([a-z0-9;:,\.])", r" \g<1>", text)

    # delete newline if PREVIOUS char is:
    # - quote mark
    # - punctuanions (except '.' because possible ambiguity)
    text = re.sub(r"([\w,\"-])\n", r"\g<1> ", text)

    # cleanup some junk
    # - multiple newlines, hyphens
    text = re.sub(r"\n{2,}", "\n", text)
    text = re.sub(r"[-]{2,}", "-", text)
    text = re.sub(r"\.-", ".", text)

    # quotation marks
    text = re.sub(r"(“|”)", '"', text)

    # scaped slashes
    text = text.replace("\/", "/")

    return text
