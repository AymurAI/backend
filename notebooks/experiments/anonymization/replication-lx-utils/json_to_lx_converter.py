#!/usr/bin/env python3
"""
JSON to langextract-inspired converter
Standalone implementation inspired by langextract's approach for converting JSON extractions
to structured format with character positions.
"""

import json
import re
import difflib
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Iterator
from dataclasses import dataclass
from enum import Enum


class AlignmentStatus(Enum):
    """Alignment status for extractions."""
    MATCH_EXACT = "match_exact"
    MATCH_FUZZY = "match_fuzzy"
    MATCH_LESSER = "match_lesser"
    MATCH_GREATER = "match_greater"


@dataclass
class CharInterval:
    """Character interval in source text."""
    start_pos: Optional[int] = None
    end_pos: Optional[int] = None


@dataclass
class TokenInterval:
    """Token interval in tokenized text."""
    start_index: Optional[int] = None
    end_index: Optional[int] = None


@dataclass
class Extraction:
    """Extraction with character positions."""
    extraction_class: str
    extraction_text: str
    char_interval: Optional[CharInterval] = None
    alignment_status: Optional[AlignmentStatus] = None
    extraction_index: Optional[int] = None
    group_index: Optional[int] = None
    attributes: Optional[Dict[str, Any]] = None
    token_interval: Optional[TokenInterval] = None


@dataclass
class AnnotatedDocument:
    """Annotated document with extractions."""
    document_id: str
    extractions: List[Extraction]
    text: str


class TextTokenizer:
    """Text tokenizer inspired by langextract's tokenizer."""
    
    @staticmethod
    def tokenize(text: str) -> List[str]:
        """Tokenize text into words using regex."""
        # Simple word tokenization - inspired by langextract's approach
        return re.findall(r'\b\w+\b', text.lower())
    
    @staticmethod
    def find_char_positions(text: str, token: str, start_pos: int = 0) -> List[Tuple[int, int]]:
        """Find all character positions of a token in text."""
        positions = []
        text_lower = text.lower()
        token_lower = token.lower()
        
        pos = start_pos
        while True:
            pos = text_lower.find(token_lower, pos)
            if pos == -1:
                break
            positions.append((pos, pos + len(token)))
            pos += 1
        
        return positions


class TextAligner:
    """Text aligner inspired by langextract's WordAligner."""
    
    def __init__(self):
        self.tokenizer = TextTokenizer()
        self.matcher = difflib.SequenceMatcher(autojunk=False)
    
    def align_extractions(self, extractions: List[Extraction], source_text: str) -> List[Extraction]:
        """Align extractions with source text using difflib approach."""
        source_tokens = self.tokenizer.tokenize(source_text)
        
        for i, extraction in enumerate(extractions):
            extraction.extraction_index = i + 1
            extraction.group_index = 0
            
            # Try exact matching first
            char_interval = self._find_exact_match(extraction.extraction_text, source_text)
            
            if char_interval:
                extraction.char_interval = char_interval
                extraction.alignment_status = AlignmentStatus.MATCH_EXACT
            else:
                # Try fuzzy matching
                char_interval = self._fuzzy_match(extraction.extraction_text, source_text, source_tokens)
                
                if char_interval:
                    extraction.char_interval = char_interval
                    extraction.alignment_status = AlignmentStatus.MATCH_FUZZY
                else:
                    extraction.alignment_status = None
        
        return extractions
    
    def _find_exact_match(self, text: str, source: str) -> Optional[CharInterval]:
        """Find exact text match in source."""
        pos = source.lower().find(text.lower())
        if pos != -1:
            return CharInterval(start_pos=pos, end_pos=pos + len(text))
        return None
    
    def _fuzzy_match(self, text: str, source: str, source_tokens: List[str]) -> Optional[CharInterval]:
        """Find text using fuzzy matching with difflib."""
        text_tokens = self.tokenizer.tokenize(text)
        
        if not text_tokens:
            return None
        
        # Use difflib to find best match
        self.matcher.set_seqs(source_tokens, text_tokens)
        matches = self.matcher.get_matching_blocks()
        
        if not matches or matches[0].size == 0:
            return None
        
        # Find the best match
        best_match = max(matches[:-1], key=lambda x: x.size)
        
        if best_match.size >= len(text_tokens) * 0.5:  # Lower threshold for better matching
            # Convert token positions to character positions
            start_token_idx = best_match.a
            end_token_idx = best_match.a + best_match.size
            
            char_start = self._token_to_char_position(source, source_tokens, start_token_idx)
            char_end = self._token_to_char_position(source, source_tokens, end_token_idx - 1) + len(source_tokens[end_token_idx - 1])
            
            return CharInterval(start_pos=char_start, end_pos=char_end)
        
        return None
    
    def _token_to_char_position(self, source: str, tokens: List[str], token_idx: int) -> int:
        """Convert token index to character position."""
        if token_idx >= len(tokens):
            return len(source)
        
        # Find the token in the source text
        token = tokens[token_idx]
        pos = 0
        
        for i in range(token_idx + 1):
            pos = source.lower().find(tokens[i], pos)
            if pos == -1:
                return 0
        
        return pos


