#!/usr/bin/env python3
"""
Comprehensive Avathon API Scraper - Implementation
Extracts detailed API specifications from all 75+ endpoints and generates complete OpenAPI specification
"""

import asyncio
import json
import logging
import re
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin
import os

import httpx
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class Parameter:
    name: str
    location: str  # query, path, header, body
    type: str
    required: bool
    description: str
    example: Optional[str] = None

@dataclass
class RequestBody:
    content_type: str
    schema: Dict[str, Any]
    example: Optional[Dict[str, Any]] = None

@dataclass
class Response:
    status_code: str
    description: str
    content_type: str
    schema: Optional[Dict[str, Any]] = None
    example: Optional[Dict[str, Any]] = None

@dataclass
class APIEndpoint:
    name: str
    method: str
    path: str
    description: str
    parameters: List[Parameter]
    request_body: Optional[RequestBody]
    responses: Dict[str, Response]
    tags: List[str]
    source_url: str

class ComprehensiveAvathonScraper:
    def __init__(self):
        self.docs_url = "https://docs.apm.sparkcognition.com"
        
        # Use working authentication from previous sessions
        self.cookies = {
            'connect.sid': 's%3A05L4a8drF65NflPjahqbtCgn1QT3G7Ru.BaApdohf6tO%2FpmLmImgWILalJFdBh5KHYQwAUqG8Imw',
            '__cf_bm': 'vZKhA9UxyWORIhSV3d5.T7cPeAolwgr_6nel5mCXe48-1755893974-1.0.1.1-dUlqeWOgtc4H5pALXgfpz.FZXyxf7qNM7ilir4wm1CsEnz4lnMV38hV1jpMYxC_bTCm0o4Wh_AKuOZZsdgdc_58sNMjrshKFpKPRh7Smaw0',
            'readme_language': 'shell',
            'readme_library': '{"shell":"curl"}'
        }
        
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:142.0) Gecko/20100101 Firefox/142.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': 'https://renewables.apm.avathon.com/',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'cross-site',
            'Priority': 'u=0, i'
        }
        
        self.discovered_endpoints = []
        self.failed_endpoints = []
        
    async def discover_all_endpoint_urls(self) -> List[str]:
        """Stage 1: Discover all endpoint URLs from the reference links"""
        logger.info("🔍 Stage 1: Discovering all endpoint URLs...")
        
        # Load reference links from previous analysis
        try:
            with open("content_analysis.json", "r") as f:
                analysis = json.load(f)
                reference_links = analysis.get("reference_links", [])
        except FileNotFoundError:
            logger.warning("⚠️  content_analysis.json not found, falling back to discovery")
            reference_links = await self._fallback_discovery()
        
        # Convert relative links to absolute URLs
        endpoint_urls = []
        for link in reference_links:
            if link.startswith('/'):
                full_url = f"{self.docs_url}{link}"
            else:
                full_url = link
            
            if self._is_api_endpoint_url(full_url):
                endpoint_urls.append(full_url)
        
        # Remove duplicates and sort
        endpoint_urls = sorted(list(set(endpoint_urls)))
        
        logger.info(f"📋 Discovered {len(endpoint_urls)} endpoint URLs")
        for i, url in enumerate(endpoint_urls[:10], 1):
            logger.info(f"  {i}. {url.split('/')[-1]}")
        if len(endpoint_urls) > 10:
            logger.info(f"  ... and {len(endpoint_urls) - 10} more")
        
        return endpoint_urls
    
    async def _fallback_discovery(self) -> List[str]:
        """Fallback endpoint discovery if content_analysis.json is missing"""
        async with httpx.AsyncClient(
            cookies=self.cookies,
            headers=self.headers,
            timeout=30.0,
            follow_redirects=True
        ) as client:
            response = await client.get(f"{self.docs_url}/reference/overview-api")
            soup = BeautifulSoup(response.text, 'html.parser')
            
            links = []
            for link in soup.find_all('a', href=True):
                href = link['href']
                if '/reference/' in href:
                    links.append(href)
            
            return links
    
    def _is_api_endpoint_url(self, url: str) -> bool:
        """Filter URLs to only include actual API endpoints"""
        if not url.startswith(self.docs_url):
            return False
        
        if '/reference/' not in url:
            return False
        
        # Skip overview and general documentation pages
        skip_patterns = [
            'overview-api',
            'security', 
            'authentication',
            'getting-started',
            'introduction',
            'when-interfacing-with-apis',
            'how-can-i-make-api-calls'
        ]
        
        url_lower = url.lower()
        return not any(pattern in url_lower for pattern in skip_patterns)
    
    async def scrape_all_endpoints(self, endpoint_urls: List[str]) -> List[APIEndpoint]:
        """Stage 2: Scrape detailed specifications from each endpoint"""
        logger.info(f"🔄 Stage 2: Scraping {len(endpoint_urls)} endpoints...")
        
        endpoints = []
        
        async with httpx.AsyncClient(
            cookies=self.cookies,
            headers=self.headers,
            timeout=30.0,
            follow_redirects=True
        ) as client:
            
            for i, url in enumerate(endpoint_urls, 1):
                try:
                    logger.info(f"📄 Scraping {i}/{len(endpoint_urls)}: {url.split('/')[-1]}")
                    
                    endpoint = await self._scrape_single_endpoint(client, url)
                    if endpoint:
                        endpoints.append(endpoint)
                        logger.info(f"  ✅ {endpoint.method} {endpoint.path}")
                    else:
                        self.failed_endpoints.append(url)
                        logger.warning(f"  ❌ Failed to extract endpoint data")
                    
                    # Rate limiting
                    await asyncio.sleep(0.3)
                    
                except Exception as e:
                    logger.error(f"  ❌ Error scraping {url}: {e}")
                    self.failed_endpoints.append(url)
                    continue
        
        logger.info(f"✅ Successfully scraped {len(endpoints)} endpoints")
        logger.info(f"❌ Failed to scrape {len(self.failed_endpoints)} endpoints")
        
        return endpoints
    
    async def _scrape_single_endpoint(self, client: httpx.AsyncClient, url: str) -> Optional[APIEndpoint]:
        """Extract detailed API specification from a single endpoint page"""
        response = await client.get(url)
        
        if response.status_code != 200:
            return None
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract core endpoint information
        name = self._extract_name(soup, url)
        method = self._extract_method(soup)
        path = self._extract_path(soup)
        description = self._extract_description(soup)
        
        # Extract detailed specifications
        parameters = self._extract_parameters(soup)
        request_body = self._extract_request_body(soup)
        responses = self._extract_responses(soup)
        tags = self._extract_tags(url, soup)
        
        return APIEndpoint(
            name=name,
            method=method,
            path=path,
            description=description,
            parameters=parameters,
            request_body=request_body,
            responses=responses,
            tags=tags,
            source_url=url
        )
    
    def _extract_name(self, soup: BeautifulSoup, url: str) -> str:
        """Extract endpoint name from page title or headers"""
        # Try h1 first
        h1 = soup.find('h1')
        if h1:
            name = h1.get_text().strip()
            if name and len(name) < 100:
                return name
        
        # Try title tag
        title = soup.find('title')
        if title:
            name = title.get_text().strip()
            # Clean up common title patterns
            name = re.sub(r'\s*-\s*.*$', '', name)  # Remove " - Documentation" etc
            if name and len(name) < 100:
                return name
        
        # Fallback to URL-based name
        return url.split('/')[-1].replace('-', ' ').title()
    
    def _extract_method(self, soup: BeautifulSoup) -> str:
        """Extract HTTP method from page content"""
        text = soup.get_text()
        
        # Look for explicit method declarations
        methods = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']
        
        # Pattern 1: "GET /api/path"
        for method in methods:
            pattern = rf'\b{method}\s+/'
            if re.search(pattern, text, re.IGNORECASE):
                return method
        
        # Pattern 2: Method in code blocks
        code_blocks = soup.find_all(['code', 'pre'])
        for block in code_blocks:
            block_text = block.get_text()
            for method in methods:
                if f'{method} /' in block_text:
                    return method
        
        # Pattern 3: Method in headers or spans
        for element in soup.find_all(['span', 'div', 'h1', 'h2', 'h3']):
            element_text = element.get_text().strip()
            for method in methods:
                if element_text.upper() == method:
                    return method
        
        # Default to GET
        return 'GET'
    
    def _extract_path(self, soup: BeautifulSoup) -> str:
        """Extract API path from page content"""
        text = soup.get_text()
        
        # Pattern 1: "METHOD /api/path"
        methods = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']
        for method in methods:
            pattern = rf'{method}\s+(/[^\s\n]+)'
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        
        # Pattern 2: Standalone API paths
        api_patterns = [
            r'(/api/v\d+/[^\s\n<>"]+)',  # /api/v1/something
            r'(/api/[^\s\n<>"]+)',       # /api/something
            r'(/v\d+/[^\s\n<>"]+)',      # /v1/something
        ]
        
        for pattern in api_patterns:
            matches = re.findall(pattern, text)
            if matches:
                # Return the most likely path (usually the first one)
                return matches[0]
        
        # Pattern 3: Look in code blocks specifically
        code_blocks = soup.find_all(['code', 'pre'])
        for block in code_blocks:
            block_text = block.get_text()
            for pattern in api_patterns:
                matches = re.findall(pattern, block_text)
                if matches:
                    return matches[0]
        
        return ""
    
    def _extract_description(self, soup: BeautifulSoup) -> str:
        """Extract endpoint description"""
        # Strategy 1: First paragraph after h1
        h1 = soup.find('h1')
        if h1:
            next_elem = h1.find_next(['p', 'div'])
            if next_elem:
                desc = next_elem.get_text().strip()
                if desc and len(desc) > 10:
                    return desc
        
        # Strategy 2: First substantial paragraph
        paragraphs = soup.find_all('p')
        for p in paragraphs:
            text = p.get_text().strip()
            if len(text) > 20 and not text.startswith('http'):
                return text
        
        # Strategy 3: Meta description
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc and meta_desc.get('content'):
            return meta_desc['content']
        
        return ""
    
    def _extract_parameters(self, soup: BeautifulSoup) -> List[Parameter]:
        """Extract parameters from tables and documentation"""
        parameters = []
        
        # Look for parameter tables
        tables = soup.find_all('table')
        
        for table in tables:
            # Check if this looks like a parameters table
            headers = [th.get_text().strip().lower() for th in table.find_all('th')]
            
            if not self._is_parameter_table(headers):
                continue
            
            # Map column indices
            col_map = self._map_parameter_columns(headers)
            
            # Extract parameter rows
            rows = table.find_all('tr')[1:]  # Skip header
            for row in rows:
                cells = [td.get_text().strip() for td in row.find_all('td')]
                
                if len(cells) < 2:
                    continue
                
                param = self._parse_parameter_row(cells, col_map)
                if param:
                    parameters.append(param)
        
        # Also look for parameter descriptions in lists
        parameters.extend(self._extract_parameters_from_lists(soup))
        
        return parameters
    
    def _is_parameter_table(self, headers: List[str]) -> bool:
        """Check if table headers indicate a parameters table"""
        param_indicators = [
            'parameter', 'param', 'name', 'field', 'property',
            'type', 'required', 'description', 'value'
        ]
        
        header_text = ' '.join(headers)
        return any(indicator in header_text for indicator in param_indicators)
    
    def _map_parameter_columns(self, headers: List[str]) -> Dict[str, int]:
        """Map parameter table columns to their purposes"""
        col_map = {}
        
        for i, header in enumerate(headers):
            header_lower = header.lower()
            
            if 'name' in header_lower or 'parameter' in header_lower:
                col_map['name'] = i
            elif 'type' in header_lower:
                col_map['type'] = i
            elif 'required' in header_lower:
                col_map['required'] = i
            elif 'description' in header_lower:
                col_map['description'] = i
            elif 'example' in header_lower:
                col_map['example'] = i
            elif 'location' in header_lower or 'in' in header_lower:
                col_map['location'] = i
        
        return col_map
    
    def _parse_parameter_row(self, cells: List[str], col_map: Dict[str, int]) -> Optional[Parameter]:
        """Parse a parameter table row"""
        if not cells or len(cells) < 2:
            return None
        
        # Extract name (required)
        name_idx = col_map.get('name', 0)
        if name_idx >= len(cells):
            return None
        
        name = cells[name_idx]
        if not name:
            return None
        
        # Extract other fields with defaults
        param_type = cells[col_map.get('type', 1)] if col_map.get('type', 1) < len(cells) else 'string'
        
        required_idx = col_map.get('required')
        required = False
        if required_idx is not None and required_idx < len(cells):
            required_text = cells[required_idx].lower()
            required = 'true' in required_text or 'yes' in required_text or 'required' in required_text
        
        description_idx = col_map.get('description')
        description = ""
        if description_idx is not None and description_idx < len(cells):
            description = cells[description_idx]
        
        example_idx = col_map.get('example')
        example = None
        if example_idx is not None and example_idx < len(cells):
            example = cells[example_idx] if cells[example_idx] else None
        
        location_idx = col_map.get('location')
        location = 'query'  # default
        if location_idx is not None and location_idx < len(cells):
            loc_text = cells[location_idx].lower()
            if 'path' in loc_text:
                location = 'path'
            elif 'header' in loc_text:
                location = 'header'
            elif 'body' in loc_text:
                location = 'body'
        
        return Parameter(
            name=name,
            location=location,
            type=param_type,
            required=required,
            description=description,
            example=example
        )
    
    def _extract_parameters_from_lists(self, soup: BeautifulSoup) -> List[Parameter]:
        """Extract parameters from bullet lists and other formats"""
        parameters = []
        
        # Look for lists that might contain parameters
        lists = soup.find_all(['ul', 'ol', 'dl'])
        
        for lst in lists:
            items = lst.find_all(['li', 'dt', 'dd'])
            
            for item in items:
                text = item.get_text().strip()
                
                # Look for parameter-like patterns
                # Pattern: "name (type): description"
                match = re.match(r'(\w+)\s*\(([^)]+)\):\s*(.+)', text)
                if match:
                    name, param_type, description = match.groups()
                    parameters.append(Parameter(
                        name=name,
                        location='query',
                        type=param_type,
                        required=False,
                        description=description
                    ))
        
        return parameters
    
    def _extract_request_body(self, soup: BeautifulSoup) -> Optional[RequestBody]:
        """Extract request body schema and examples"""
        # Look for JSON examples in code blocks
        code_blocks = soup.find_all(['code', 'pre'])
        
        for block in code_blocks:
            text = block.get_text().strip()
            
            # Check if this looks like a JSON request body
            if text.startswith('{') and '"' in text:
                try:
                    json_data = json.loads(text)
                    
                    # Infer schema from example
                    schema = self._infer_json_schema(json_data)
                    
                    return RequestBody(
                        content_type='application/json',
                        schema=schema,
                        example=json_data
                    )
                except json.JSONDecodeError:
                    continue
        
        return None
    
    def _extract_responses(self, soup: BeautifulSoup) -> Dict[str, Response]:
        """Extract response examples and schemas"""
        responses = {}
        
        # Look for response examples in code blocks
        code_blocks = soup.find_all(['code', 'pre'])
        
        for block in code_blocks:
            text = block.get_text().strip()
            
            # Skip if this looks like a request (has methods)
            if any(method in text for method in ['GET ', 'POST ', 'PUT ', 'DELETE ', 'PATCH ']):
                continue
            
            # Check if this looks like a JSON response
            if text.startswith('{') and '"' in text and len(text) > 10:
                try:
                    json_data = json.loads(text)
                    
                    # Infer schema from example
                    schema = self._infer_json_schema(json_data)
                    
                    responses['200'] = Response(
                        status_code='200',
                        description='Successful response',
                        content_type='application/json',
                        schema=schema,
                        example=json_data
                    )
                    break  # Use first valid JSON response
                    
                except json.JSONDecodeError:
                    continue
        
        # Add default response if none found
        if not responses:
            responses['200'] = Response(
                status_code='200',
                description='Successful response',
                content_type='application/json'
            )
        
        return responses
    
    def _infer_json_schema(self, json_data: Any) -> Dict[str, Any]:
        """Infer JSON schema from example data"""
        if isinstance(json_data, dict):
            properties = {}
            for key, value in json_data.items():
                properties[key] = self._infer_json_schema(value)
            
            return {
                "type": "object",
                "properties": properties
            }
        
        elif isinstance(json_data, list):
            if json_data:
                return {
                    "type": "array",
                    "items": self._infer_json_schema(json_data[0])
                }
            else:
                return {"type": "array"}
        
        elif isinstance(json_data, str):
            return {"type": "string"}
        elif isinstance(json_data, int):
            return {"type": "integer"}
        elif isinstance(json_data, float):
            return {"type": "number"}
        elif isinstance(json_data, bool):
            return {"type": "boolean"}
        else:
            return {"type": "string"}
    
    def _extract_tags(self, url: str, soup: BeautifulSoup) -> List[str]:
        """Extract tags/categories for the endpoint"""
        tags = []
        
        # Extract from URL path
        path_parts = url.split('/')
        for part in path_parts:
            if part and part not in ['reference', 'docs', 'https:', 'apm', 'sparkcognition', 'com']:
                # Clean up the part
                clean_part = part.replace('-', ' ').title()
                if clean_part not in tags and len(clean_part) > 2:
                    tags.append(clean_part)
        
        # Look for category indicators in the page
        text = soup.get_text().lower()
        
        # Common API categories
        category_keywords = {
            'assets': 'Assets',
            'device': 'Devices', 
            'alarm': 'Alarms',
            'forecast': 'Forecasting',
            'performance': 'Performance',
            'health': 'Health',
            'component': 'Components',
            'notification': 'Notifications',
            'plant': 'Plants',
            'user': 'Users',
            'query': 'Data Query',
            'mapping': 'Mappings',
            'availability': 'Availability',
            'power': 'Power',
            'curtailment': 'Curtailment'
        }
        
        for keyword, tag in category_keywords.items():
            if keyword in text and tag not in tags:
                tags.append(tag)
        
        return tags[:3]  # Limit to 3 most relevant tags
    
    def generate_openapi_spec(self, endpoints: List[APIEndpoint]) -> Dict[str, Any]:
        """Stage 3: Generate complete OpenAPI 3.0.3 specification"""
        logger.info("🔄 Stage 3: Generating OpenAPI specification...")
        
        # Group endpoints by path for consolidation
        paths = {}
        components = {"schemas": {}}
        tags = set()
        
        for endpoint in endpoints:
            # Skip endpoints without valid paths
            if not endpoint.path:
                continue
            
            # Collect tags
            tags.update(endpoint.tags)
            
            # Initialize path if needed
            if endpoint.path not in paths:
                paths[endpoint.path] = {}
            
            # Build operation object
            operation = {
                "summary": endpoint.name,
                "description": endpoint.description,
                "operationId": self._generate_operation_id(endpoint),
                "tags": endpoint.tags[:1] if endpoint.tags else ["General"]
            }
            
            # Add parameters
            if endpoint.parameters:
                operation["parameters"] = []
                for param in endpoint.parameters:
                    param_obj = {
                        "name": param.name,
                        "in": param.location,
                        "required": param.required,
                        "description": param.description,
                        "schema": {"type": param.type}
                    }
                    if param.example:
                        param_obj["example"] = param.example
                    
                    operation["parameters"].append(param_obj)
            
            # Add request body
            if endpoint.request_body:
                operation["requestBody"] = {
                    "required": True,
                    "content": {
                        endpoint.request_body.content_type: {
                            "schema": endpoint.request_body.schema
                        }
                    }
                }
                if endpoint.request_body.example:
                    operation["requestBody"]["content"][endpoint.request_body.content_type]["example"] = endpoint.request_body.example
            
            # Add responses
            operation["responses"] = {}
            for status, response in endpoint.responses.items():
                response_obj = {
                    "description": response.description
                }
                
                if response.content_type and response.schema:
                    response_obj["content"] = {
                        response.content_type: {
                            "schema": response.schema
                        }
                    }
                    if response.example:
                        response_obj["content"][response.content_type]["example"] = response.example
                
                operation["responses"][status] = response_obj
            
            # Add operation to path
            paths[endpoint.path][endpoint.method.lower()] = operation
        
        # Build complete OpenAPI spec
        openapi_spec = {
            "openapi": "3.0.3",
            "info": {
                "title": "Avathon API",
                "description": "Complete API specification for Avathon renewable energy management platform",
                "version": "1.0.0",
                "contact": {
                    "name": "Avathon API Support",
                    "url": "https://docs.apm.sparkcognition.com"
                }
            },
            "servers": [
                {
                    "url": "https://renewables.apm.avathon.com/api",
                    "description": "Production server"
                }
            ],
            "tags": [{"name": tag, "description": f"{tag} related operations"} for tag in sorted(tags)],
            "paths": paths,
            "components": components,
            "security": [
                {
                    "sessionAuth": []
                }
            ]
        }
        
        # Add security schemes
        openapi_spec["components"]["securitySchemes"] = {
            "sessionAuth": {
                "type": "apiKey",
                "in": "cookie",
                "name": "connect.sid",
                "description": "Session-based authentication using connect.sid cookie"
            }
        }
        
        logger.info(f"✅ Generated OpenAPI spec with {len(paths)} paths and {len(tags)} tags")
        
        return openapi_spec
    
    def _generate_operation_id(self, endpoint: APIEndpoint) -> str:
        """Generate unique operation ID for endpoint"""
        # Clean up the name to be camelCase
        name_parts = endpoint.name.lower().replace('-', ' ').replace('_', ' ').split()
        
        if not name_parts:
            name_parts = endpoint.path.strip('/').split('/')[-1:]
        
        # Convert to camelCase
        operation_id = name_parts[0]
        for part in name_parts[1:]:
            operation_id += part.capitalize()
        
        # Add method prefix
        method_prefix = endpoint.method.lower()
        if method_prefix != 'get':
            operation_id = method_prefix + operation_id.capitalize()
        
        return operation_id
    
    def save_results(self, endpoints: List[APIEndpoint], openapi_spec: Dict[str, Any]):
        """Save all results to files"""
        logger.info("💾 Saving results...")
        
        # Save raw endpoint data
        endpoints_data = [asdict(endpoint) for endpoint in endpoints]
        with open("endpoint_details.json", "w") as f:
            json.dump(endpoints_data, f, indent=2)
        
        # Save OpenAPI specification
        with open("avathon_api_complete.json", "w") as f:
            json.dump(openapi_spec, f, indent=2)
        
        # Generate parameter catalog
        all_parameters = []
        for endpoint in endpoints:
            for param in endpoint.parameters:
                param_info = asdict(param)
                param_info['endpoint'] = endpoint.name
                param_info['path'] = endpoint.path
                all_parameters.append(param_info)
        
        with open("parameter_catalog.json", "w") as f:
            json.dump(all_parameters, f, indent=2)
        
        # Generate scraping report
        report = {
            "scraping_timestamp": asyncio.get_event_loop().time(),
            "total_endpoints_discovered": len(endpoints) + len(self.failed_endpoints),
            "successfully_scraped": len(endpoints),
            "failed_endpoints": len(self.failed_endpoints),
            "failed_urls": self.failed_endpoints,
            "success_rate": len(endpoints) / (len(endpoints) + len(self.failed_endpoints)) * 100,
            "methods_distribution": {},
            "tags_distribution": {},
            "paths_with_parameters": sum(1 for e in endpoints if e.parameters),
            "paths_with_request_body": sum(1 for e in endpoints if e.request_body),
            "paths_with_examples": sum(1 for e in endpoints if e.responses and any(r.example for r in e.responses.values()))
        }
        
        # Calculate distributions
        for endpoint in endpoints:
            method = endpoint.method
            report["methods_distribution"][method] = report["methods_distribution"].get(method, 0) + 1
            
            for tag in endpoint.tags:
                report["tags_distribution"][tag] = report["tags_distribution"].get(tag, 0) + 1
        
        with open("scraping_report.json", "w") as f:
            json.dump(report, f, indent=2)
        
        logger.info("💾 Results saved:")
        logger.info("   📄 endpoint_details.json - Raw extracted data")
        logger.info("   📋 avathon_api_complete.json - Complete OpenAPI specification")
        logger.info("   📊 parameter_catalog.json - All parameters catalog")
        logger.info("   📈 scraping_report.json - Scraping statistics")
        
        return report

