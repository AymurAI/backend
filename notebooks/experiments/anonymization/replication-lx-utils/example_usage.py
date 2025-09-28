#!/usr/bin/env python3
"""
Example usage of the JSON to langextract-inspired converter
"""

from json_to_lx_converter import JSONToLXConverter, ResultPrinter, DocumentSaver
from pathlib import Path


def example_1_simple_conversion():
    """Example 1: Simple JSON to structured format conversion."""
    print("=== Example 1: Simple Conversion ===\n")
    
    # Initialize converter
    converter = JSONToLXConverter()
    printer = ResultPrinter()
    
    # Your JSON data
    json_data = {
        "extractions": [
            {"NOMBRE": "Rodríguez, Ana Carolina"},
            {"NOMBRE": "Fernández, Diego Esteban"},
            {"FECHA": "11 de noviembre de 2023"},
            {"LUGAR": "Ciudad de Buenos Aires"}
        ]
    }
    
    # Source text
    source_text = """
    El documento presenta información sobre Rodríguez, Ana Carolina y Fernández, Diego Esteban.
    La fecha de emisión es 11 de noviembre de 2023 en la Ciudad de Buenos Aires.
    """
    
    # Convert
    result = converter.convert(json_data, source_text, "example_doc")
    
    # Print results
    printer.print_results(result)
    printer.print_statistics(result)
    
    return result


def example_2_batch_processing():
    """Example 2: Batch processing multiple documents."""
    print("\n=== Example 2: Batch Processing ===\n")
    
    converter = JSONToLXConverter()
    printer = ResultPrinter()
    
    # Multiple JSON documents
    json_batch = [
        {
            "extractions": [
                {"PERSONA": "Juan Pérez"},
                {"EDAD": "35 años"}
            ]
        },
        {
            "extractions": [
                {"FECHA": "2023-01-15"},
                {"HORA": "14:30"}
            ]
        },
        {
            "extractions": [
                {"LUGAR": "Madrid"},
                {"PAIS": "España"}
            ]
        }
    ]
    
    # Corresponding source texts
    text_batch = [
        "El paciente Juan Pérez tiene 35 años.",
        "La cita es el 2023-01-15 a las 14:30.",
        "El evento se realizará en Madrid, España."
    ]
    
    # Document IDs
    doc_ids = ["patient_doc", "appointment_doc", "event_doc"]
    
    # Convert batch
    results = converter.convert_batch(json_batch, text_batch, doc_ids)
    
    # Print results for each document
    for i, result in enumerate(results):
        print(f"Document {i+1}: {result.document_id}")
        printer.print_results(result, max_show=2)
        print()
    
    return results


def example_3_conll_file():
    """Example 3: Loading from CONLL file."""
    print("\n=== Example 3: CONLL File Processing ===\n")
    
    converter = JSONToLXConverter()
    printer = ResultPrinter()
    
    # Check if CONLL file exists
    conll_path = Path('/Users/sofi/Desktop/CollectiveAI/projects/data-genero/backend/resources/data/sample/annotations.conll')
    
    if conll_path.exists():
        print(f"Loading CONLL file: {conll_path}")
        
        # You need to provide the actual source text
        source_text = """
        This is a sample document containing various entities that were extracted.
        The entities include names, dates, and other information that was tagged.
        """
        
        # Convert from CONLL
        result = converter.convert_from_conll(conll_path, source_text, "conll_doc")
        
        # Print results
        printer.print_results(result, max_show=5)
        printer.print_statistics(result)
        
        return result
    else:
        print(f"CONLL file not found: {conll_path}")
        return None


def example_4_save_and_load():
    """Example 4: Saving and loading documents."""
    print("\n=== Example 4: Save and Load ===\n")
    
    converter = JSONToLXConverter()
    saver = DocumentSaver()
    printer = ResultPrinter()
    
    # Create a document
    json_data = {
        "extractions": [
            {"TITULO": "Documento de Prueba"},
            {"AUTOR": "Sistema Automático"},
            {"FECHA": "2023-12-01"}
        ]
    }
    
    source_text = "Este es un Documento de Prueba creado por el Sistema Automático el 2023-12-01."
    
    # Convert
    result = converter.convert(json_data, source_text, "save_example_doc")
    
    # Save to file
    output_path = Path("example_output.json")
    saver.save_to_json(result, output_path)
    
    # Load from file
    loaded_doc = saver.load_from_json(output_path)
    
    print("Original document:")
    printer.print_results(result, max_show=3)
    
    print("\nLoaded document:")
    printer.print_results(loaded_doc, max_show=3)
    
    # Verify they are the same
    assert result.document_id == loaded_doc.document_id
    assert len(result.extractions) == len(loaded_doc.extractions)
    
    print("✓ Save and load successful!")
    
    # Clean up
    if output_path.exists():
        output_path.unlink()
        print(f"Cleaned up {output_path}")
    
    return result


def example_5_custom_alignment():
    """Example 5: Custom alignment scenarios."""
    print("\n=== Example 5: Custom Alignment Scenarios ===\n")
    
    converter = JSONToLXConverter()
    printer = ResultPrinter()
    
    # Test different alignment scenarios
    test_cases = [
        {
            "name": "Exact Match",
            "json": {"extractions": [{"EXACT": "exact match"}]},
            "text": "This is an exact match in the text."
        },
        {
            "name": "Case Insensitive",
            "json": {"extractions": [{"CASE": "Case Sensitive"}]},
            "text": "This is case sensitive text."
        },
        {
            "name": "Fuzzy Match",
            "json": {"extractions": [{"FUZZY": "fuzzy matching"}]},
            "text": "This is fuzzy match text."
        },
        {
            "name": "No Match",
            "json": {"extractions": [{"NOT_FOUND": "not in text"}]},
            "text": "This text doesn't contain the entity."
        }
    ]
    
    for i, test_case in enumerate(test_cases):
        print(f"Test {i+1}: {test_case['name']}")
        result = converter.convert(test_case["json"], test_case["text"], f"test_{i}")
        
        extraction = result.extractions[0]
        print(f"  Entity: {extraction.extraction_class} = '{extraction.extraction_text}'")
        print(f"  Status: {extraction.alignment_status}")
        
        if extraction.char_interval:
            start = extraction.char_interval.start_pos
            end = extraction.char_interval.end_pos
            matched_text = test_case["text"][start:end]
            print(f"  Position: {start}-{end}")
            print(f"  Matched: '{matched_text}'")
        else:
            print("  Position: Not aligned")
        
        print()


def main():
    """Run all examples."""
    print("=== JSON to langextract-inspired Converter Examples ===\n")
    
    try:
        # Run examples
        example_1_simple_conversion()
        example_2_batch_processing()
        example_3_conll_file()
        example_4_save_and_load()
        example_5_custom_alignment()
        
        print("\n🎉 All examples completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Example failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