class JSONParser:
    """JSON parser inspired by langextract's format handler."""
    
    @staticmethod
    def parse_extractions(json_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse JSON data to extract entities."""
        if "extractions" not in json_data:
            raise ValueError("JSON data must contain 'extractions' key")
        
        if not isinstance(json_data["extractions"], list):
            raise ValueError("'extractions' must be a list")
        
        return json_data["extractions"]
    
    @staticmethod
    def create_extractions(extraction_data: List[Dict[str, Any]]) -> List[Extraction]:
        """Create Extraction objects from parsed data."""
        extractions = []
        
        for i, extraction_dict in enumerate(extraction_data):
            for class_name, text in extraction_dict.items():
                extraction = Extraction(
                    extraction_class=class_name,
                    extraction_text=str(text),
                    extraction_index=i + 1,
                    group_index=0
                )
                extractions.append(extraction)
        
        return extractions


class CONLLParser:
    """CONLL file parser inspired by langextract's data loading."""
    
    @staticmethod
    def load_conll_to_json(conll_path: Path) -> Dict[str, Any]:
        """Load CONLL file and convert to JSON format."""
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


class JSONToLXConverter:
    """Main converter class inspired by langextract's architecture."""
    
    def __init__(self):
        self.parser = JSONParser()
        self.aligner = TextAligner()
        self.conll_parser = CONLLParser()
    
    def convert(self, json_data: Dict[str, Any], source_text: str, doc_id: str = "converted_doc") -> AnnotatedDocument:
        """Convert JSON extractions to structured format."""
        # Parse JSON data
        extraction_data = self.parser.parse_extractions(json_data)
        
        # Create extractions
        extractions = self.parser.create_extractions(extraction_data)
        
        # Align with source text
        aligned_extractions = self.aligner.align_extractions(extractions, source_text)
        
        return AnnotatedDocument(
            document_id=doc_id,
            extractions=aligned_extractions,
            text=source_text
        )
    
    def convert_batch(self, json_batch: List[Dict[str, Any]], source_texts: List[str], doc_ids: Optional[List[str]] = None) -> List[AnnotatedDocument]:
        """Convert multiple JSON extractions in batch."""
        results = []
        
        for i, (json_data, source_text) in enumerate(zip(json_batch, source_texts)):
            doc_id = doc_ids[i] if doc_ids and i < len(doc_ids) else f"doc_{i}"
            result = self.convert(json_data, source_text, doc_id)
            results.append(result)
        
        return results
    
    def convert_from_conll(self, conll_path: Path, source_text: str, doc_id: str = "conll_doc") -> AnnotatedDocument:
        """Convert from CONLL file."""
        json_data = self.conll_parser.load_conll_to_json(conll_path)
        return self.convert(json_data, source_text, doc_id)


class ResultPrinter:
    """Result printer inspired by langextract's visualization."""
    
    @staticmethod
    def print_results(annotated_doc: AnnotatedDocument, max_show: int = 5):
        """Print conversion results."""
        print(f"Document ID: {annotated_doc.document_id}")
        print(f"Total extractions: {len(annotated_doc.extractions)}")
        print(f"Source text length: {len(annotated_doc.text)}")
        
        # Count alignment statuses
        status_counts = {}
        for ext in annotated_doc.extractions:
            status = ext.alignment_status.value if ext.alignment_status else "None"
            status_counts[status] = status_counts.get(status, 0) + 1
        
        print(f"Alignment statuses: {status_counts}")
        print(f"\nFirst {max_show} extractions:")
        print("-" * 60)
        
        for i, extraction in enumerate(annotated_doc.extractions[:max_show]):
            print(f"{i+1}. {extraction.extraction_class}: '{extraction.extraction_text}'")
            if extraction.char_interval:
                start = extraction.char_interval.start_pos
                end = extraction.char_interval.end_pos
                print(f"   Position: {start}-{end}")
                if annotated_doc.text:
                    actual_text = annotated_doc.text[start:end]
                    print(f"   Matched: '{actual_text}'")
            print(f"   Status: {extraction.alignment_status}")
            print()
    
    @staticmethod
    def print_statistics(annotated_doc: AnnotatedDocument):
        """Print conversion statistics."""
        total = len(annotated_doc.extractions)
        aligned = sum(1 for ext in annotated_doc.extractions if ext.alignment_status is not None)
        not_aligned = total - aligned
        
        print(f"Conversion Statistics:")
        print(f"- Total extractions: {total}")
        print(f"- Successfully aligned: {aligned}")
        print(f"- Not aligned: {not_aligned}")
        print(f"- Alignment rate: {(aligned/total*100):.1f}%" if total > 0 else "N/A")


class DocumentSaver:
    """Document saver inspired by langextract's data handling."""
    
    @staticmethod
    def save_to_json(annotated_doc: AnnotatedDocument, output_path: Path):
        """Save AnnotatedDocument to JSON file."""
        doc_dict = {
            "document_id": annotated_doc.document_id,
            "text": annotated_doc.text,
            "extractions": []
        }
        
        for extraction in annotated_doc.extractions:
            extraction_dict = {
                "extraction_class": extraction.extraction_class,
                "extraction_text": extraction.extraction_text,
                "extraction_index": extraction.extraction_index,
                "group_index": extraction.group_index,
                "alignment_status": extraction.alignment_status.value if extraction.alignment_status else None,
                "attributes": extraction.attributes,
                "char_interval": {
                    "start_pos": extraction.char_interval.start_pos if extraction.char_interval else None,
                    "end_pos": extraction.char_interval.end_pos if extraction.char_interval else None,
                } if extraction.char_interval else None,
            }
            doc_dict["extractions"].append(extraction_dict)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(doc_dict, f, ensure_ascii=False, indent=2)
        
        print(f"Saved annotated document to {output_path}")
    
    @staticmethod
    def load_from_json(input_path: Path) -> AnnotatedDocument:
        """Load AnnotatedDocument from JSON file."""
        with open(input_path, 'r', encoding='utf-8') as f:
            doc_dict = json.load(f)
        
        extractions = []
        for ext_dict in doc_dict.get("extractions", []):
            char_interval = None
            if ext_dict.get("char_interval"):
                char_interval = CharInterval(
                    start_pos=ext_dict["char_interval"]["start_pos"],
                    end_pos=ext_dict["char_interval"]["end_pos"]
                )
            
            alignment_status = None
            if ext_dict.get("alignment_status"):
                alignment_status = AlignmentStatus(ext_dict["alignment_status"])
            
            extraction = Extraction(
                extraction_class=ext_dict["extraction_class"],
                extraction_text=ext_dict["extraction_text"],
                extraction_index=ext_dict.get("extraction_index"),
                group_index=ext_dict.get("group_index"),
                alignment_status=alignment_status,
                attributes=ext_dict.get("attributes"),
                char_interval=char_interval,
            )
            extractions.append(extraction)
        
        return AnnotatedDocument(
            document_id=doc_dict.get("document_id"),
            text=doc_dict.get("text"),
            extractions=extractions
        )


def main():
    """Main function with examples."""
    print("=== JSON to langextract-inspired Converter ===\n")
    
    # Initialize converter
    converter = JSONToLXConverter()
    printer = ResultPrinter()
    saver = DocumentSaver()
    
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
    printer.print_results(result)
    printer.print_statistics(result)
    
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
        printer.print_results(result, max_show=1)
        print()
    
    # Example 3: CONLL file conversion
    print("3. CONLL file conversion:")
    conll_path = Path('/Users/sofi/Desktop/CollectiveAI/projects/data-genero/backend/resources/data/sample/annotations.conll')
    if conll_path.exists():
        result = converter.convert_from_conll(conll_path, "Your actual source text here...", "conll_doc")
        printer.print_results(result, max_show=3)
        printer.print_statistics(result)
        
        # Save results
        output_path = Path("converted_annotations.json")
        saver.save_to_json(result, output_path)
    else:
        print(f"CONLL file not found: {conll_path}")


if __name__ == "__main__":
    main()
