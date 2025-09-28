#!/usr/bin/env python3
"""
Test script for JSON to langextract conversion
"""

import json
import sys
from pathlib import Path

# Add langextract to path
sys.path.append('/Users/sofi/Desktop/CollectiveAI/langextract')

from improved_converter import JSONToLangextractConverter


def test_basic_conversion():
    """Test basic JSON to langextract conversion."""
    print("Testing basic conversion...")
    
    converter = JSONToLangextractConverter()
    
    # Test data
    json_data = {
        "extractions": [
            {"NOMBRE": "Rodríguez, Ana Carolina"},
            {"NOMBRE": "Fernández, Diego Esteban"},
            {"FECHA": "11 de noviembre de 2023"}
        ]
    }
    
    source_text = """
    El documento presenta información sobre Rodríguez, Ana Carolina y Fernández, Diego Esteban.
    La fecha de emisión es 11 de noviembre de 2023.
    """
    
    # Convert
    result = converter.convert(json_data, source_text, "test_doc")
    
    # Verify results
    assert result.document_id == "test_doc"
    assert len(result.extractions) == 3
    assert result.text == source_text
    
    # Check alignment
    aligned_count = sum(1 for ext in result.extractions if ext.alignment_status is not None)
    print(f"Successfully aligned {aligned_count}/{len(result.extractions)} extractions")
    
    # Print details
    for i, ext in enumerate(result.extractions):
        print(f"  {i+1}. {ext.extraction_class}: '{ext.extraction_text}'")
        if ext.char_interval:
            start = ext.char_interval.start_pos
            end = ext.char_interval.end_pos
            actual_text = source_text[start:end]
            print(f"     Position: {start}-{end}, Text: '{actual_text.strip()}'")
        print(f"     Status: {ext.alignment_status}")
    
    print("✓ Basic conversion test passed!")
    return True


def test_batch_conversion():
    """Test batch conversion."""
    print("\nTesting batch conversion...")
    
    converter = JSONToLangextractConverter()
    
    # Test data
    json_batch = [
        {"extractions": [{"PERSONA": "Juan Pérez"}]},
        {"extractions": [{"FECHA": "2023-01-01"}]},
        {"extractions": [{"LUGAR": "Madrid"}]},
    ]
    
    text_batch = [
        "El nombre es Juan Pérez",
        "La fecha es 2023-01-01",
        "El lugar es Madrid",
    ]
    
    doc_ids = ["doc1", "doc2", "doc3"]
    
    # Convert
    results = converter.convert_batch(json_batch, text_batch, doc_ids)
    
    # Verify results
    assert len(results) == 3
    for i, result in enumerate(results):
        assert result.document_id == doc_ids[i]
        assert len(result.extractions) == 1
        print(f"  {result.document_id}: {result.extractions[0].extraction_class} = '{result.extractions[0].extraction_text}'")
    
    print("✓ Batch conversion test passed!")
    return True


def test_conll_loading():
    """Test CONLL file loading."""
    print("\nTesting CONLL file loading...")
    
    from improved_converter import load_conll_to_json
    
    # Create a test CONLL file
    test_conll = Path("test.conll")
    test_conll.write_text("""Juan B-PERSONA
Pérez I-PERSONA
es O
de O
Madrid B-LUGAR
. O
""")
    
    try:
        json_data = load_conll_to_json(test_conll)
        assert "extractions" in json_data
        assert len(json_data["extractions"]) == 2  # PERSONA and LUGAR
        
        print(f"  Loaded {len(json_data['extractions'])} entities:")
        for ext in json_data["extractions"]:
            print(f"    {list(ext.keys())[0]}: {list(ext.values())[0]}")
        
        print("✓ CONLL loading test passed!")
        return True
    finally:
        # Clean up
        if test_conll.exists():
            test_conll.unlink()


def main():
    """Run all tests."""
    print("=== Testing JSON to langextract Conversion ===\n")
    
    try:
        test_basic_conversion()
        test_batch_conversion()
        test_conll_loading()
        print("\n🎉 All tests passed!")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