async def main():
    """Main execution function"""
    logger.info("🚀 Starting Comprehensive Avathon API Scraper...")
    
    scraper = ComprehensiveAvathonScraper()
    
    try:
        # Stage 1: Discover all endpoint URLs
        endpoint_urls = await scraper.discover_all_endpoint_urls()
        
        if not endpoint_urls:
            logger.error("❌ No endpoint URLs discovered")
            return
        
        # Stage 2: Scrape detailed specifications
        endpoints = await scraper.scrape_all_endpoints(endpoint_urls)
        
        if not endpoints:
            logger.error("❌ No endpoints successfully scraped")
            return
        
        # Stage 3: Generate OpenAPI specification
        openapi_spec = scraper.generate_openapi_spec(endpoints)
        
        # Save all results
        report = scraper.save_results(endpoints, openapi_spec)
        
        # Final summary
        logger.info("🎉 COMPREHENSIVE SCRAPING COMPLETE!")
        logger.info(f"📊 Success Rate: {report['success_rate']:.1f}%")
        logger.info(f"📋 Total Endpoints: {report['successfully_scraped']}")
        logger.info(f"🔧 Methods: {report['methods_distribution']}")
        logger.info(f"🏷️  Tags: {list(report['tags_distribution'].keys())}")
        logger.info(f"📈 Endpoints with Parameters: {report['paths_with_parameters']}")
        logger.info(f"📥 Endpoints with Request Bodies: {report['paths_with_request_body']}")
        logger.info(f"📤 Endpoints with Examples: {report['paths_with_examples']}")
        
        if report['failed_endpoints'] > 0:
            logger.warning(f"⚠️  {report['failed_endpoints']} endpoints failed - see scraping_report.json")
        
    except Exception as e:
        logger.error(f"❌ Comprehensive scraping failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())