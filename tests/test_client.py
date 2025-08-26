#!/usr/bin/env python3
"""
Test script for Avathon API client.
Validates authentication and basic API functionality.
"""

import asyncio
import sys
from client import get_avathon_client, close_avathon_client

async def test_client():
    """Test the Avathon client with basic endpoints."""
    print("🧪 Testing Avathon API Client")
    print("=" * 50)
    
    client = None
    try:
        # Get client instance
        client = get_avathon_client()
        print(f"✅ Client initialized: {client.base_url}")
        print(f"✅ API key loaded: {'***' + client.api_key[-4:] if len(client.api_key) > 4 else '***'}")
        
        # Debug: Show exact headers being sent
        print(f"✅ Headers being sent: {dict(client.http.headers)}")
        
        # Test 1: Try health score endpoint (simpler, might be more reliable)
        print("\n🔍 Test 1: GET /api/health_scores (requires asset_id)")
        print("   ℹ️  Skipping - requires asset_id parameter")
        
        # Test 2: Try health alerts endpoint (might work without parameters)
        print("\n🔍 Test 2: GET /api/health_alerts")
        try:
            response = await client.get("/api/health_alerts")
            print(f"   Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ Success! Response type: {type(data)}")
                if isinstance(data, dict):
                    print(f"   📊 Response keys: {list(data.keys())}")
                else:
                    print(f"   📊 Response length: {len(data) if isinstance(data, list) else 'N/A'}")
            elif response.status_code == 401:
                print(f"   ❌ Authentication failed - check AVATHON_API_KEY")
                print(f"   Response: {response.text[:200]}...")
                return False
            elif response.status_code == 404:
                print(f"   ❌ Endpoint not found - check base URL")
                print(f"   Response: {response.text[:200]}...")
                return False
            elif response.status_code == 400:
                print(f"   ⚠️  Bad request (might need parameters)")
                print(f"   Response: {response.text[:200]}...")
            else:
                print(f"   ⚠️  Status: {response.status_code}")
                print(f"   Response: {response.text[:200]}...")
                
        except Exception as e:
            print(f"   ❌ Request failed: {e}")
            return False
        
        # Test 3: Try /api/assets (main data endpoint)
        print("\n🔍 Test 3: GET /api/assets") 
        try:
            response = await client.get("/api/assets")
            print(f"   Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ Success! Response type: {type(data)}")
                if isinstance(data, dict) and 'data' in data:
                    assets = data.get('data', [])
                    print(f"   📊 Found {len(assets)} assets")
                elif isinstance(data, list):
                    print(f"   📊 Found {len(data)} assets")
                else:
                    print(f"   📊 Response keys: {list(data.keys()) if isinstance(data, dict) else 'N/A'}")
            elif response.status_code == 500:
                print(f"   ⚠️  Server error (500) - API might be having issues")
                print(f"   Response: {response.text[:100]}...")
            else:
                print(f"   Status: {response.status_code}")
                print(f"   Response: {response.text[:200]}...")
                
        except Exception as e:
            print(f"   ⚠️  Request failed: {e}")
        
        # Test 4: Test with query parameters (if assets endpoint works)
        print("\n🔍 Test 4: GET /api/assets with params")
        try:
            response = await client.get("/api/assets", params={"limit": 5})
            print(f"   Status: {response.status_code}")
            
            if response.status_code == 200:
                print(f"   ✅ Query parameters work!")
            elif response.status_code == 500:
                print(f"   ⚠️  Server error (500)")
            else:
                print(f"   Status: {response.status_code}")
                
        except Exception as e:
            print(f"   ⚠️  Request failed: {e}")
        
        print("\n🎉 Client testing complete!")
        return True
        
    except Exception as e:
        print(f"❌ Client initialization failed: {e}")
        return False
    
    finally:
        # Clean up
        await close_avathon_client()

def main():
    """Run the test."""
    try:
        success = asyncio.run(test_client())
        if success:
            print("\n✅ Phase 1 Complete: Authentication client working!")
            sys.exit(0)
        else:
            print("\n❌ Phase 1 Failed: Fix authentication issues")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n⏸️  Test interrupted")
        sys.exit(1)

if __name__ == "__main__":
    main()