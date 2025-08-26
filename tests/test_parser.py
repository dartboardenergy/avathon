#!/usr/bin/env python3
"""
Test script for Avathon OpenAPI Parser (Phase 2).
Validates that we can successfully parse the OpenAPI spec into Operation objects.
"""

import sys
from utils.spec_parser import OpenAPIExtractor, load_openapi_spec, _build_input_model_from_operation

def test_parser():
    """Test the OpenAPI parser with our Avathon spec."""
    print("🧪 Testing Avathon OpenAPI Parser")
    print("=" * 50)
    
    try:
        # Test 1: Load OpenAPI spec
        print("🔍 Test 1: Loading OpenAPI specification")
        spec_path = "specs/avathon_OAS.json"
        
        try:
            oas = load_openapi_spec(spec_path)
            print(f"   ✅ Loaded spec from {spec_path}")
            print(f"   📊 Title: {oas.get('info', {}).get('title', 'Unknown')}")
            print(f"   📊 Version: {oas.get('info', {}).get('version', 'Unknown')}")
            print(f"   📊 OpenAPI Version: {oas.get('openapi', 'Unknown')}")
        except Exception as e:
            print(f"   ❌ Failed to load spec: {e}")
            return False
        
        # Test 2: Create extractor and parse operations
        print("\n🔍 Test 2: Extracting operations from spec")
        try:
            extractor = OpenAPIExtractor(oas)
            operations = list(extractor.iter_operations())
            
            print(f"   ✅ Extracted {len(operations)} operations")
            
            if len(operations) == 0:
                print("   ❌ No operations found - check spec format")
                return False
                
        except Exception as e:
            print(f"   ❌ Failed to extract operations: {e}")
            return False
        
        # Test 3: Analyze operation details
        print("\n🔍 Test 3: Analyzing operation details")
        
        # Find some key operations we know exist
        key_operations = ['assets', 'healthAlerts', 'healthScores']
        found_operations = {}
        
        for op in operations:
            if op.name in key_operations:
                found_operations[op.name] = op
                
        print(f"   📊 Found key operations: {list(found_operations.keys())}")
        
        # Show details for first few operations
        print(f"\n   📋 Sample operations:")
        for i, op in enumerate(operations[:5]):
            param_count = len(op.parameters)
            has_body = op.request_body_schema is not None
            print(f"      {i+1}. {op.method} {op.path_template} ({op.name})")
            print(f"         Description: {op.description[:50]}...")
            print(f"         Parameters: {param_count}, Body: {has_body}, Tags: {op.tag_path}")
        
        # Test 4: Generate Pydantic models
        print("\n🔍 Test 4: Generating Pydantic input models")
        
        model_tests = []
        for op_name in ['assets', 'healthAlerts']:
            if op_name in found_operations:
                try:
                    op = found_operations[op_name]
                    InputModel = _build_input_model_from_operation(op)
                    model_tests.append((op_name, InputModel, op))
                    print(f"   ✅ Generated model for {op_name}: {InputModel.__name__}")
                    
                    # Show model fields
                    if hasattr(InputModel, 'model_fields'):
                        fields = list(InputModel.model_fields.keys())
                        print(f"      Fields: {fields}")
                    
                except Exception as e:
                    print(f"   ❌ Failed to generate model for {op_name}: {e}")
                    
        if not model_tests:
            print("   ⚠️  No models generated successfully")
            return False
        
        # Test 5: Validate model instantiation
        print("\n🔍 Test 5: Testing model instantiation")
        
        for op_name, InputModel, op in model_tests:
            try:
                # Try creating instance with empty data
                instance = InputModel()
                print(f"   ✅ {op_name} model instantiated successfully")
                print(f"      Model: {instance.model_dump()}")
            except Exception as e:
                print(f"   ⚠️  {op_name} model requires parameters: {e}")
        
        # Test 6: Path parameter analysis
        print("\n🔍 Test 6: Path parameter analysis")
        
        path_param_ops = [op for op in operations if '{' in op.path_template]
        print(f"   📊 Operations with path parameters: {len(path_param_ops)}")
        
        for op in path_param_ops[:3]:  # Show first 3
            path_params = [p for p in op.parameters if p.get('in') == 'path']
            print(f"      {op.method} {op.path_template} ({op.name})")
            print(f"         Path params: {[p.get('name') for p in path_params]}")
        
        print("\n🎉 Parser testing complete!")
        print(f"\n📊 Summary:")
        print(f"   • Total operations: {len(operations)}")
        print(f"   • Operations with path params: {len(path_param_ops)}")
        print(f"   • Models generated: {len(model_tests)}")
        print(f"   • Key operations found: {list(found_operations.keys())}")
        
        return True
        
    except Exception as e:
        print(f"❌ Parser testing failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run the test."""
    try:
        success = test_parser()
        if success:
            print("\n✅ Phase 2 Complete: OpenAPI parser working!")
            sys.exit(0)
        else:
            print("\n❌ Phase 2 Failed: Fix parser issues")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n⏸️  Test interrupted")
        sys.exit(1)

if __name__ == "__main__":
    main()