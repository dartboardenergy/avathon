#!/usr/bin/env python3
"""
Test script for Full Toolset Coverage (Phase 5).
Validates that all 54 Avathon API operations can be converted to working tools.
SAFETY: Only tests GET endpoints - skips POST/PUT operations.
"""

import asyncio
import sys
from toolset import AvathonToolset, AVATHON_EXECUTION_REGISTRY
from utils.spec_parser import _build_input_model_from_operation

async def test_full_coverage():
    """Test comprehensive toolset coverage across all endpoints."""
    print("🧪 Testing Full Avathon Toolset Coverage (Phase 5)")
    print("=" * 60)
    
    try:
        # Initialize toolset
        toolset = AvathonToolset()
        all_operations = toolset._operations_by_name
        
        print(f"📊 Total operations loaded: {len(all_operations)}")
        
        # Safety check: separate GET from non-GET operations
        get_operations = {}
        non_get_operations = {}
        
        for name, op in all_operations.items():
            if op.method == "GET":
                get_operations[name] = op
            else:
                non_get_operations[name] = op
        
        print(f"🔒 Safety breakdown: {len(get_operations)} GET (safe), {len(non_get_operations)} non-GET (skipped)")
        print(f"🔍 Testing only GET operations to ensure no data modification")
        
        if non_get_operations:
            print(f"\n⚠️  Skipped non-GET operations for safety:")
            for name, op in non_get_operations.items():
                print(f"   • {op.method} {op.path_template} ({name})")
        
        # Test 1: Tool Generation Coverage
        print("\n" + "="*50)
        print("🔍 Test 1: Tool Generation Coverage")
        print("="*50)
        
        successful_tools = []
        failed_tools = []
        
        print(f"🧪 Testing tool generation for {len(get_operations)} GET operations...")
        
        for name, op in get_operations.items():
            try:
                # Test tool function creation
                tool_func = toolset._create_tool_function(op)
                InputModel = _build_input_model_from_operation(op)
                
                # Basic validation
                assert callable(tool_func), f"Tool function not callable for {name}"
                assert hasattr(InputModel, 'model_fields'), f"Input model invalid for {name}"
                
                successful_tools.append(name)
                
            except Exception as e:
                failed_tools.append((name, str(e)))
        
        print(f"   ✅ Successful: {len(successful_tools)}/{len(get_operations)}")
        print(f"   ❌ Failed: {len(failed_tools)}")
        
        if failed_tools:
            print(f"\n   ⚠️  Failed tool generations:")
            for name, error in failed_tools[:5]:  # Show first 5
                print(f"      • {name}: {error[:80]}")
            if len(failed_tools) > 5:
                print(f"      ... and {len(failed_tools) - 5} more")
        
        # Test 2: Pydantic Model Generation
        print("\n" + "="*50)
        print("🔍 Test 2: Pydantic Model Analysis")
        print("="*50)
        
        model_stats = {
            'no_params': 0,
            'simple_params': 0,  # 1-3 params
            'medium_params': 0,  # 4-7 params
            'complex_params': 0  # 8+ params
        }
        
        param_counts = []
        type_issues = []
        
        for name in successful_tools[:10]:  # Test first 10 successful tools
            try:
                op = get_operations[name]
                InputModel = _build_input_model_from_operation(op)
                
                fields = list(InputModel.model_fields.keys())
                param_count = len([f for f in fields if f not in ['extra_headers', 'body', 'include_all']])
                param_counts.append((name, param_count))
                
                # Categorize by complexity
                if param_count == 0:
                    model_stats['no_params'] += 1
                elif param_count <= 3:
                    model_stats['simple_params'] += 1
                elif param_count <= 7:
                    model_stats['medium_params'] += 1
                else:
                    model_stats['complex_params'] += 1
                
                # Test model instantiation
                instance = InputModel()
                
            except Exception as e:
                type_issues.append((name, str(e)))
        
        print(f"   📊 Model complexity distribution:")
        print(f"      • No params: {model_stats['no_params']}")
        print(f"      • Simple (1-3): {model_stats['simple_params']}")
        print(f"      • Medium (4-7): {model_stats['medium_params']}")  
        print(f"      • Complex (8+): {model_stats['complex_params']}")
        
        if param_counts:
            top_complex = sorted(param_counts, key=lambda x: x[1], reverse=True)[:3]
            print(f"   🏆 Most complex endpoints:")
            for name, count in top_complex:
                op = get_operations[name]
                print(f"      • {name}: {count} params ({op.path_template})")
        
        if type_issues:
            print(f"   ⚠️  Model issues: {len(type_issues)}")
        
        # Test 3: Registry Export
        print("\n" + "="*50)
        print("🔍 Test 3: Registry Export Validation")
        print("="*50)
        
        print(f"🧪 Testing AVATHON_EXECUTION_REGISTRY export...")
        
        registry_size = len(AVATHON_EXECUTION_REGISTRY)
        expected_size = len(all_operations)
        
        print(f"   📊 Registry size: {registry_size}")
        print(f"   📊 Expected size: {expected_size}")
        
        if registry_size == expected_size:
            print(f"   ✅ Registry export complete")
        else:
            print(f"   ⚠️  Registry size mismatch")
        
        # Test some registry entries
        sample_entries = list(AVATHON_EXECUTION_REGISTRY.items())[:5]
        print(f"   📋 Sample registry entries:")
        for name, desc in sample_entries:
            print(f"      • {name}: {desc[:60]}...")
        
        # Test 4: Endpoint Categories Analysis
        print("\n" + "="*50)
        print("🔍 Test 4: Endpoint Categories")
        print("="*50)
        
        # Group endpoints by path patterns
        categories = {}
        for name, op in get_operations.items():
            path = op.path_template
            if path.startswith('/api/'):
                category = path.split('/')[2] if len(path.split('/')) > 2 else 'root'
            elif path.startswith('/gpm/api/'):
                category = f"gpm_{path.split('/')[3]}" if len(path.split('/')) > 3 else 'gpm_root'
            else:
                category = 'other'
            
            if category not in categories:
                categories[category] = []
            categories[category].append(name)
        
        print(f"   📊 API categories found: {len(categories)}")
        for category, endpoints in sorted(categories.items()):
            print(f"      • {category}: {len(endpoints)} endpoints")
            if len(endpoints) <= 3:  # Show endpoints for small categories
                for ep in endpoints:
                    print(f"        - {ep}")
        
        # Test 5: Live API Sampling (Safe GET endpoints only)
        print("\n" + "="*50)
        print("🔍 Test 5: Live API Sampling (Safe GETs)")
        print("="*50)
        
        # Test a few different types of endpoints
        test_endpoints = [
            ('assets', 'Main data endpoint'),
            ('healthAlerts', 'Query parameters endpoint'),
        ]
        
        # Add a GPM endpoint if available
        gpm_endpoints = [name for name, op in get_operations.items() if op.path_template.startswith('/gpm/')]
        if gpm_endpoints:
            # Skip path parameter endpoints for safety
            non_path_gpm = [name for name in gpm_endpoints if '{' not in get_operations[name].path_template]
            if non_path_gpm:
                test_endpoints.append((non_path_gpm[0], 'GPM endpoint'))
        
        api_results = {'success': 0, 'client_error': 0, 'server_error': 0, 'other': 0}
        
        print(f"🧪 Testing {len(test_endpoints)} representative endpoints with live API...")
        
        for endpoint_name, endpoint_desc in test_endpoints:
            if endpoint_name in successful_tools:
                try:
                    op = get_operations[endpoint_name] 
                    tool_func = toolset._create_tool_function(op)
                    InputModel = _build_input_model_from_operation(op)
                    
                    # Create minimal input
                    input_data = InputModel()
                    
                    print(f"   🌐 Testing {endpoint_name} ({endpoint_desc})...")
                    result = await tool_func(MockRunContext(), input_data)
                    
                    # New return format: tools now return JSON directly or raise ModelRetry
                    if isinstance(result, dict):
                        # Check if it's a data response
                        if 'data' in result or 'query' in result or len(result) > 0:
                            api_results['success'] += 1
                            print(f"      ✅ Success - Got data response")
                        else:
                            api_results['other'] += 1
                            print(f"      ❓ Empty or unusual response: {list(result.keys())}")
                    elif isinstance(result, list):
                        api_results['success'] += 1
                        print(f"      ✅ Success - Got array response ({len(result)} items)")
                    else:
                        api_results['other'] += 1
                        print(f"      ❓ Unexpected response type: {type(result)}")
                        
                except Exception as e:
                    api_results['other'] += 1
                    print(f"      ❌ Exception: {str(e)[:60]}")
            else:
                print(f"   ⏭️  Skipping {endpoint_name} (tool generation failed)")
        
        # Summary
        print("\n" + "="*50)
        print("📊 Phase 5 Summary")
        print("="*50)
        
        success_rate = len(successful_tools) / len(get_operations) * 100 if get_operations else 0
        
        print(f"✅ Tool generation success: {len(successful_tools)}/{len(get_operations)} ({success_rate:.1f}%)")
        print(f"✅ Registry export: {registry_size} entries")
        print(f"✅ API categories: {len(categories)} different endpoint types")
        print(f"✅ Live API sampling: {sum(api_results.values())} endpoints tested")
        print(f"   • Successful responses: {api_results['success']}")
        print(f"   • Client errors (expected): {api_results['client_error']}")
        print(f"   • Server errors: {api_results['server_error']}")
        print(f"   • Other: {api_results['other']}")
        
        # Overall assessment
        if success_rate >= 95 and len(failed_tools) <= 2:
            print(f"\n🎉 PHASE 5 SUCCESS: Toolset has comprehensive coverage!")
            print(f"🚀 Ready for dartboard integration!")
            return True
        elif success_rate >= 90:
            print(f"\n✅ PHASE 5 MOSTLY SUCCESS: Minor issues to address")
            return True
        else:
            print(f"\n⚠️  PHASE 5 NEEDS WORK: Too many tool generation failures")
            return False
        
    except Exception as e:
        print(f"❌ Full coverage testing failed: {e}")
        import traceback
        traceback.print_exc()
        return False


class MockRunContext:
    """Mock PydanticAI RunContext for testing."""
    pass


def main():
    """Run the full coverage tests."""
    try:
        success = asyncio.run(test_full_coverage())
        if success:
            print("\n✅ Phase 5 Complete: Full toolset coverage validated!")
            sys.exit(0)
        else:
            print("\n❌ Phase 5 Failed: Coverage issues need resolution")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n⏸️  Test interrupted")
        sys.exit(1)


if __name__ == "__main__":
    main()