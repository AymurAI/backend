#!/usr/bin/env python3
"""
Minimal JSON to langextract converter
Converts JSON extractions to langextract AnnotatedDocument format with character positions.
"""

import json
import sys
from pathlib import Path

# Add langextract to path
sys.path.append('/Users/sofi/Desktop/CollectiveAI/langextract')

from langextract.core import data
from langextract.core import format_handler as fh
from langextract import resolver


def convert_json_to_langextract(json_data, source_text):
    """
    Convert JSON extractions to langextract AnnotatedDocument format.
    
    Args:
        json_data: Dictionary with 'extractions' key containing list of entity dicts
        source_text: The original source text
    
    Returns:
        AnnotatedDocument with aligned extractions
    """
    # Create format handler for JSON parsing
    format_handler = fh.FormatHandler(
        format_type=data.FormatType.JSON,
        use_wrapper=True,
        wrapper_key=data.EXTRACTIONS_KEY,
        use_fences=False,
        attribute_suffix=data.ATTRIBUTE_SUFFIX,
    )
    
    # Create resolver
    resolver_instance = resolver.Resolver(
        format_handler=format_handler,
        extraction_index_suffix=None,
    )
    
    # Convert JSON to string for parsing
    json_string = json.dumps(json_data, ensure_ascii=False)
    
    # Parse the JSON to get extraction data
    extraction_data = format_handler.parse_output(json_string)
    
    # Convert to Extraction objects
    extractions = resolver_instance.extract_ordered_extractions(extraction_data)
    
    # Align extractions with source text to get character positions
    aligned_extractions = list(resolver_instance.align(
        extractions=extractions,
        source_text=source_text,
        token_offset=0,
        char_offset=0,
        enable_fuzzy_alignment=True,
        fuzzy_alignment_threshold=0.75,
        accept_match_lesser=True,
    ))
    
    # Create AnnotatedDocument
    return data.AnnotatedDocument(
        document_id="converted_doc",
        extractions=aligned_extractions,
        text=source_text,
    )


def load_conll_to_json(conll_path):
    """Load CONLL file and convert to JSON format."""
    entities = []
    current_tokens = []
    current_label = None
    
    with conll_path.open(encoding='utf-8') as handle:
        for raw_line in handle:
            line = raw_line.strip()
            
            if not line or raw_line.startswith('-DOCSTART-'):
                if current_label and current_tokens:
                    entities.append({current_label: ' '.join(current_tokens)})
                current_tokens = []
                current_label = None
                continue
            
            parts = raw_line.split()
            if len(parts) < 2:
                continue
                
            token, tag = parts[0], parts[-1]
            
            if tag == 'O':
                if current_label and current_tokens:
                    entities.append({current_label: ' '.join(current_tokens)})
                current_tokens = []
                current_label = None
                continue
            
            if '-' not in tag:
                continue
            
            prefix, label = tag.split('-', 1)
            
            if prefix == 'B':
                if current_label and current_tokens:
                    entities.append({current_label: ' '.join(current_tokens)})
                current_tokens = [token]
                current_label = label
            elif prefix == 'I' and current_label == label:
                current_tokens.append(token)
            else:
                if current_label and current_tokens:
                    entities.append({current_label: ' '.join(current_tokens)})
                current_tokens = []
                current_label = None
    
    if current_label and current_tokens:
        entities.append({current_label: ' '.join(current_tokens)})
    
    return {'extractions': entities}


def print_results(annotated_doc, max_show=5):
    """Print conversion results."""
    print(f"Document ID: {annotated_doc.document_id}")
    print(f"Total extractions: {len(annotated_doc.extractions or [])}")
    print(f"Source text length: {len(annotated_doc.text or '')}")
    print(f"\nFirst {max_show} extractions:")
    print("-" * 60)
    
    for i, extraction in enumerate((annotated_doc.extractions or [])[:max_show]):
        print(f"{i+1}. {extraction.extraction_class}: '{extraction.extraction_text}'")
        if extraction.char_interval:
            start = extraction.char_interval.start_pos
            end = extraction.char_interval.end_pos
            print(f"   Position: {start}-{end}")
            if annotated_doc.text:
                actual_text = annotated_doc.text[start:end]
                print(f"   Matched: '{actual_text}'")
        print(f"   Alignment: {extraction.alignment_status}")
        print()


def main():
    """Main conversion function."""
    # Example usage
    print("=== JSON to langextract Converter ===\n")
    
    # Sample data
    sample_json = {
        "extractions": [
            {"NOMBRE": "Rodríguez, Ana Carolina"},
            {"NOMBRE": "Fernández, Diego Esteban"},
            {"FECHA": "11 de noviembre de 2023"}
        ]
    }
    
    sample_text = """
    El documento presenta información sobre Rodríguez, Ana Carolina y Fernández, Diego Esteban.
    La fecha de emisión es 11 de noviembre de 2023.
    """
    
    print("Converting sample data...")
    annotated_doc = convert_json_to_langextract(sample_json, sample_text)
    print_results(annotated_doc)
    
    # Convert CONLL file if it exists
    conll_path = Path('/Users/sofi/Desktop/CollectiveAI/projects/data-genero/backend/resources/data/sample/annotations.conll')
    if conll_path.exists():
        print("Converting CONLL file...")
        json_data = load_conll_to_json(conll_path)
        print(f"Loaded {len(json_data['extractions'])} entities from CONLL")
        
        # You need to provide the actual source text here
        source_text = "Your actual source text here..."
        annotated_doc = convert_json_to_langextract(json_data, source_text)
        print_results(annotated_doc, max_show=3)
    else:
        print(f"CONLL file not found: {conll_path}")


if __name__ == "__main__":
    main()
