#!/usr/bin/env python3
"""
Avathon API Documentation Scraper

Authenticates with Avathon platform and scrapes comprehensive API documentation
to build a structured specification for PydanticAI integration.
"""

import os
import json
import time
import logging
import asyncio
from typing import Dict, List, Any, Optional, Set
from urllib.parse import urljoin, urlparse
from dataclasses import dataclass, asdict

import httpx
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class APIEndpoint:
    """Represents a discovered API endpoint"""
    name: str
    method: str
    path: str
    description: str
    parameters: List[Dict[str, Any]]
    request_body: Optional[Dict[str, Any]]
    responses: Dict[str, Dict[str, Any]]
    tags: List[str]
    auth_required: bool = True

@dataclass
class APIParameter:
    """Represents an API parameter"""
    name: str
    location: str  # path, query, header, body
    type: str
    required: bool
    description: str
    example: Optional[str] = None

class AvathonScraper:
    """
    Comprehensive Avathon API documentation scraper with authentication.
    
    Handles the full login flow and discovers all available API endpoints.
    """
    
    def __init__(self):
        self.username = os.getenv("AVATHON_USERNAME")
        self.password = os.getenv("AVATHON_PASSWORD")
        
        if not self.username or not self.password:
            raise ValueError("AVATHON_USERNAME and AVATHON_PASSWORD must be set in .env file")
        
        self.client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
        )
        
        self.base_url = "https://renewables.apm.avathon.com"
        self.docs_url = "https://docs.apm.sparkcognition.com"
        self.discovered_endpoints: List[APIEndpoint] = []
        self.visited_urls: Set[str] = set()
        
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
    
    async def authenticate(self) -> bool:
        """
        Perform complete authentication flow with Avathon platform.
        
        Returns:
            bool: True if authentication successful, False otherwise
        """
        logger.info("Starting Avathon authentication flow...")
        
        try:
            # Step 1: Initial request to get login page
            logger.info("Step 1: Accessing initial login page")
            response = await self.client.get(self.base_url)
            response.raise_for_status()
            
            # Step 2: Get auth page (should redirect to /auth)
            logger.info("Step 2: Following redirect to auth page")
            auth_url = urljoin(self.base_url, "/auth")
            response = await self.client.get(auth_url)
            response.raise_for_status()
            
            # Parse the auth page to find login form
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for login form
            login_form = soup.find('form')
            if not login_form:
                logger.error("No login form found on auth page")
                return False
            
            # Extract form action and method
            form_action = login_form.get('action', '/auth/login')
            form_method = login_form.get('method', 'POST').upper()
            
            # Build login URL
            login_url = urljoin(auth_url, form_action)
            
            # Step 3: Submit login credentials
            logger.info(f"Step 3: Submitting credentials to {login_url}")
            
            # Prepare login data
            login_data = {
                'username': self.username,
                'password': self.password
            }
            
            # Look for additional form fields (CSRF tokens, etc.)
            for input_field in login_form.find_all('input'):
                field_type = input_field.get('type', '').lower()
                field_name = input_field.get('name', '')
                field_value = input_field.get('value', '')
                
                if field_type == 'hidden' and field_name and field_value:
                    login_data[field_name] = field_value
                    logger.debug(f"Added hidden field: {field_name}")
            
            # Submit login
            if form_method == 'GET':
                response = await self.client.get(login_url, params=login_data)
            else:
                response = await self.client.post(login_url, data=login_data)
            
            response.raise_for_status()
            
            # Step 4: Verify authentication success
            # Check if we're redirected to a dashboard or if login failed
            if 'login' in response.url.path.lower() or 'auth' in response.url.path.lower():
                # Still on login page - likely failed
                soup = BeautifulSoup(response.text, 'html.parser')
                error_msgs = soup.find_all(['div', 'span', 'p'], class_=lambda x: x and ('error' in x.lower() or 'alert' in x.lower()))
                if error_msgs:
                    logger.error(f"Login failed: {error_msgs[0].get_text().strip()}")
                else:
                    logger.error("Login failed: Still on auth page after credential submission")
                return False
            
            # Step 5: Test access to documentation
            logger.info("Step 4: Testing access to API documentation")
            docs_response = await self.client.get(f"{self.docs_url}/reference/overview-api")
            
            if docs_response.status_code == 200 and 'password' not in docs_response.text.lower():
                logger.info("✅ Authentication successful! Can access API documentation")
                return True
            else:
                logger.error("Authentication may have failed - docs still password protected")
                return False
                
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error during authentication: {e.response.status_code} - {e.response.text}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during authentication: {e}")
            return False
    
    async def discover_documentation_structure(self) -> List[str]:
        """
        Discover the structure of API documentation and return all endpoint URLs.
        
        Returns:
            List[str]: URLs of all discovered endpoint documentation pages
        """
        logger.info("Discovering API documentation structure...")
        
        try:
            # Start with the main API reference page
            main_docs_url = f"{self.docs_url}/reference/overview-api"
            response = await self.client.get(main_docs_url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            endpoint_urls = []
            
            # Strategy 1: Look for navigation links
            nav_links = soup.find_all('a', href=True)
            for link in nav_links:
                href = link['href']
                if '/reference/' in href and href not in self.visited_urls:
                    full_url = urljoin(main_docs_url, href)
                    endpoint_urls.append(full_url)
            
            # Strategy 2: Look for API endpoint patterns in text
            # Look for common REST patterns like GET /api/v1/...
            text_content = soup.get_text()
            import re
            
            # Find potential endpoint patterns
            endpoint_patterns = re.findall(r'(GET|POST|PUT|DELETE|PATCH)\s+(/[^\s]+)', text_content)
            for method, path in endpoint_patterns:
                logger.debug(f"Found potential endpoint: {method} {path}")
            
            # Strategy 3: Look for specific documentation sections
            sections = soup.find_all(['h1', 'h2', 'h3', 'h4'], string=re.compile(r'API|endpoint|reference', re.I))
            for section in sections:
                # Look for links in the same section
                section_parent = section.find_parent()
                if section_parent:
                    section_links = section_parent.find_all('a', href=True)
                    for link in section_links:
                        href = link['href']
                        if '/reference/' in href:
                            full_url = urljoin(main_docs_url, href)
                            if full_url not in endpoint_urls:
                                endpoint_urls.append(full_url)
            
            # Remove duplicates and filter
            endpoint_urls = list(set(endpoint_urls))
            endpoint_urls = [url for url in endpoint_urls if self._is_valid_endpoint_url(url)]
            
            logger.info(f"Discovered {len(endpoint_urls)} potential endpoint documentation pages")
            return endpoint_urls
            
        except Exception as e:
            logger.error(f"Error discovering documentation structure: {e}")
            return []
    
    def _is_valid_endpoint_url(self, url: str) -> bool:
        """Check if URL looks like valid endpoint documentation"""
        if not url.startswith(self.docs_url):
            return False
        
        # Skip non-reference pages
        if '/reference/' not in url:
            return False
        
        # Skip obvious non-endpoint pages
        skip_patterns = ['overview', 'getting-started', 'authentication', 'errors']
        return not any(pattern in url.lower() for pattern in skip_patterns)
    
    async def scrape_endpoint(self, url: str) -> Optional[APIEndpoint]:
        """
        Scrape a single endpoint documentation page.
        
        Args:
            url: URL of the endpoint documentation page
            
        Returns:
            APIEndpoint object if successful, None otherwise
        """
        if url in self.visited_urls:
            return None
        
        self.visited_urls.add(url)
        
        try:
            logger.info(f"Scraping endpoint: {url}")
            response = await self.client.get(url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract endpoint information
            endpoint = self._extract_endpoint_info(soup, url)
            
            if endpoint:
                logger.info(f"✅ Successfully scraped: {endpoint.method} {endpoint.path}")
                return endpoint
            else:
                logger.warning(f"⚠️  Could not extract endpoint info from {url}")
                return None
                
        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            return None
        
        # Add delay to be respectful
        await asyncio.sleep(1)
    
    def _extract_endpoint_info(self, soup: BeautifulSoup, url: str) -> Optional[APIEndpoint]:
        """
        Extract endpoint information from a documentation page.
        
        Args:
            soup: BeautifulSoup object of the page
            url: URL of the page for context
            
        Returns:
            APIEndpoint object if extraction successful
        """
        try:
            # Extract title/name
            title_elem = soup.find('h1') or soup.find('title')
            name = title_elem.get_text().strip() if title_elem else url.split('/')[-1]
            
            # Extract HTTP method and path
            method = "GET"  # Default
            path = ""
            
            # Look for method and path in various formats
            method_path_patterns = [
                # Pattern: "GET /api/v1/resources"
                soup.find(string=lambda text: text and any(m in text.upper() for m in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])),
                # Pattern in code blocks
                soup.find('code', string=lambda text: text and '/' in text),
                # Pattern in headers
                soup.find(['h2', 'h3'], string=lambda text: text and any(m in text.upper() for m in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']))
            ]
            
            for pattern in method_path_patterns:
                if pattern and isinstance(pattern, str):
                    import re
                    match = re.search(r'(GET|POST|PUT|DELETE|PATCH)\s+(/[^\s]+)', pattern.upper())
                    if match:
                        method = match.group(1)
                        path = match.group(2)
                        break
            
            # Extract description
            description = ""
            desc_elem = soup.find('p') or soup.find(['div'], class_=lambda x: x and 'description' in x.lower())
            if desc_elem:
                description = desc_elem.get_text().strip()
            
            # Extract parameters
            parameters = self._extract_parameters(soup)
            
            # Extract request body schema
            request_body = self._extract_request_body(soup)
            
            # Extract response schemas
            responses = self._extract_responses(soup)
            
            # Extract tags/categories
            tags = self._extract_tags(soup, url)
            
            return APIEndpoint(
                name=name,
                method=method,
                path=path,
                description=description,
                parameters=parameters,
                request_body=request_body,
                responses=responses,
                tags=tags,
                auth_required=True
            )
            
        except Exception as e:
            logger.error(f"Error extracting endpoint info: {e}")
            return None
    
    def _extract_parameters(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Extract parameter information from documentation"""
        parameters = []
        
        # Look for parameter tables
        tables = soup.find_all('table')
        for table in tables:
            headers = [th.get_text().strip().lower() for th in table.find_all('th')]
            if any(header in ['parameter', 'name', 'field'] for header in headers):
                rows = table.find_all('tr')[1:]  # Skip header row
                for row in rows:
                    cells = [td.get_text().strip() for td in row.find_all('td')]
                    if cells:
                        param = {
                            'name': cells[0] if len(cells) > 0 else '',
                            'type': cells[1] if len(cells) > 1 else 'string',
                            'required': 'required' in (cells[2] if len(cells) > 2 else '').lower(),
                            'description': cells[3] if len(cells) > 3 else cells[2] if len(cells) > 2 else '',
                            'in': 'query'  # Default, can be refined
                        }
                        parameters.append(param)
        
        return parameters
    
    def _extract_request_body(self, soup: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """Extract request body schema from documentation"""
        # Look for JSON schemas or example request bodies
        code_blocks = soup.find_all(['code', 'pre'])
        for block in code_blocks:
            text = block.get_text()
            if '{' in text and ('"' in text or "'" in text):
                try:
                    # Try to parse as JSON
                    import json
                    return json.loads(text)
                except:
                    continue
        return None
    
    def _extract_responses(self, soup: BeautifulSoup) -> Dict[str, Dict[str, Any]]:
        """Extract response schemas from documentation"""
        responses = {}
        
        # Look for response examples or schemas
        code_blocks = soup.find_all(['code', 'pre'])
        for block in code_blocks:
            text = block.get_text()
            if '{' in text and 'response' in block.get('class', []):
                try:
                    import json
                    responses['200'] = {'schema': json.loads(text)}
                except:
                    responses['200'] = {'description': text}
        
        if not responses:
            responses['200'] = {'description': 'Success'}
        
        return responses
    
    def _extract_tags(self, soup: BeautifulSoup, url: str) -> List[str]:
        """Extract tags/categories for the endpoint"""
        tags = []
        
        # Extract from URL path
        path_parts = url.split('/')
        for part in path_parts:
            if part and part not in ['reference', 'api', 'v1', 'docs']:
                tags.append(part.replace('-', ' ').title())
        
        # Look for category information in the page
        breadcrumbs = soup.find_all(['nav', 'ol'], class_=lambda x: x and 'breadcrumb' in x.lower())
        for breadcrumb in breadcrumbs:
            links = breadcrumb.find_all('a')
            for link in links:
                text = link.get_text().strip()
                if text and text not in tags:
                    tags.append(text)
        
        return tags[:3]  # Limit to 3 tags
    
    async def scrape_all_endpoints(self) -> List[APIEndpoint]:
        """
        Discover and scrape all API endpoints.
        
        Returns:
            List of all discovered APIEndpoint objects
        """
        logger.info("Starting comprehensive endpoint discovery and scraping...")
        
        # First authenticate
        if not await self.authenticate():
            logger.error("Authentication failed - cannot proceed with scraping")
            return []
        
        # Discover all endpoint URLs
        endpoint_urls = await self.discover_documentation_structure()
        
        if not endpoint_urls:
            logger.warning("No endpoint URLs discovered")
            return []
        
        logger.info(f"Found {len(endpoint_urls)} potential endpoint pages to scrape")
        
        # Scrape each endpoint
        endpoints = []
        for url in endpoint_urls:
            endpoint = await self.scrape_endpoint(url)
            if endpoint:
                endpoints.append(endpoint)
        
        logger.info(f"✅ Successfully scraped {len(endpoints)} endpoints")
        return endpoints
    
    def generate_openapi_spec(self, endpoints: List[APIEndpoint]) -> Dict[str, Any]:
        """
        Generate OpenAPI specification from scraped endpoints.
        
        Args:
            endpoints: List of APIEndpoint objects
            
        Returns:
            OpenAPI specification dictionary
        """
        spec = {
            "openapi": "3.0.3",
            "info": {
                "title": "Avathon API",
                "description": "Scraped Avathon API specification for PydanticAI integration",
                "version": "1.0.0"
            },
            "servers": [
                {
                    "url": "https://renewables.apm.avathon.com/api",
                    "description": "Avathon Production API"
                }
            ],
            "security": [
                {
                    "sessionAuth": []
                }
            ],
            "components": {
                "securitySchemes": {
                    "sessionAuth": {
                        "type": "apiKey",
                        "in": "cookie",
                        "name": "sessionid"
                    }
                }
            },
            "paths": {}
        }
        
        # Convert endpoints to OpenAPI paths
        for endpoint in endpoints:
            if not endpoint.path:
                continue
                
            if endpoint.path not in spec["paths"]:
                spec["paths"][endpoint.path] = {}
            
            # Build operation
            operation = {
                "summary": endpoint.name,
                "description": endpoint.description,
                "tags": endpoint.tags,
                "parameters": self._convert_parameters_to_openapi(endpoint.parameters),
                "responses": self._convert_responses_to_openapi(endpoint.responses)
            }
            
            if endpoint.request_body:
                operation["requestBody"] = {
                    "content": {
                        "application/json": {
                            "schema": endpoint.request_body
                        }
                    }
                }
            
            spec["paths"][endpoint.path][endpoint.method.lower()] = operation
        
        return spec
    
    def _convert_parameters_to_openapi(self, parameters: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert internal parameter format to OpenAPI format"""
        openapi_params = []
        for param in parameters:
            openapi_param = {
                "name": param.get("name", ""),
                "in": param.get("in", "query"),
                "required": param.get("required", False),
                "schema": {
                    "type": param.get("type", "string")
                }
            }
            if param.get("description"):
                openapi_param["description"] = param["description"]
            openapi_params.append(openapi_param)
        return openapi_params
    
    def _convert_responses_to_openapi(self, responses: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Convert internal response format to OpenAPI format"""
        openapi_responses = {}
        for code, response in responses.items():
            openapi_response = {
                "description": response.get("description", "Success")
            }
            if "schema" in response:
                openapi_response["content"] = {
                    "application/json": {
                        "schema": response["schema"]
                    }
                }
            openapi_responses[code] = openapi_response
        return openapi_responses

async def main():
    """Main function to run the scraper"""
    logger.info("🚀 Starting Avathon API documentation scraper...")
    
    async with AvathonScraper() as scraper:
        # Scrape all endpoints
        endpoints = await scraper.scrape_all_endpoints()
        
        if not endpoints:
            logger.error("❌ No endpoints were successfully scraped")
            return
        
        # Generate OpenAPI specification
        openapi_spec = scraper.generate_openapi_spec(endpoints)
        
        # Save to file
        output_file = "avathon_api_spec.json"
        with open(output_file, 'w') as f:
            json.dump(openapi_spec, f, indent=2)
        
        # Save raw endpoints for debugging
        raw_endpoints_file = "avathon_endpoints_raw.json"
        with open(raw_endpoints_file, 'w') as f:
            json.dump([asdict(endpoint) for endpoint in endpoints], f, indent=2)
        
        logger.info(f"✅ Scraping complete!")
        logger.info(f"📄 OpenAPI spec saved to: {output_file}")
        logger.info(f"🔍 Raw endpoints saved to: {raw_endpoints_file}")
        logger.info(f"📊 Total endpoints discovered: {len(endpoints)}")
        
        # Summary statistics
        methods = {}
        tags = set()
        for endpoint in endpoints:
            methods[endpoint.method] = methods.get(endpoint.method, 0) + 1
            tags.update(endpoint.tags)
        
        logger.info(f"📋 Methods: {dict(methods)}")
        logger.info(f"🏷️  Categories: {sorted(list(tags))}")

if __name__ == "__main__":
    asyncio.run(main())