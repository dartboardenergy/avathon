#!/usr/bin/env python3
"""
Debug script to analyze Avathon authentication flow
"""

import asyncio
import httpx
from bs4 import BeautifulSoup
import json

async def analyze_auth_flow():
    """Analyze the actual authentication flow"""
    
    async with httpx.AsyncClient(
        timeout=30.0,
        follow_redirects=True,
        headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
    ) as client:
        
        print("=== Step 1: Analyze initial page ===")
        response = await client.get("https://renewables.apm.avathon.com")
        print(f"Status: {response.status_code}")
        print(f"URL: {response.url}")
        print(f"Headers: {dict(response.headers)}")
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Look for login forms
        forms = soup.find_all('form')
        print(f"\nFound {len(forms)} forms:")
        for i, form in enumerate(forms):
            print(f"Form {i+1}:")
            print(f"  Action: {form.get('action')}")
            print(f"  Method: {form.get('method')}")
            inputs = form.find_all('input')
            for input_field in inputs:
                print(f"    Input: {input_field.get('name')} ({input_field.get('type')})")
        
        # Look for JavaScript that might handle auth
        scripts = soup.find_all('script')
        print(f"\nFound {len(scripts)} script tags")
        
        # Look for any mention of auth endpoints
        page_text = response.text
        if '/auth' in page_text:
            print("✅ Found /auth mentioned in page")
        if 'login' in page_text.lower():
            print("✅ Found 'login' mentioned in page")
        if 'api' in page_text.lower():
            print("✅ Found 'api' mentioned in page")
        
        print("\n=== Step 2: Try alternative auth endpoints ===")
        
        # Try common auth endpoints
        auth_endpoints = [
            "/login",
            "/api/auth",
            "/api/login", 
            "/auth/login",
            "/user/login"
        ]
        
        for endpoint in auth_endpoints:
            try:
                url = f"https://renewables.apm.avathon.com{endpoint}"
                test_response = await client.get(url)
                print(f"{endpoint}: {test_response.status_code} - {test_response.url}")
            except Exception as e:
                print(f"{endpoint}: Error - {e}")
        
        print("\n=== Step 3: Check if it's a SPA (Single Page App) ===")
        # Look for bundle files that might contain routing info
        bundle_scripts = [tag for tag in soup.find_all('script') if tag.get('src') and 'bundle' in tag.get('src')]
        print(f"Found {len(bundle_scripts)} bundle scripts - likely a React/Vue SPA")
        
        for script in bundle_scripts:
            print(f"  Bundle: {script.get('src')}")

if __name__ == "__main__":
    asyncio.run(analyze_auth_flow())