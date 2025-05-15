import os
import re
import zipfile

import pandas as pd
from lxml import etree

from aymurai.meta.xml_document import XMLParagraphWithParagraphPrediction
from aymurai.text.anonymization.alignment import gen_alignment_table


def unzip_document(doc_path: str, output_dir: str) -> None:
    """
    Unzips the document file to the specified output directory.

    Args:
        doc_path (str): The path to the document file.
        output_dir (str): The directory where the contents of the document
            file will be extracted.
    """
    # Ensure the output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # Open the doc file as a zip file
    with zipfile.ZipFile(doc_path, "r") as doc_zip:
        # Extract all the contents to the output directory
        doc_zip.extractall(output_dir)
        # logger.info(f"unzipped {doc_path} to {output_dir}")


def normalize_document(xml_content: str) -> str:
    """
    Normalizes the XML document by removing extra spaces, preserving line breaks,
    and removing hyperlinks while preserving text content.

    Args:
        xml_content (str): The XML content to be normalized.

    Returns:
        str: The normalized XML content.
    """
    # Parse the XML content
    parser = etree.XMLParser(ns_clean=True)
    root = etree.fromstring(xml_content.encode("utf-8"), parser)

    # Extract namespaces
    namespaces = {k: v for k, v in root.nsmap.items() if k}

    # Remove hyperlinks but preserve the text content
    for hyperlink in root.xpath("//w:hyperlink", namespaces=namespaces):
        parent = hyperlink.getparent()
        index = list(parent).index(hyperlink)

        # Move all text-containing children (e.g., w:r elements) outside the hyperlink tag
        for child in hyperlink:
            parent.insert(index, child)
            index += 1
        parent.remove(hyperlink)  # Remove the <w:hyperlink> element itself

    # Process each paragraph
    for wp in root.xpath("//w:p", namespaces=namespaces):
        first = True

        # Find all w:r elements containing w:t elements
        for wr in wp.xpath(".//w:r", namespaces=namespaces):
            wt = wr.find(".//w:t", namespaces)
            if wt is not None and wt.text:
                # Normalize spaces within the text, preserving new line breaks
                wt.text = re.sub(r"[^\S\r\n]+", " ", wt.text)

                # Add a leading space if not the first fragment in the paragraph
                if not first:
                    wt.text = " " + wt.text.lstrip()
                else:
                    wt.text = wt.text.lstrip()
                    first = False

                # Remove trailing spaces from all fragments
                wt.text = wt.text.rstrip()

                # Set the xml:space attribute to preserve
                wt.set(
                    "{http://www.w3.org/XML/1998/namespace}space",
                    "preserve",
                )

                # Check if the text is empty after normalization
                if not wt.text or wt.text.strip() == "":
                    # Remove the w:r element from its parent
                    wr.getparent().remove(wr)

    # Write back the XML content to a string
    xml_str = etree.tostring(root, encoding="unicode", pretty_print=True)

    return xml_str


def replace_text_in_xml(
    paragraphs: list[XMLParagraphWithParagraphPrediction], base_dir: str
) -> None:
    tokens = pd.concat(
        [gen_alignment_table(paragraph) for paragraph in paragraphs],
        ignore_index=True,
    )

    fragments = (
        tokens.groupby(["xml_file", "paragraph_index", "fragment_index"])
        .agg({"target": " ".join, "start_char": "min", "end_char": "max"})
        .reset_index()
    )

    for xml_file, group in fragments.groupby("xml_file"):
        group = group.sort_values("end_char", ascending=False)

        with open(f"{base_dir}/word/{xml_file}", "r+") as file:
            content = file.read()

            for _, r in group.iterrows():
                start_char = r["start_char"]
                end_char = r["end_char"]

                target = r["target"]
                target = re.sub(r"[^\S\r\n]+", " ", target)

                content = content[:start_char] + target + content[end_char:]

            # MUST be at the end to dont screw up the indexes
            content = normalize_document(content)

            file.seek(0)
            file.write(content)
            file.truncate()


def add_files_to_zip(zip_file: zipfile.ZipFile, directory: str) -> None:
    """
    Adds all files in the specified directory to a zip file.

    Args:
        zip_file (zipfile.ZipFile): The zip file to add the files to.
        directory (str): The directory containing the files to be added.
    """
    for root, _, files in os.walk(directory):
        for file in files:
            file_path = os.path.join(root, file)
            zip_file.write(file_path, os.path.relpath(file_path, directory))


def create_docx(xml_directory, output_file) -> None:
    """
    Creates a new DOCX file by adding XML components from the specified directory.

    Args:
        xml_directory (str): The directory containing the XML components.
        output_file (str): The path to the output DOCX file.
    """
    # Create a new zip file
    with zipfile.ZipFile(output_file, "w") as docx:
        # Add XML components
        add_files_to_zip(docx, xml_directory)
