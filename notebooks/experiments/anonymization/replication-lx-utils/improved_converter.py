#!/usr/bin/env python3
"""
Improved JSON to langextract converter
Uses langextract's built-in functions more efficiently.
"""

import json
import sys
from pathlib import Path

# Add langextract to path
sys.path.append('/Users/sofi/Desktop/CollectiveAI/langextract')

from langextract.core import data
from langextract.core import format_handler as fh
from langextract import resolver


class JSONToLangextractConverter:
    """Efficient converter from JSON extractions to langextract format."""
    
    def __init__(self):
        """Initialize the converter with optimized settings."""
        self.format_handler = fh.FormatHandler(
            format_type=data.FormatType.JSON,
            use_wrapper=True,
            wrapper_key=data.EXTRACTIONS_KEY,
            use_fences=False,
            attribute_suffix=data.ATTRIBUTE_SUFFIX,
        )
        
        self.resolver = resolver.Resolver(
            format_handler=self.format_handler,
            extraction_index_suffix=None,
        )
    
    def convert(self, json_data, source_text, doc_id=None):
        """
        Convert JSON extractions to langextract AnnotatedDocument.
        
        Args:
            json_data: Dictionary with 'extractions' key
            source_text: Original source text
            doc_id: Optional document ID
        
        Returns:
            AnnotatedDocument with aligned extractions
        """
        # Parse JSON data
        json_string = json.dumps(json_data, ensure_ascii=False)
        extraction_data = self.format_handler.parse_output(json_string)
        
        # Create extractions
        extractions = self.resolver.extract_ordered_extractions(extraction_data)
        
        # Align with source text
        aligned_extractions = list(self.resolver.align(
            extractions=extractions,
            source_text=source_text,
            token_offset=0,
            char_offset=0,
            enable_fuzzy_alignment=True,
            fuzzy_alignment_threshold=0.75,
            accept_match_lesser=True,
        ))
        
        return data.AnnotatedDocument(
            document_id=doc_id or "converted_doc",
            extractions=aligned_extractions,
            text=source_text,
        )
    
    def convert_batch(self, json_batch, source_texts, doc_ids=None):
        """
        Convert multiple JSON extractions in batch.
        
        Args:
            json_batch: List of JSON data dictionaries
            source_texts: List of source texts
            doc_ids: Optional list of document IDs
        
        Returns:
            List of AnnotatedDocuments
        """
        results = []
        for i, (json_data, source_text) in enumerate(zip(json_batch, source_texts)):
            doc_id = doc_ids[i] if doc_ids and i < len(doc_ids) else f"doc_{i}"
            result = self.convert(json_data, source_text, doc_id)
            results.append(result)
        return results


def load_conll_to_json(conll_path):
    """Load CONLL file and convert to JSON format efficiently."""
    entities = []
    current_tokens = []
    current_label = None
    
    with conll_path.open(encoding='utf-8') as handle:
        for raw_line in handle:
            line = raw_line.strip()
            
            # Document boundary
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
            
            # Outside tag
            if tag == 'O':
                if current_label and current_tokens:
                    entities.append({current_label: ' '.join(current_tokens)})
                current_tokens = []
                current_label = None
                continue
            
            # Invalid tag format
            if '-' not in tag:
                continue
            
            prefix, label = tag.split('-', 1)
            
            # Beginning tag
            if prefix == 'B':
                if current_label and current_tokens:
                    entities.append({current_label: ' '.join(current_tokens)})
                current_tokens = [token]
                current_label = label
            # Inside tag
            elif prefix == 'I' and current_label == label:
                current_tokens.append(token)
            # Different label
            else:
                if current_label and current_tokens:
                    entities.append({current_label: ' '.join(current_tokens)})
                current_tokens = []
                current_label = None
    
    # Final entity
    if current_label and current_tokens:
        entities.append({current_label: ' '.join(current_tokens)})
    
    return {'extractions': entities}


def print_conversion_stats(annotated_doc):
    """Print conversion statistics."""
    extractions = annotated_doc.extractions or []
    
    # Count alignment statuses
    status_counts = {}
    for ext in extractions:
        status = ext.alignment_status.value if ext.alignment_status else "None"
        status_counts[status] = status_counts.get(status, 0) + 1
    
    print(f"Document: {annotated_doc.document_id}")
    print(f"Total extractions: {len(extractions)}")
    print(f"Source text length: {len(annotated_doc.text or '')}")
    print(f"Alignment statuses: {status_counts}")
    
    # Show sample extractions
    print("\nSample extractions:")
    for i, ext in enumerate(extractions[:3]):
        print(f"  {i+1}. {ext.extraction_class}: '{ext.extraction_text}'")
        if ext.char_interval:
            print(f"     Position: {ext.char_interval.start_pos}-{ext.char_interval.end_pos}")
        print(f"     Status: {ext.alignment_status}")


def main():
    """Main function with examples."""
    print("=== Improved JSON to langextract Converter ===\n")
    
    # Initialize converter
    converter = JSONToLangextractConverter()
    
    # Example 1: Simple conversion
    print("1. Simple conversion example:")
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
    
    result = converter.convert(sample_json, sample_text, "sample_doc")
    print_conversion_stats(result)
    
    # Example 2: Batch conversion
    print("\n2. Batch conversion example:")
    json_batch = [
        {"extractions": [{"PERSONA": "Juan Pérez"}]},
        {"extractions": [{"FECHA": "2023-01-01"}]},
    ]
    
    text_batch = [
        "El nombre es Juan Pérez",
        "La fecha es 2023-01-01",
    ]
    
    batch_results = converter.convert_batch(json_batch, text_batch, ["doc1", "doc2"])
    for result in batch_results:
        print_conversion_stats(result)
        print()
    
    # Example 3: CONLL file conversion
    print("3. CONLL file conversion:")
    conll_path = Path('/Users/sofi/Desktop/CollectiveAI/projects/data-genero/backend/resources/data/sample/annotations.conll')
    if conll_path.exists():
        json_data = load_conll_to_json(conll_path)
        print(f"Loaded {len(json_data['extractions'])} entities from CONLL")
        
        # You need to provide the actual source text
        source_text = "Your actual source text here..."
        result = converter.convert(json_data, source_text, "conll_doc")
        print_conversion_stats(result)
    else:
        print(f"CONLL file not found: {conll_path}")


if __name__ == "__main__":
    main()
