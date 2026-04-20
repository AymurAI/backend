import re
import unicodedata


def _normalize_document_characters(text: str) -> str:
    """
    Apply character-level normalization without changing document structure.

    Args:
        text (str): Raw extracted document text.

    Returns:
        str: Character-normalized text.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"(“|”)", '"', text)
    text = text.replace("\\/", "/")
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text


def _normalize_paragraph_text(text: str) -> str:
    """
    Normalize text inside a single paragraph while preserving paragraph borders.

    Args:
        text (str): Paragraph text.

    Returns:
        str: Normalized paragraph content.
    """
    text = re.sub(r"[ \t]*\n[ \t]*", "\n", text.strip())

    # delete newline if NEXT char is:
    # - lower character or a number
    # - punctuation
    text = re.sub(r"\n([a-z0-9;:,\.])", r" \g<1>", text)

    # delete newline if PREVIOUS char is:
    # - quote mark
    # - punctuations (except '.' because possible ambiguity)
    text = re.sub(r"([\w,\"-])\n", r"\g<1> ", text)

    # cleanup some junk
    text = re.sub(r"[-]{2,}", "-", text)
    text = re.sub(r"\.-", ".", text)
    text = re.sub(r" {2,}", " ", text)
    return text.strip()


def document_normalize(text: str, *, preserve_paragraphs: bool = False) -> str:
    """Normalize extracted text from documents.

    Args:
        text (str): Document text.
        preserve_paragraphs (bool): Preserve blank-line paragraph boundaries. Defaults to False.

    Returns:
        str: Normalized document text.
    """
    text = _normalize_document_characters(text)

    if preserve_paragraphs:
        paragraphs = [
            _normalize_paragraph_text(paragraph)
            for paragraph in re.split(r"\n\s*\n+", text)
            if paragraph.strip()
        ]
        return "\n\n".join(paragraphs)

    text = _normalize_paragraph_text(text)
    return re.sub(r"\n{2,}", "\n", text)
