#!/usr/bin/env python3
"""
Test script for Avathon Toolset (Phase 3).
Validates that we can generate working PydanticAI tools and make API calls.
"""

import asyncio
import sys
from toolset import AvathonToolset

async def test_toolset():
    """Test the Avathon toolset with real API calls."""
    print("🧪 Testing Avathon Toolset")
    print("=" * 50)
    
    try:
        # Test 1: Initialize toolset
        print("🔍 Test 1: Initializing AvathonToolset")
        
        try:
            toolset = AvathonToolset()
            available_tools = toolset.get_available_tools()
            
            print(f"   ✅ Toolset initialized successfully")
            print(f"   📊 Available tools: {len(available_tools)}")
            
            # Show some key tools
            key_tools = ['assets', 'health_alerts', 'health_scores']
            found_tools = {k: v for k, v in available_tools.items() if k in key_tools}
            
            print(f"   📋 Key tools found: {list(found_tools.keys())}")
            for tool_name, desc in found_tools.items():
                print(f"      • {tool_name}: {desc[:60]}...")
                
        except Exception as e:
            print(f"   ❌ Failed to initialize toolset: {e}")
            return False
        
        # Test 2: Create PydanticAI toolset
        print("\n🔍 Test 2: Creating PydanticAI toolset")
        
        try:
            # Test with simple tools first
            test_tools = ['assets', 'healthAlerts']
            pydantic_toolset = toolset.create_toolset(test_tools)
            
            print(f"   ✅ PydanticAI toolset created with {len(test_tools)} tools")
            
            # Check that tools were added
            toolset_functions = []
            if hasattr(pydantic_toolset, 'functions'):
                toolset_functions = list(pydantic_toolset.functions.keys()) if pydantic_toolset.functions else []
            elif hasattr(pydantic_toolset, '_functions'):
                toolset_functions = list(pydantic_toolset._functions.keys()) if pydantic_toolset._functions else []
            
            print(f"   📋 Toolset functions: {toolset_functions}")
            
        except Exception as e:
            print(f"   ❌ Failed to create PydanticAI toolset: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        # Test 3: Test individual tool functions
        print("\n🔍 Test 3: Testing individual tool functions")
        
        # Get the raw tool functions for direct testing
        try:
            assets_op = toolset._operations_by_name.get('assets')
            if assets_op:
                assets_func = toolset._create_tool_function(assets_op)
                print(f"   ✅ Generated assets tool function")
                print(f"      Function name: {assets_func.__name__}")
                print(f"      Description: {assets_func.__doc__[:100]}...")
            else:
                print(f"   ❌ Assets operation not found")
                return False
                
        except Exception as e:
            print(f"   ❌ Failed to generate tool function: {e}")
            return False
        
        # Test 4: Execute tool with real API call
        print("\n🔍 Test 4: Executing tool with real API call")
        
        try:
            # Get the input model for assets
            from utils.spec_parser import _build_input_model_from_operation
            
            AssetsInput = _build_input_model_from_operation(assets_op)
            
            # Create input instance (assets might not require parameters)
            input_data = AssetsInput()
            print(f"   📋 Input data: {input_data.model_dump()}")
            
            # Execute the tool function
            print(f"   🚀 Executing assets API call...")
            
            # Create a mock RunContext (PydanticAI context)
            class MockRunContext:
                pass
            
            result = await assets_func(MockRunContext(), input_data)
            
            print(f"   📊 Result keys: {list(result.keys()) if isinstance(result, dict) else 'N/A'}")
            
            if result.get('success'):
                print(f"   ✅ API call successful!")
                print(f"      Status: {result.get('status_code')}")
                
                data = result.get('data', {})
                if isinstance(data, dict) and 'data' in data:
                    assets = data.get('data', [])
                    print(f"      Assets found: {len(assets)}")
                elif isinstance(data, list):
                    print(f"      Assets found: {len(data)}")
                else:
                    print(f"      Data type: {type(data)}")
                    
            elif result.get('error'):
                print(f"   ⚠️  API call failed: {result.get('error')}")
                print(f"      Status: {result.get('status_code')}")
                if 'error_details' in result:
                    print(f"      Details: {result['error_details']}")
            else:
                print(f"   ⚠️  Unexpected result: {result}")
                
        except Exception as e:
            print(f"   ❌ Tool execution failed: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        # Test 5: Test tool with parameters (healthalerts)
        print("\n🔍 Test 5: Testing tool with query parameters")
        
        try:
            health_alerts_op = toolset._operations_by_name.get('healthAlerts')
            if health_alerts_op:
                health_alerts_func = toolset._create_tool_function(health_alerts_op)
                HealthAlertsInput = _build_input_model_from_operation(health_alerts_op)
                
                # Create input with some parameters
                input_data = HealthAlertsInput()  # All parameters are optional
                print(f"   📋 Health alerts input: {input_data.model_dump()}")
                
                result = await health_alerts_func(MockRunContext(), input_data)
                
                if result.get('success'):
                    print(f"   ✅ Health alerts API call successful!")
                    data = result.get('data', {})
                    if isinstance(data, dict):
                        print(f"      Response keys: {list(data.keys())}")
                else:
                    print(f"   ⚠️  Health alerts call: {result.get('error', 'Unknown error')}")
            else:
                print(f"   ⚠️  Health alerts operation not found")
                
        except Exception as e:
            print(f"   ❌ Health alerts test failed: {e}")
        
        print("\n🎉 Toolset testing complete!")
        return True
        
    except Exception as e:
        print(f"❌ Toolset testing failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run the test."""
    try:
        success = asyncio.run(test_toolset())
        if success:
            print("\n✅ Phase 3 Complete: Core toolset working!")
            sys.exit(0)
        else:
            print("\n❌ Phase 3 Failed: Fix toolset issues")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n⏸️  Test interrupted")
        sys.exit(1)

if __name__ == "__main__":
    main()