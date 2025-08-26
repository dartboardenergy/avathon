#!/usr/bin/env python3
"""
Test script for Tool Discovery Methods.
Tests the enhanced search and schema capabilities.
"""

import sys
from toolset import AvathonToolset

def test_discovery():
    """Test the tool discovery capabilities."""
    print("🧪 Testing Tool Discovery Methods")
    print("=" * 50)
    
    try:
        toolset = AvathonToolset()
        
        # Test 1: Search functionality
        print("🔍 Test 1: Search functionality")
        
        health_tools = toolset.get_tools(search_terms=["health"])
        print(f"   📊 'health' search: {len(health_tools)} tools found")
        for name in list(health_tools.keys())[:3]:
            print(f"      • {name}")
        
        asset_tools = toolset.get_tools(search_terms=["asset"])
        print(f"   📊 'asset' search: {len(asset_tools)} tools found")
        
        # Test 2: Method filtering
        print("\n🔍 Test 2: Method filtering")
        
        get_tools = toolset.get_tools(methods=["GET"])
        print(f"   📊 GET methods: {len(get_tools)} tools")
        
        # Test 3: Tool schema
        print("\n🔍 Test 3: Tool schema inspection")
        
        assets_schema = toolset.get_tool_schema("assets")
        if "error" not in assets_schema:
            print(f"   ✅ Assets schema retrieved")
            print(f"      Method: {assets_schema['method']}")
            print(f"      Path: {assets_schema['path']}")
            print(f"      Parameters: {len(assets_schema['parameters'])}")
            print(f"      Tags: {assets_schema['tags']}")
        else:
            print(f"   ❌ Assets schema error: {assets_schema['error']}")
        
        # Test 4: Category filtering (if we have tags)
        print("\n🔍 Test 4: Category filtering")
        
        general_tools = toolset.get_tools(categories=["General"])
        predict_tools = toolset.get_tools(categories=["Predict"])
        
        print(f"   📊 'General' category: {len(general_tools)} tools")
        print(f"   📊 'Predict' category: {len(predict_tools)} tools")
        
        # Test 5: Complex search combinations
        print("\n🔍 Test 5: Complex search combinations")
        
        complex_search = toolset.get_tools(
            search_terms=["health"], 
            methods=["GET"],
            limit=5
        )
        print(f"   📊 Health + GET + limit 5: {len(complex_search)} tools")
        
        print("\n✅ Discovery methods working!")
        return True
        
    except Exception as e:
        print(f"❌ Discovery testing failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run the discovery tests."""
    try:
        success = test_discovery()
        if success:
            print("\n✅ Tool Discovery Complete!")
            sys.exit(0)
        else:
            print("\n❌ Tool Discovery Failed")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n⏸️  Test interrupted")
        sys.exit(1)

if __name__ == "__main__":
    main()