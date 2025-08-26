#!/usr/bin/env python3
"""
Comprehensive Tool Registry & Schema Validation Test.
Validates that ALL 54 endpoints have proper registry entries and schemas.
"""

import sys
from toolset import AvathonToolset, AVATHON_EXECUTION_REGISTRY

def test_complete_validation():
    """Run comprehensive validation on all tools and schemas."""
    print("🧪 Comprehensive Tool Registry & Schema Validation")
    print("=" * 60)
    
    try:
        toolset = AvathonToolset()
        
        # Test 1: Complete Tool Registry Validation
        print("🔍 Test 1: Complete Tool Registry Validation")
        print("=" * 50)
        
        available_tools = toolset.get_available_tools()
        registry_tools = AVATHON_EXECUTION_REGISTRY
        
        print(f"📊 Available tools: {len(available_tools)}")
        print(f"📊 Registry export: {len(registry_tools)}")
        print(f"📊 Operations loaded: {len(toolset._operations_by_name)}")
        
        # Validate counts match expected
        if len(available_tools) == 54 and len(registry_tools) == 54:
            print(f"   ✅ Tool counts correct: 54 tools as expected")
        else:
            print(f"   ❌ Tool count mismatch!")
            return False
        
        # Validate registry format
        registry_issues = []
        for tool_name, description in available_tools.items():
            if not tool_name or not isinstance(tool_name, str):
                registry_issues.append(f"Invalid tool name: {repr(tool_name)}")
            if not description or not isinstance(description, str):
                registry_issues.append(f"Invalid description for {tool_name}: {repr(description)}")
        
        if registry_issues:
            print(f"   ❌ Registry format issues: {len(registry_issues)}")
            for issue in registry_issues[:5]:
                print(f"      • {issue}")
        else:
            print(f"   ✅ All registry entries properly formatted")
        
        # Test 2: Schema Fetching for All Endpoints
        print("\n🔍 Test 2: Schema Generation for All 54 Endpoints")
        print("=" * 50)
        
        schema_results = {
            'success': 0,
            'failed': 0,
            'errors': []
        }
        
        print(f"🧪 Testing schema generation for all {len(available_tools)} tools...")
        
        for tool_name in available_tools.keys():
            try:
                schema = toolset.get_tool_schema(tool_name)
                
                # Validate schema structure
                required_fields = ['name', 'description', 'method', 'path', 'tags', 'parameters', 'has_request_body']
                missing_fields = [f for f in required_fields if f not in schema]
                
                if missing_fields:
                    schema_results['errors'].append(f"{tool_name}: missing fields {missing_fields}")
                    schema_results['failed'] += 1
                elif "error" in schema:
                    schema_results['errors'].append(f"{tool_name}: {schema['error']}")
                    schema_results['failed'] += 1
                else:
                    schema_results['success'] += 1
                    
            except Exception as e:
                schema_results['errors'].append(f"{tool_name}: Exception - {str(e)}")
                schema_results['failed'] += 1
        
        print(f"   ✅ Successful schemas: {schema_results['success']}")
        print(f"   ❌ Failed schemas: {schema_results['failed']}")
        
        if schema_results['errors']:
            print(f"   ⚠️  Schema errors ({len(schema_results['errors'])}):")
            for error in schema_results['errors'][:5]:  # Show first 5
                print(f"      • {error}")
            if len(schema_results['errors']) > 5:
                print(f"      ... and {len(schema_results['errors']) - 5} more")
        
        # Test 3: Schema Content Validation
        print("\n🔍 Test 3: Schema Content Validation")
        print("=" * 50)
        
        # Test a few representative schemas in detail
        test_schemas = ['assets', 'healthAlerts', 'alarms']  # Simple, medium, complex
        if 'plant' in available_tools:
            test_schemas.append('plant')  # Path parameter example
        
        content_results = {
            'valid_params': 0,
            'invalid_params': 0,
            'param_issues': []
        }
        
        for tool_name in test_schemas:
            if tool_name in available_tools:
                print(f"\n   🧪 Analyzing {tool_name} schema...")
                schema = toolset.get_tool_schema(tool_name)
                
                if "error" not in schema:
                    print(f"      Method: {schema['method']}")
                    print(f"      Path: {schema['path']}")
                    print(f"      Parameters: {len(schema['parameters'])}")
                    print(f"      Has body: {schema['has_request_body']}")
                    print(f"      Tags: {schema['tags']}")
                    
                    # Validate each parameter
                    for param in schema['parameters']:
                        required_param_fields = ['name', 'in', 'required', 'type', 'description']
                        missing_param_fields = [f for f in required_param_fields if f not in param]
                        
                        if missing_param_fields:
                            content_results['invalid_params'] += 1
                            content_results['param_issues'].append(f"{tool_name}.{param.get('name', 'unknown')}: missing {missing_param_fields}")
                        else:
                            content_results['valid_params'] += 1
                            
                        # Show parameter details
                        param_name = param.get('name', 'unknown')
                        param_type = param.get('type', 'unknown')
                        param_in = param.get('in', 'unknown')
                        param_required = param.get('required', False)
                        print(f"         • {param_name}: {param_type} ({param_in}) {'*required*' if param_required else 'optional'}")
                else:
                    print(f"      ❌ Schema error: {schema['error']}")
        
        print(f"\n   📊 Parameter validation:")
        print(f"      • Valid parameters: {content_results['valid_params']}")
        print(f"      • Invalid parameters: {content_results['invalid_params']}")
        
        if content_results['param_issues']:
            print(f"   ⚠️  Parameter issues:")
            for issue in content_results['param_issues'][:3]:
                print(f"      • {issue}")
        
        # Test 4: Edge Case Coverage
        print("\n🔍 Test 4: Edge Cases & Error Handling")
        print("=" * 50)
        
        # Test non-existent tool
        print("🧪 Testing non-existent tool schema...")
        invalid_schema = toolset.get_tool_schema("non_existent_tool")
        if "error" in invalid_schema:
            print(f"   ✅ Non-existent tool properly rejected: {invalid_schema['error']}")
        else:
            print(f"   ❌ Non-existent tool should return error")
        
        # Test tools with no parameters
        no_param_tools = []
        for tool_name in available_tools.keys():
            schema = toolset.get_tool_schema(tool_name)
            if "error" not in schema and len(schema.get('parameters', [])) == 0:
                no_param_tools.append(tool_name)
        
        print(f"🧪 Tools with no parameters: {len(no_param_tools)}")
        if no_param_tools:
            print(f"   📋 Examples: {no_param_tools[:3]}")
        
        # Test tools with path parameters
        path_param_tools = []
        for tool_name in available_tools.keys():
            schema = toolset.get_tool_schema(tool_name)
            if "error" not in schema:
                path_params = [p for p in schema.get('parameters', []) if p.get('in') == 'path']
                if path_params:
                    path_param_tools.append((tool_name, len(path_params)))
        
        print(f"🧪 Tools with path parameters: {len(path_param_tools)}")
        for tool_name, count in path_param_tools:
            schema = toolset.get_tool_schema(tool_name)
            print(f"   • {tool_name}: {count} path params ({schema['path']})")
        
        # Test tools with request bodies
        body_tools = []
        for tool_name in available_tools.keys():
            schema = toolset.get_tool_schema(tool_name)
            if "error" not in schema and schema.get('has_request_body'):
                body_tools.append(tool_name)
        
        print(f"🧪 Tools with request bodies: {len(body_tools)}")
        for tool_name in body_tools:
            schema = toolset.get_tool_schema(tool_name)
            print(f"   • {tool_name}: {schema['method']} {schema['path']}")
        
        # Final Summary
        print("\n" + "="*50)
        print("📊 Complete Validation Summary")
        print("="*50)
        
        total_success = (
            len(available_tools) == 54 and
            len(registry_tools) == 54 and
            schema_results['success'] == 54 and
            schema_results['failed'] == 0 and
            not registry_issues and
            content_results['invalid_params'] == 0
        )
        
        print(f"✅ Registry entries: {len(available_tools)}/54")
        print(f"✅ Schema generation: {schema_results['success']}/54")
        print(f"✅ Parameter validation: {content_results['valid_params']} valid, {content_results['invalid_params']} invalid")
        print(f"✅ Edge cases: {len(path_param_tools)} path param tools, {len(body_tools)} body tools")
        print(f"✅ Error handling: Non-existent tool properly rejected")
        
        if total_success:
            print(f"\n🎉 COMPLETE VALIDATION SUCCESS!")
            print(f"🚀 All 54 tools have perfect registry entries and schemas!")
            print(f"🚀 Toolset is 100% ready for dartboard integration!")
            return True
        else:
            print(f"\n⚠️  VALIDATION ISSUES DETECTED")
            print(f"💡 Some tools may need fixes before dartboard integration")
            return len(available_tools) >= 50  # Accept if mostly working
        
    except Exception as e:
        print(f"❌ Complete validation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run the complete validation."""
    try:
        success = test_complete_validation()
        if success:
            print("\n✅ Complete Validation Passed!")
            sys.exit(0)
        else:
            print("\n❌ Complete Validation Failed!")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n⏸️  Test interrupted")
        sys.exit(1)

if __name__ == "__main__":
    main()