#!/usr/bin/env python3
"""
HTTP-based Avathon API Documentation Scraper

Uses session cookies to directly scrape the API documentation without keeping Selenium running.
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
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import NoSuchElementException
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

class HTTPAvathonScraper:
    """
    HTTP-based scraper that uses session cookies for authentication
    """
    
    def __init__(self):
        self.username = os.getenv("AVATHON_USERNAME")
        self.password = os.getenv("AVATHON_PASSWORD")
        
        if not self.username or not self.password:
            raise ValueError("AVATHON_USERNAME and AVATHON_PASSWORD must be set in .env file")
        
        self.base_url = "https://renewables.apm.avathon.com"
        self.docs_url = "https://docs.apm.sparkcognition.com"
        self.session_cookies = {}
        self.discovered_endpoints = []
        self.visited_urls = set()
        
    def get_session_cookies_with_selenium(self) -> Dict[str, str]:
        """Use Selenium briefly to authenticate and get session cookies"""
        logger.info("🔐 Getting session cookies via Selenium authentication...")
        
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # Run in background
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        
        driver = None
        try:
            driver = webdriver.Chrome(options=chrome_options)
            logger.info("✅ Chrome WebDriver initialized")
            
            # Navigate and authenticate
            driver.get(self.base_url)
            time.sleep(3)
            
            # Find login form
            inputs = driver.find_elements(By.TAG_NAME, "input")
            username_field = None
            password_field = None
            
            for input_elem in inputs:
                input_type = input_elem.get_attribute("type")
                placeholder = input_elem.get_attribute("placeholder") or ""
                
                if input_type == "text" or "email" in placeholder.lower():
                    username_field = input_elem
                elif input_type == "password":
                    password_field = input_elem
            
            if not username_field or not password_field:
                logger.error("❌ Could not find login fields")
                return {}
            
            # Fill credentials
            username_field.clear()
            username_field.send_keys(self.username)
            password_field.clear()
            password_field.send_keys(self.password)
            
            # Find and click continue button
            buttons = driver.find_elements(By.TAG_NAME, "button")
            submit_button = None
            for button in buttons:
                if "continue" in button.text.lower():
                    submit_button = button
                    break
            
            if not submit_button:
                logger.error("❌ Could not find submit button")
                return {}
            
            # Submit and wait
            submit_button.click()
            time.sleep(5)
            
            current_url = driver.current_url
            if "storage" not in current_url:
                logger.error("❌ Authentication may have failed")
                return {}
            
            logger.info("✅ Authentication successful!")
            
            # Get all cookies from both domains
            cookies = {}
            
            # Get cookies from main domain
            main_cookies = driver.get_cookies()
            for cookie in main_cookies:
                cookies[cookie['name']] = cookie['value']
                logger.info(f"Main domain cookie: {cookie['name']}")
            
            # Navigate to docs to trigger cookie sharing
            logger.info("🌐 Navigating to docs to get session cookies...")
            driver.get(f"{self.docs_url}/reference/overview-api")
            time.sleep(3)
            
            # Get docs domain cookies
            docs_cookies = driver.get_cookies()
            for cookie in docs_cookies:
                cookies[cookie['name']] = cookie['value']
                logger.info(f"Docs domain cookie: {cookie['name']}")
            
            logger.info(f"✅ Collected {len(cookies)} total cookies")
            return cookies
            
        except Exception as e:
            logger.error(f"❌ Error getting session cookies: {e}")
            return {}
        finally:
            if driver:
                driver.quit()
                logger.info("🧹 WebDriver cleaned up")
    
    async def scrape_with_http_client(self, cookies: Dict[str, str]) -> List[APIEndpoint]:
        """Use HTTP client with session cookies to scrape documentation"""
        logger.info("📡 Starting HTTP-based documentation scraping...")
        
        # Create HTTP client with cookies
        async with httpx.AsyncClient(
            cookies=cookies,
            timeout=30.0,
            follow_redirects=True,
            headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
        ) as client:
            # Test access to main docs page
            logger.info("🌐 Testing access to API documentation...")
            main_docs_url = f"{self.docs_url}/reference/overview-api"
            
            response = await client.get(main_docs_url)
            logger.info(f"Response status: {response.status_code}")
            logger.info(f"Response URL: {response.url}")
            
            if response.status_code != 200:
                logger.error(f"❌ Failed to access docs: HTTP {response.status_code}")
                return []
            
            if 'password' in response.text.lower():
                logger.error("❌ Documentation is still password protected")
                return []
            
            logger.info("✅ Successfully accessed API documentation!")
            
            # Parse the main page to find all endpoint links
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Save the main page for analysis
            with open("api_docs_main_page.html", "w") as f:
                f.write(response.text)
            logger.info("💾 Main docs page saved to api_docs_main_page.html")
            
            # Find all API reference links
            endpoint_urls = self.discover_endpoint_urls(soup, main_docs_url)
            logger.info(f"📋 Discovered {len(endpoint_urls)} endpoint URLs")
            
            # Scrape each endpoint
            endpoints = []
            for i, url in enumerate(endpoint_urls, 1):
                if url in self.visited_urls:
                    continue
                    
                try:
                    logger.info(f"📄 Scraping endpoint {i}/{len(endpoint_urls)}: {url}")
                    endpoint = await self.scrape_single_endpoint(client, url)
                    if endpoint:
                        endpoints.append(endpoint)
                    
                    # Be respectful - small delay between requests
                    await asyncio.sleep(0.5)
                    
                except Exception as e:
                    logger.error(f"❌ Error scraping {url}: {e}")
                    continue
            
            logger.info(f"✅ Successfully scraped {len(endpoints)} endpoints")
            return endpoints
    
    def discover_endpoint_urls(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Discover all API endpoint URLs from the main documentation page"""
        endpoint_urls = []
        
        # Look for links to API reference pages
        links = soup.find_all('a', href=True)
        
        for link in links:
            href = link['href']
            
            # Filter for API reference links
            if '/reference/' in href:
                # Convert relative URLs to absolute
                if href.startswith('/'):
                    full_url = f"{self.docs_url}{href}"
                elif href.startswith('http'):
                    full_url = href
                else:
                    full_url = urljoin(base_url, href)
                
                if full_url not in endpoint_urls:
                    endpoint_urls.append(full_url)
        
        # Also look for navigation menus or sidebars
        nav_elements = soup.find_all(['nav', 'ul', 'ol'], class_=lambda x: x and any(
            term in x.lower() for term in ['nav', 'menu', 'sidebar', 'toc', 'contents']
        ))
        
        for nav in nav_elements:
            nav_links = nav.find_all('a', href=True)
            for link in nav_links:
                href = link['href']
                if '/reference/' in href:
                    if href.startswith('/'):
                        full_url = f"{self.docs_url}{href}"
                    else:
                        full_url = urljoin(base_url, href)
                    
                    if full_url not in endpoint_urls:
                        endpoint_urls.append(full_url)
        
        # Remove duplicates and filter out non-endpoint pages
        endpoint_urls = [url for url in endpoint_urls if self.is_endpoint_url(url)]
        return endpoint_urls
    
    def is_endpoint_url(self, url: str) -> bool:
        """Check if URL looks like an API endpoint documentation page"""
        if not url.startswith(self.docs_url):
            return False
        
        # Skip overview and general pages
        skip_patterns = ['overview', 'getting-started', 'authentication', 'errors', 'introduction']
        return not any(pattern in url.lower() for pattern in skip_patterns)
    
    async def scrape_single_endpoint(self, client: httpx.AsyncClient, url: str) -> Optional[APIEndpoint]:
        """Scrape a single endpoint documentation page"""
        self.visited_urls.add(url)
        
        try:
            response = await client.get(url)
            
            if response.status_code != 200:
                logger.warning(f"⚠️  HTTP {response.status_code} for {url}")
                return None
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract endpoint information
            endpoint = self.extract_endpoint_info(soup, url)
            
            if endpoint:
                logger.info(f"✅ Extracted: {endpoint.method} {endpoint.path}")
            
            return endpoint
            
        except Exception as e:
            logger.error(f"❌ Error scraping {url}: {e}")
            return None
    
    def extract_endpoint_info(self, soup: BeautifulSoup, url: str) -> Optional[APIEndpoint]:
        """Extract endpoint information from a documentation page"""
        try:
            # Extract title/name
            title_elem = soup.find('h1') or soup.find('title')
            name = title_elem.get_text().strip() if title_elem else url.split('/')[-1]
            
            # Extract HTTP method and path
            method = "GET"  # Default
            path = ""
            
            # Look for method and path in various locations
            # Check for code blocks with HTTP methods
            code_blocks = soup.find_all(['code', 'pre'])
            for block in code_blocks:
                text = block.get_text().upper()
                import re
                method_match = re.search(r'(GET|POST|PUT|DELETE|PATCH)\s+(/[^\s]+)', text)
                if method_match:
                    method = method_match.group(1)
                    path = method_match.group(2)
                    break
            
            # Check headers for method/path info
            headers = soup.find_all(['h1', 'h2', 'h3', 'h4'])
            for header in headers:
                text = header.get_text().upper()
                import re
                method_match = re.search(r'(GET|POST|PUT|DELETE|PATCH)\s+(/[^\s]+)', text)
                if method_match:
                    method = method_match.group(1)
                    path = method_match.group(2)
                    break
            
            # Extract description
            description = ""
            # Look for the first paragraph after h1
            h1 = soup.find('h1')
            if h1:
                next_p = h1.find_next('p')
                if next_p:
                    description = next_p.get_text().strip()
            
            if not description:
                # Fallback to any paragraph
                p = soup.find('p')
                if p:
                    description = p.get_text().strip()
            
            # Extract parameters from tables
            parameters = self.extract_parameters_from_tables(soup)
            
            # Extract request body examples
            request_body = self.extract_request_body(soup)
            
            # Extract response examples
            responses = self.extract_responses(soup)
            
            # Extract tags from URL or content
            tags = self.extract_tags(url, soup)
            
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
            logger.error(f"❌ Error extracting endpoint info: {e}")
            return None
    
    def extract_parameters_from_tables(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Extract parameters from documentation tables"""
        parameters = []
        
        # Look for parameter tables
        tables = soup.find_all('table')
        for table in tables:
            headers = [th.get_text().strip().lower() for th in table.find_all('th')]
            
            # Check if this looks like a parameters table
            param_indicators = ['parameter', 'name', 'field', 'property']
            if any(indicator in ' '.join(headers) for indicator in param_indicators):
                
                rows = table.find_all('tr')[1:]  # Skip header row
                for row in rows:
                    cells = [td.get_text().strip() for td in row.find_all('td')]
                    
                    if len(cells) >= 2:
                        param = {
                            'name': cells[0] if len(cells) > 0 else '',
                            'type': cells[1] if len(cells) > 1 else 'string',
                            'required': 'required' in (cells[2] if len(cells) > 2 else '').lower(),
                            'description': cells[3] if len(cells) > 3 else cells[2] if len(cells) > 2 else '',
                            'in': 'query'  # Default location
                        }
                        parameters.append(param)
        
        return parameters
    
    def extract_request_body(self, soup: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """Extract request body schema from code examples"""
        # Look for JSON examples in code blocks
        code_blocks = soup.find_all(['code', 'pre'])
        
        for block in code_blocks:
            text = block.get_text().strip()
            
            # Check if this looks like JSON
            if text.startswith('{') and text.endswith('}'):
                try:
                    import json
                    return json.loads(text)
                except json.JSONDecodeError:
                    continue
        
        return None
    
    def extract_responses(self, soup: BeautifulSoup) -> Dict[str, Dict[str, Any]]:
        """Extract response examples and schemas"""
        responses = {}
        
        # Look for response sections
        response_headers = soup.find_all(['h2', 'h3', 'h4'], string=lambda text: text and 'response' in text.lower())
        
        for header in response_headers:
            # Look for code blocks after response headers
            next_elem = header.find_next(['code', 'pre'])
            if next_elem:
                text = next_elem.get_text().strip()
                if text.startswith('{'):
                    try:
                        import json
                        response_data = json.loads(text)
                        responses['200'] = {'schema': response_data}
                    except json.JSONDecodeError:
                        responses['200'] = {'description': text}
        
        # Default response if none found
        if not responses:
            responses['200'] = {'description': 'Success'}
        
        return responses
    
    def extract_tags(self, url: str, soup: BeautifulSoup) -> List[str]:
        """Extract tags/categories from URL and content"""
        tags = []
        
        # Extract from URL path
        path_parts = url.split('/')
        for part in path_parts:
            if part and part not in ['reference', 'api', 'v1', 'docs', 'https:', '']:
                clean_part = part.replace('-', ' ').replace('_', ' ').title()
                if clean_part not in tags:
                    tags.append(clean_part)
        
        # Extract from breadcrumbs or navigation
        breadcrumbs = soup.find_all(['nav', 'ol', 'ul'], class_=lambda x: x and 'breadcrumb' in x.lower())
        for breadcrumb in breadcrumbs:
            links = breadcrumb.find_all('a')
            for link in links:
                text = link.get_text().strip()
                if text and text not in tags and len(tags) < 3:
                    tags.append(text)
        
        return tags[:3]  # Limit to 3 tags
    
    def generate_openapi_spec(self, endpoints: List[APIEndpoint]) -> Dict[str, Any]:
        """Generate OpenAPI specification from scraped endpoints"""
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
                    "cookieAuth": []
                }
            ],
            "components": {
                "securitySchemes": {
                    "cookieAuth": {
                        "type": "apiKey",
                        "in": "cookie",
                        "name": "connect.sid"
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
                "parameters": self.convert_parameters_to_openapi(endpoint.parameters),
                "responses": self.convert_responses_to_openapi(endpoint.responses),
                "security": [{"cookieAuth": []}]
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
    
    def convert_parameters_to_openapi(self, parameters: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert parameters to OpenAPI format"""
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
    
    def convert_responses_to_openapi(self, responses: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Convert responses to OpenAPI format"""
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
    """Main function to run the HTTP scraper"""
    logger.info("🚀 Starting HTTP-based Avathon API scraper...")
    
    scraper = HTTPAvathonScraper()
    
    try:
        # Get session cookies via Selenium
        cookies = scraper.get_session_cookies_with_selenium()
        
        if not cookies:
            logger.error("❌ Failed to get session cookies")
            return
        
        logger.info(f"✅ Got {len(cookies)} session cookies")
        
        # Use HTTP client to scrape documentation
        endpoints = await scraper.scrape_with_http_client(cookies)
        
        if not endpoints:
            logger.error("❌ No endpoints were scraped")
            return
        
        # Generate OpenAPI specification
        logger.info("📄 Generating OpenAPI specification...")
        openapi_spec = scraper.generate_openapi_spec(endpoints)
        
        # Save results
        output_file = "avathon_api_spec_final.json"
        with open(output_file, 'w') as f:
            json.dump(openapi_spec, f, indent=2)
        
        # Save raw endpoints
        raw_endpoints_file = "avathon_endpoints_final.json"
        with open(raw_endpoints_file, 'w') as f:
            json.dump([asdict(endpoint) for endpoint in endpoints], f, indent=2)
        
        # Save session data for future use
        session_file = "avathon_session_cookies.json"
        with open(session_file, 'w') as f:
            json.dump(cookies, f, indent=2)
        
        logger.info("🎉 SUCCESS! Scraping completed!")
        logger.info(f"📄 OpenAPI spec saved to: {output_file}")
        logger.info(f"🔍 Raw endpoints saved to: {raw_endpoints_file}")
        logger.info(f"🍪 Session cookies saved to: {session_file}")
        logger.info(f"📊 Total endpoints discovered: {len(endpoints)}")
        
        # Summary statistics
        methods = {}
        tags = set()
        for endpoint in endpoints:
            methods[endpoint.method] = methods.get(endpoint.method, 0) + 1
            tags.update(endpoint.tags)
        
        logger.info(f"📋 HTTP Methods: {dict(methods)}")
        logger.info(f"🏷️  Categories: {sorted(list(tags))}")
        
    except Exception as e:
        logger.error(f"❌ Scraping failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())