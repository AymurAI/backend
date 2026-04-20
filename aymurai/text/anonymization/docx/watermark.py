from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.opc.constants import RELATIONSHIP_TYPE
from docx.oxml.shared import OxmlElement, qn
from docx.shared import Inches, Pt, RGBColor


def _add_hyperlink(
    paragraph,
    text: str,
    url: str,
    font_name: str = "Archivo",
    size: int = 10,
    color: RGBColor = RGBColor(115, 190, 250),
    italic: bool = False,
    bold: bool = True,
    underline: bool = True,
) -> None:
    """
    Adds a formatted hyperlink to a given paragraph in a Word document.

    Notes:
        - This method directly manipulates the underlying XML of the paragraph to insert a hyperlink,
            as python-docx does not natively support hyperlinks.
        - The hyperlink will be appended to the end of the given paragraph.
        - Formatting options (font, size, color, italic, bold, underline) are applied to the hyperlink text.

    Args:
        paragraph: The python-docx paragraph object to which the hyperlink will be added.
        text (str): The display text for the hyperlink.
        url (str): The URL that the hyperlink points to.
        font_name (str, optional): The font name to use for the hyperlink text. Defaults to "Archivo".
        size (int, optional): The font size (in points) for the hyperlink text. Defaults to 10.
        color (RGBColor, optional): The font color as an RGBColor tuple. Defaults to RGBColor(115, 190, 250).
        italic (bool, optional): Whether the hyperlink text should be italicized. Defaults to False.
        bold (bool, optional): Whether the hyperlink text should be bold. Defaults to True.
        underline (bool, optional): Whether the hyperlink text should be underlined. Defaults to True.

    Raises:
        ValueError: If the paragraph is not a valid python-docx paragraph object.
    """
    # Create the hyperlink relationship
    part = paragraph.part
    r_id = part.relate_to(url, RELATIONSHIP_TYPE.HYPERLINK, is_external=True)

    # Create the hyperlink element
    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("r:id"), r_id)

    # Create a new run
    new_run = OxmlElement("w:r")

    # Set run properties (formatting)
    r_pr = OxmlElement("w:rPr")

    # Set font
    if font_name:
        font = OxmlElement("w:rFonts")
        font.set(qn("w:ascii"), font_name)
        font.set(qn("w:hAnsi"), font_name)
        r_pr.append(font)

    # Set color
    if color:
        color_el = OxmlElement("w:color")
        color_el.set(qn("w:val"), f"{color[0]:02x}{color[1]:02x}{color[2]:02x}")
        r_pr.append(color_el)

    # Set italic
    if italic:
        r_pr.append(OxmlElement("w:i"))

    # Set bold
    if bold:
        r_pr.append(OxmlElement("w:b"))

    # Set underline - added for links
    if underline:
        underline_el = OxmlElement("w:u")
        underline_el.set(qn("w:val"), "single")  # single underline
        r_pr.append(underline_el)

    # Set size
    sz = OxmlElement("w:sz")
    sz.set(qn("w:val"), str(size * 2))  # Word uses half-points
    r_pr.append(sz)

    # Add properties to run
    new_run.append(r_pr)

    # Set text
    text_el = OxmlElement("w:t")
    text_el.text = text
    new_run.append(text_el)

    # Add run to hyperlink
    hyperlink.append(new_run)

    # Add hyperlink to paragraph
    paragraph._p.append(hyperlink)


def _add_watermark_to_footer(
    footer,
    alignment,
    font_name: str = "Archivo",
    hyperlink_text: str = "AymurAI",
    hyperlink_url: str = "https://www.aymurai.info/",
    watermark_text: str = "Documento anonimizado por AymurAI",
) -> None:
    """
    Adds a watermark text to the footer of a document.

    Args:
        footer: The footer object to which the watermark will be added.
        alignment: The alignment setting for the paragraph (e.g., left, center, right).
        font_name (str, optional): The font name to use for the watermark text. Defaults to "Archivo".
        hyperlink_text (str, optional): The text to be hyperlinked. Defaults to "AymurAI".
        hyperlink_url (str, optional): The URL to link "AymurAI" to. Defaults to "https://www.aymurai.info/".
        watermark_text (str): The text to be used as the watermark. Defaults to "Documento anonimizado por AymurAI".
    """
    paragraph = footer.add_paragraph()
    paragraph.alignment = alignment

    if hyperlink_url and hyperlink_text in watermark_text:
        parts = watermark_text.split(hyperlink_text, 1)
        before_text = parts[0]
        after_text = parts[1] if len(parts) > 1 else ""

        # Add text before the hyperlink
        if before_text:
            run = paragraph.add_run(before_text)
            run.font.name = "Archivo"
            run.font.color.rgb = RGBColor(192, 192, 192)
            run.font.size = Pt(10)

        # Add hyperlink
        _add_hyperlink(paragraph, hyperlink_text, hyperlink_url)

        # Add text after the hyperlink
        if after_text:
            run = paragraph.add_run(after_text)
            run.font.name = font_name
            run.font.color.rgb = RGBColor(192, 192, 192)
            run.font.size = Pt(10)

    else:
        # Just add the full text without a hyperlink
        run = paragraph.add_run(watermark_text)
        run.font.name = font_name
        run.font.color.rgb = RGBColor(192, 192, 192)
        run.font.size = Pt(10)


def add_footer_watermark(
    doc_path: str,
    font_name: str = "Archivo",
    hyperlink_text: str = "AymurAI",
    hyperlink_url: str = "https://www.aymurai.info/",
    watermark_text: str = "Documento anonimizado por AymurAI",
) -> None:
    """
    Adds a watermark to the footer of each section in a Word document.

    Args:
        doc_path (str): Path to the document.
        font_name (str, optional): The font name to use for the watermark text. Defaults to "Archivo".
        hyperlink_text (str, optional): The text to be hyperlinked. Defaults to "AymurAI".
        hyperlink_url (str, optional): The URL to link "AymurAI" to. Defaults to "https://www.aymurai.info/".
        watermark_text (str, optional): The text to be used as the watermark. Defaults to "Documento anonimizado por AymurAI".
    """
    document = Document(doc_path)
    processed_footers = set()

    for section in document.sections:
        section.footer_distance = Inches(0.1)

        # List of (footer_obj, alignment) tuples
        footers = [(section.footer, WD_ALIGN_PARAGRAPH.RIGHT)]  # Odd/default
        if section.even_page_footer is not None:
            footers.append((section.even_page_footer, WD_ALIGN_PARAGRAPH.LEFT))
        if section.different_first_page_header_footer:
            footers.append((section.first_page_footer, WD_ALIGN_PARAGRAPH.RIGHT))

        for footer, alignment in footers:
            if id(footer) not in processed_footers:
                _add_watermark_to_footer(
                    footer,
                    alignment,
                    font_name=font_name,
                    hyperlink_text=hyperlink_text,
                    hyperlink_url=hyperlink_url,
                    watermark_text=watermark_text,
                )
                processed_footers.add(id(footer))

    document.save(doc_path)
