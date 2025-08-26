import requests
import json
import re
import html
from urllib.parse import urljoin, urlparse
import argparse
import sys

class ReadMeSchemaExtractor:
    def __init__(self, base_url, cookies=None):
        self.base_url = base_url
        self.session = requests.Session()
        # Set headers to mimic a real browser
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
        
        # Set cookies if provided
        if cookies:
            self.session.headers['Cookie'] = cookies
    
    def fetch_endpoint_html(self, endpoint_path):
        """
        Fetches the HTML content from a ReadMe endpoint page.
        
        Args:
            endpoint_path (str): The endpoint path (e.g., '/reference/gpmalarms')
            
        Returns:
            str: Raw HTML content
        """
        full_url = urljoin(self.base_url, endpoint_path)
        
        try:
            response = self.session.get(full_url, timeout=30)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            print(f"Error fetching {full_url}: {e}")
            return None
    
    def extract_openapi_from_html(self, html_content):
        """
        Extracts OpenAPI specification from ReadMe HTML content.
        
        This function looks for the JSON data in the 'ssr-props' script tag
        that contains the complete API specification.
        
        Args:
            html_content (str): Raw HTML content from ReadMe page
            
        Returns:
            dict or None: Parsed OpenAPI specification
        """
        # First, try to find the script tag with id="ssr-props"
        script_tag_pattern = r'<script id="ssr-props"(.+?)</script>'
        script_tag_match = re.search(script_tag_pattern, html_content, re.DOTALL)
        
        if script_tag_match:
            script_tag_content = script_tag_match.group(1)
            
            # Look for the data-initial-props attribute
            data_props_pattern = r'data-initial-props="(.+?)"'
            props_match = re.search(data_props_pattern, script_tag_content, re.DOTALL)
            
            if props_match:
                json_string = props_match.group(1)
                
                # Unescape HTML entities
                unescaped_json_string = html.unescape(json_string)
                
                try:
                    # Parse the JSON
                    api_data = json.loads(unescaped_json_string)
                    
                    # Navigate to the OpenAPI schema
                    api_schema = api_data.get("document", {}).get("api", {}).get("schema")
                    
                    if api_schema:
                        return api_schema
                    else:
                        print("OpenAPI schema not found in expected location within JSON data.")
                        # Try alternative paths
                        return self._try_alternative_paths(api_data)
                        
                except json.JSONDecodeError as e:
                    print(f"Error parsing JSON: {e}")
                    return None
            else:
                print("Could not find 'data-initial-props' attribute.")
                return None
        else:
            print("Could not find 'ssr-props' script tag.")
            # Try alternative extraction methods
            return self._try_alternative_extraction(html_content)
    
    def _try_alternative_paths(self, api_data):
        """Try alternative paths to find the OpenAPI schema within the JSON data."""
        alternative_paths = [
            ["schema"],
            ["api", "spec"],
            ["document", "spec"],
            ["props", "schema"],
            ["data", "schema"],
        ]
        
        for path in alternative_paths:
            current = api_data
            try:
                for key in path:
                    current = current.get(key, {})
                if current and isinstance(current, dict) and "openapi" in current:
                    print(f"Found OpenAPI schema at path: {' -> '.join(path)}")
                    return current
            except (AttributeError, TypeError):
                continue
        
        return None
    
    def _try_alternative_extraction(self, html_content):
        """Try alternative methods to extract OpenAPI data from HTML."""
        # Look for any script tags containing "openapi"
        script_pattern = r'<script[^>]*>(.*?)</script>'
        scripts = re.findall(script_pattern, html_content, re.DOTALL)
        
        for i, script in enumerate(scripts):
            if 'openapi' in script.lower() and '{' in script:
                try:
                    # Try to find JSON within the script
                    json_pattern = r'(\{.*"openapi".*\})'
                    json_match = re.search(json_pattern, script, re.DOTALL)
                    if json_match:
                        json_str = json_match.group(1)
                        return json.loads(json_str)
                except (json.JSONDecodeError, AttributeError):
                    continue
        
        return None
    
    def discover_endpoints(self, html_content):
        """
        Attempts to discover other endpoint URLs from the HTML content.
        
        Returns:
            list: List of discovered endpoint paths
        """
        endpoints = []
        
        # Look for links that match ReadMe reference patterns
        link_patterns = [
            r'/reference/([a-zA-Z0-9\-_]+)',
            r'href="([^"]*reference/[^"]*)"'
        ]
        
        for pattern in link_patterns:
            matches = re.findall(pattern, html_content)
            for match in matches:
                if match.startswith('/reference/'):
                    endpoints.append(match)
                elif '/reference/' in match:
                    # Extract just the path portion
                    parsed = urlparse(match)
                    endpoints.append(parsed.path)
        
        # Remove duplicates and return
        return list(set(endpoints))
    
    def extract_from_site(self, endpoint_path="/reference"):
        """
        Main method to extract OpenAPI specification from a ReadMe site.
        
        Args:
            endpoint_path (str): Starting endpoint path to try
            
        Returns:
            dict: Complete extraction results
        """
        print(f"Fetching content from: {urljoin(self.base_url, endpoint_path)}")
        
        # Fetch the HTML content
        html_content = self.fetch_endpoint_html(endpoint_path)
        if not html_content:
            return {"success": False, "error": "Failed to fetch HTML content"}
        
        # Extract OpenAPI specification
        openapi_spec = self.extract_openapi_from_html(html_content)
        
        if not openapi_spec:
            return {"success": False, "error": "Could not extract OpenAPI specification"}
        
        # Discover other available endpoints
        discovered_endpoints = self.discover_endpoints(html_content)
        
        return {
            "success": True,
            "openapi_spec": openapi_spec,
            "discovered_endpoints": discovered_endpoints,
            "source_url": urljoin(self.base_url, endpoint_path)
        }

