#!/usr/bin/env python3
"""
Test script for the JSON to langextract-inspired converter
"""

import json
from pathlib import Path
from json_to_lx_converter import JSONToLXConverter, ResultPrinter, DocumentSaver


def test_basic_conversion():
    """Test basic JSON to structured format conversion."""
    print("Testing basic conversion...")
    
    converter = JSONToLXConverter()
    printer = ResultPrinter()
    
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
    printer.print_results(result)
    printer.print_statistics(result)
    
    print("✓ Basic conversion test passed!")
    return True


def test_batch_conversion():
    """Test batch conversion."""
    print("\nTesting batch conversion...")
    
    converter = JSONToLXConverter()
    printer = ResultPrinter()
    
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
    
    converter = JSONToLXConverter()
    printer = ResultPrinter()
    
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
        source_text = "Juan Pérez es de Madrid."
        result = converter.convert_from_conll(test_conll, source_text, "test_conll_doc")
        
        assert len(result.extractions) == 2  # PERSONA and LUGAR
        print(f"  Loaded {len(result.extractions)} entities:")
        for ext in result.extractions:
            print(f"    {ext.extraction_class}: {ext.extraction_text}")
        
        printer.print_statistics(result)
        print("✓ CONLL loading test passed!")
        return True
    finally:
        # Clean up
        if test_conll.exists():
            test_conll.unlink()


def test_save_load():
    """Test saving and loading documents."""
    print("\nTesting save/load functionality...")
    
    converter = JSONToLXConverter()
    saver = DocumentSaver()
    printer = ResultPrinter()
    
    # Create test document
    json_data = {"extractions": [{"TEST": "sample text"}]}
    source_text = "This is sample text for testing."
    result = converter.convert(json_data, source_text, "save_test_doc")
    
    # Save to file
    output_path = Path("test_save.json")
    saver.save_to_json(result, output_path)
    
    try:
        # Load from file
        loaded_doc = saver.load_from_json(output_path)
        
        # Verify loaded document
        assert loaded_doc.document_id == "save_test_doc"
        assert len(loaded_doc.extractions) == 1
        assert loaded_doc.extractions[0].extraction_class == "TEST"
        assert loaded_doc.extractions[0].extraction_text == "sample text"
        
        print("✓ Save/load test passed!")
        return True
    finally:
        # Clean up
        if output_path.exists():
            output_path.unlink()


def test_alignment_accuracy():
    """Test alignment accuracy with various text patterns."""
    print("\nTesting alignment accuracy...")
    
    converter = JSONToLXConverter()
    printer = ResultPrinter()
    
    test_cases = [
        {
            "json": {"extractions": [{"EXACT": "exact match"}]},
            "text": "This is an exact match in the text.",
            "expected_aligned": True
        },
        {
            "json": {"extractions": [{"CASE": "Case Sensitive"}]},
            "text": "This is case sensitive text.",
            "expected_aligned": True
        },
        {
            "json": {"extractions": [{"FUZZY": "fuzzy matching"}]},
            "text": "This is fuzzy match text.",
            "expected_aligned": True
        },
        {
            "json": {"extractions": [{"NOT_FOUND": "not in text"}]},
            "text": "This text doesn't contain the entity.",
            "expected_aligned": False
        }
    ]
    
    for i, test_case in enumerate(test_cases):
        result = converter.convert(test_case["json"], test_case["text"], f"test_{i}")
        extraction = result.extractions[0]
        
        is_aligned = extraction.alignment_status is not None
        expected = test_case["expected_aligned"]
        
        if is_aligned == expected:
            print(f"  ✓ Test case {i+1}: {'PASSED' if is_aligned else 'FAILED as expected'}")
        else:
            print(f"  ✗ Test case {i+1}: Expected {expected}, got {is_aligned}")
            return False
    
    print("✓ Alignment accuracy test passed!")
    return True


def main():
    """Run all tests."""
    print("=== Testing JSON to langextract-inspired Converter ===\n")
    
    tests = [
        test_basic_conversion,
        test_batch_conversion,
        test_conll_loading,
        test_save_load,
        test_alignment_accuracy,
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
            print()
        except Exception as e:
            print(f"  ✗ Test failed with error: {e}")
            print()
    
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed!")
        return True
    else:
        print("❌ Some tests failed")
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
