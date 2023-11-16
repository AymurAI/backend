import os
import re
import base64
import zipfile

import mammoth
from bs4.element import Tag
from bs4 import BeautifulSoup
from more_itertools import collapse


def parse_rels(xml_rels: str | None) -> dict:
    if not xml_rels:
        return {}
    # Load XML into BeautifulSoup
    soup = BeautifulSoup(xml_rels, "lxml-xml")

    rels = {}
    # Find all relationships
    relationships = soup.find_all("Relationship")

    for rel in relationships:
        rels[rel["Id"]] = rel["Target"]

    return rels


def paragraph_handler(tag: Tag) -> str:
    assert tag.name == "r", "not an `r` tag"

    # Start an empty list to hold all formatted pieces of text in this paragraph
    paragraph_html_pieces = []

    text = tag.find("w:t")
    if text is not None and text.string is not None:
        # check for formatting tags
        if tag.find("w:b") is not None:
            # bold tag -> wrap in <strong>
            text_string = f"<strong>{text.string}</strong>"
        else:
            text_string = text.string

        if tag.find("w:sz") is not None:
            # size tag -> wrap the current string in a <span>
            # assuming w:val size is in half-points, so divide by 2 to get equivalent pt
            # size for HTML
            size_pt = int(tag.find("w:sz")["w:val"]) / 2
            text_string = f'<span style="font-size: {size_pt}pt">{text_string}</span>'

        paragraph_html_pieces.append(text_string)

    # combine all pieces of this paragraph, separated by spaces
    return " ".join(paragraph_html_pieces)


def docx_header_footer_to_html(archive, xml, rels_dict: dict):
    # Load XML into BeautifulSoup
    soup = BeautifulSoup(xml, "lxml-xml")

    # Initialize HTML content
    html = ""

    # Find all paragraph tags
    paragraphs = soup.find_all("w:p")

    for p in paragraphs:
        content = []
        for tag in p.find_all(["w:r", "pic:pic"]):
            if tag.name == "r":
                content.append(paragraph_handler(tag))
            elif tag.name == "pic":
                img_id = tag.find("a:blip")["r:embed"]  # extract r:embed attribute
                image_path = rels_dict.get(img_id)
                image_path = f"word/{image_path}"
                image = archive.read(image_path)
                # print(image)

                encoded_string = base64.b64encode(image).decode()
                b64_string = f"data:image/jpeg;base64,{encoded_string}"
                # b64_string = extract_base64_image_data(image)
                image = f'<img src="{b64_string}" alt="embedded_image"/>'
                content.append(image)
            else:
                continue

        content = "".join(content)
        # add the paragraph contents to our html, wrapped in <p> tags
        html += f"<p>{content}</p>"

    return html


def docx2html(path: str):
    output = {
        "header": [],
        "footer": [],
        "document": None,
    }

    with open(path, "rb") as docx_file:
        output["document"] = mammoth.convert_to_html(docx_file).value

    with zipfile.ZipFile(path, "r") as zipped:
        files = zipped.namelist()

        for block in ["header", "footer"]:
            _files = map(lambda x: re.findall(rf"word/{block}\d+.xml", x), files)
            _files = filter(bool, _files)
            _files = collapse(_files)
            _files = list(_files)
            for file in _files:
                xml = zipped.read(file)

                basename = os.path.basename(file)
                rels_file = f"word/_rels/{basename}.rels"
                xml_rels = zipped.read(rels_file) if rels_file in files else None
                rels_dict = parse_rels(xml_rels)

                content = docx_header_footer_to_html(zipped, xml, rels_dict)
                output[block].append(content)

    return output