def main():
    parser = argparse.ArgumentParser(description='Extract API schemas from ReadMe.io documentation sites')
    parser.add_argument('url', help='Base URL of the ReadMe documentation site')
    parser.add_argument('--endpoint', default='/reference', help='Specific endpoint path to start with (default: /reference)')
    parser.add_argument('--output', default='extracted_api_spec.json', help='Output filename for the extracted schema (default: extracted_api_spec.json)')
    parser.add_argument('--cookies', help='Cookie string for authentication (copy from browser dev tools)')
    parser.add_argument('--discover-only', action='store_true', help='Only discover endpoints, don\'t extract schema')
    
    args = parser.parse_args()
    
    # Clean up URL
    base_url = args.url.rstrip('/')
    if not base_url.startswith(('http://', 'https://')):
        base_url = f"https://{base_url}"
    
    print(f"Starting extraction from: {base_url}")
    if args.cookies:
        print("Using provided authentication cookies")
    
    # Initialize extractor
    extractor = ReadMeSchemaExtractor(base_url, cookies=args.cookies)
    
    if args.discover_only:
        # Just discover endpoints
        html_content = extractor.fetch_endpoint_html(args.endpoint)
        if html_content:
            endpoints = extractor.discover_endpoints(html_content)
            print(f"Discovered {len(endpoints)} endpoints:")
            for endpoint in sorted(endpoints):
                print(f"  {endpoint}")
        else:
            print("Failed to fetch content for endpoint discovery")
        return
    
    # Extract the full specification
    result = extractor.extract_from_site(args.endpoint)
    
    if result["success"]:
        print("Successfully extracted OpenAPI specification!")
        
        # Save to file
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(result["openapi_spec"], f, indent=2)
        
        print(f"Saved complete OpenAPI spec to: {args.output}")
        
        # Print summary
        spec = result["openapi_spec"]
        print(f"\nExtracted API Summary:")
        print(f"  Title: {spec.get('info', {}).get('title', 'Unknown')}")
        print(f"  Version: {spec.get('info', {}).get('version', 'Unknown')}")
        print(f"  Endpoints: {len(spec.get('paths', {}))}")
        print(f"  Schemas: {len(spec.get('components', {}).get('schemas', {}))}")
        
        if result["discovered_endpoints"]:
            print(f"\nDiscovered {len(result['discovered_endpoints'])} endpoint URLs:")
            for endpoint in sorted(result["discovered_endpoints"])[:10]:  # Show first 10
                print(f"  {endpoint}")
            if len(result["discovered_endpoints"]) > 10:
                print(f"  ... and {len(result['discovered_endpoints']) - 10} more")
    else:
        print(f"Extraction failed: {result['error']}")
        sys.exit(1)

if __name__ == "__main__":
    try:
        # Example usage if run directly
        if len(sys.argv) == 1:
            print("ReadMe.io API Schema Extractor")
            print("=" * 40)
            print("Example usage:")
            print("python readme_extractor.py https://docs.apm.sparkcognition.com")
            print("python readme_extractor.py https://docs.example.com --endpoint /reference/users")
            print("python readme_extractor.py https://docs.example.com --discover-only")
            print("\nWith authentication cookies:")
            print('python readme_extractor.py https://docs.example.com --cookies "session_id=abc123; auth=xyz789"')
            print("\nTo get cookies:")
            print("1. Open the ReadMe site in your browser")
            print("2. Open Developer Tools (F12)")
            print("3. Go to Network tab")
            print("4. Refresh the page")
            print("5. Click on any request")
            print("6. Copy the entire Cookie header value")
            sys.exit(0)
        
        print("DEBUG: Script started successfully")
        main()
    except Exception as e:
        print(f"FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)