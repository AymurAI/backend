#!/usr/bin/env python3
"""
Simple test for JSON to langextract conversion without full installation
"""

import json
import sys
from pathlib import Path

# Add langextract to path
sys.path.append('/Users/sofi/Desktop/CollectiveAI/langextract')

def test_imports():
    """Test that we can import the necessary modules."""
    print("Testing imports...")
    
    try:
        from langextract.core import data
        print("✓ data module imported")
    except ImportError as e:
        print(f"✗ data module import failed: {e}")
        return False
    
    try:
        from langextract.core import format_handler as fh
        print("✓ format_handler module imported")
    except ImportError as e:
        print(f"✗ format_handler module import failed: {e}")
        return False
    
    try:
        from langextract import resolver
        print("✓ resolver module imported")
    except ImportError as e:
        print(f"✗ resolver module import failed: {e}")
        return False
    
    return True

def test_basic_functionality():
    """Test basic functionality without full conversion."""
    print("\nTesting basic functionality...")
    
    try:
        from langextract.core import data
        from langextract.core import format_handler as fh
        
        # Test data structures
        char_interval = data.CharInterval(start_pos=10, end_pos=20)
        print(f"✓ CharInterval created: {char_interval}")
        
        # Test format handler
        format_handler = fh.FormatHandler(
            format_type=data.FormatType.JSON,
            use_wrapper=True,
            wrapper_key=data.EXTRACTIONS_KEY,
            use_fences=False,
        )
        print(f"✓ FormatHandler created: {format_handler}")
        
        # Test JSON parsing
        json_data = {"extractions": [{"NOMBRE": "Juan Pérez"}]}
        json_string = json.dumps(json_data)
        extraction_data = format_handler.parse_output(json_string)
        print(f"✓ JSON parsed: {extraction_data}")
        
        return True
        
    except Exception as e:
        print(f"✗ Basic functionality test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_conll_parsing():
    """Test CONLL file parsing."""
    print("\nTesting CONLL parsing...")
    
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
        # Parse CONLL file
        entities = []
        current_tokens = []
        current_label = None
        
        with test_conll.open(encoding='utf-8') as handle:
            for raw_line in handle:
                line = raw_line.strip()
                
                if not line:
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
        
        print(f"✓ CONLL parsed: {len(entities)} entities")
        for entity in entities:
            print(f"  {list(entity.keys())[0]}: {list(entity.values())[0]}")
        
        return True
        
    except Exception as e:
        print(f"✗ CONLL parsing test failed: {e}")
        return False
    finally:
        # Clean up
        if test_conll.exists():
            test_conll.unlink()

def main():
    """Run all tests."""
    print("=== Simple JSON to langextract Test ===\n")
    
    tests = [
        test_imports,
        test_basic_functionality,
        test_conll_parsing,
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
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
    sys.exit(0 if success else 1)
