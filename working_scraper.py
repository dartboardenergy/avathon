#!/usr/bin/env python3
"""
Working Avathon API scraper using exact browser headers and cookies
"""

import asyncio
import json
import logging
from typing import List, Dict, Any
from urllib.parse import urljoin
import re

import httpx
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class WorkingAvathonScraper:
    def __init__(self):
        self.docs_url = "https://docs.apm.sparkcognition.com"
        
        # Use the exact cookies from your browser session
        self.cookies = {
            'connect.sid': 's%3A05L4a8drF65NflPjahqbtCgn1QT3G7Ru.BaApdohf6tO%2FpmLmImgWILalJFdBh5KHYQwAUqG8Imw',
            '__cf_bm': 'vZKhA9UxyWORIhSV3d5.T7cPeAolwgr_6nel5mCXe48-1755893974-1.0.1.1-dUlqeWOgtc4H5pALXgfpz.FZXyxf7qNM7ilir4wm1CsEnz4lnMV38hV1jpMYxC_bTCm0o4Wh_AKuOZZsdgdc_58sNMjrshKFpKPRh7Smaw0',
            'readme_language': 'shell',
            'readme_library': '{"shell":"curl"}'
        }
        
        # Use the exact headers from your browser
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:142.0) Gecko/20100101 Firefox/142.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Referer': 'https://renewables.apm.avathon.com/',  # This is crucial!
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'cross-site',
            'Priority': 'u=0, i'
        }
        
        self.discovered_endpoints = []
    
    async def test_access(self):
        """Test if we can access the API documentation with these cookies"""
        logger.info("🧪 Testing API documentation access...")
        
        async with httpx.AsyncClient(
            cookies=self.cookies,
            headers=self.headers,
            timeout=30.0,
            follow_redirects=True
        ) as client:
            
            main_docs_url = f"{self.docs_url}/reference/overview-api"
            logger.info(f"📍 Requesting: {main_docs_url}")
            
            response = await client.get(main_docs_url)
            
            logger.info(f"📊 Response status: {response.status_code}")
            logger.info(f"📍 Final URL: {response.url}")
            
            # Save the page for inspection
            with open("working_api_docs.html", "w") as f:
                f.write(response.text)
            logger.info("💾 Page saved to working_api_docs.html")
            
            # Check if we got the actual docs or password page
            if 'password' in response.text.lower():
                logger.error("❌ Still getting password page")
                return False
            elif 'api' in response.text.lower() and 'reference' in response.text.lower():
                logger.info("✅ Successfully accessed API documentation!")
                return True
            else:
                logger.warning("⚠️  Got response but unclear if it's the docs")
                return True  # Let's proceed anyway
    
    async def discover_all_endpoints(self):
        """Discover and scrape all API endpoints"""
        logger.info("🔍 Starting comprehensive endpoint discovery...")
        
        async with httpx.AsyncClient(
            cookies=self.cookies,
            headers=self.headers,
            timeout=30.0,
            follow_redirects=True
        ) as client:
            
            # Get the main docs page
            main_docs_url = f"{self.docs_url}/reference/overview-api"
            response = await client.get(main_docs_url)
            
            if response.status_code != 200:
                logger.error(f"❌ Failed to get main docs page: {response.status_code}")
                return []
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find all links that look like API endpoints
            endpoint_urls = set()
            
            # Strategy 1: Look for links in navigation/sidebar
            nav_links = soup.find_all('a', href=True)
            for link in nav_links:
                href = link['href']
                if '/reference/' in href:
                    if href.startswith('/'):
                        full_url = f"{self.docs_url}{href}"
                    elif href.startswith('http'):
                        full_url = href
                    else:
                        full_url = urljoin(main_docs_url, href)
                    
                    endpoint_urls.add(full_url)
            
            # Strategy 2: Look for patterns in the page source that might reveal endpoints
            page_text = response.text
            
            # Look for href patterns
            href_patterns = re.findall(r'href=["\']([^"\']*\/reference\/[^"\']*)["\']', page_text)
            for pattern in href_patterns:
                if pattern.startswith('/'):
                    full_url = f"{self.docs_url}{pattern}"
                else:
                    full_url = urljoin(main_docs_url, pattern)
                endpoint_urls.add(full_url)
            
            # Filter out non-endpoint URLs
            filtered_endpoints = []
            for url in endpoint_urls:
                if self.is_likely_endpoint_url(url):
                    filtered_endpoints.append(url)
            
            logger.info(f"📋 Found {len(filtered_endpoints)} potential endpoint URLs")
            
            # Log first few URLs for verification
            for i, url in enumerate(sorted(filtered_endpoints)[:10]):
                logger.info(f"  {i+1}. {url}")
            
            if len(filtered_endpoints) > 10:
                logger.info(f"  ... and {len(filtered_endpoints) - 10} more")
            
            # Scrape each endpoint
            endpoints = []
            for i, url in enumerate(filtered_endpoints, 1):
                try:
                    logger.info(f"📄 Scraping {i}/{len(filtered_endpoints)}: {url.split('/')[-1]}")
                    endpoint_data = await self.scrape_single_endpoint(client, url)
                    if endpoint_data:
                        endpoints.append(endpoint_data)
                    
                    # Small delay to be respectful
                    await asyncio.sleep(0.5)
                    
                except Exception as e:
                    logger.error(f"❌ Error scraping {url}: {e}")
                    continue
            
            logger.info(f"✅ Successfully scraped {len(endpoints)} endpoints")
            return endpoints
    
    def is_likely_endpoint_url(self, url: str) -> bool:
        """Filter out URLs that don't look like API endpoints"""
        if not url.startswith(self.docs_url):
            return False
        
        # Must contain /reference/
        if '/reference/' not in url:
            return False
        
        # Skip overview pages and general docs
        skip_patterns = [
            'overview',
            'getting-started', 
            'authentication',
            'errors',
            'introduction',
            'quickstart',
            '#',  # Skip anchors
        ]
        
        url_lower = url.lower()
        return not any(pattern in url_lower for pattern in skip_patterns)
    
    async def scrape_single_endpoint(self, client: httpx.AsyncClient, url: str) -> Dict[str, Any]:
        """Scrape a single endpoint documentation page"""
        try:
            response = await client.get(url)
            
            if response.status_code != 200:
                logger.warning(f"⚠️  HTTP {response.status_code} for {url}")
                return None
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract endpoint information
            endpoint_data = {
                'url': url,
                'name': self.extract_name(soup, url),
                'method': self.extract_method(soup),
                'path': self.extract_path(soup),
                'description': self.extract_description(soup),
                'parameters': self.extract_parameters(soup),
                'request_body': self.extract_request_body(soup),
                'responses': self.extract_responses(soup),
                'examples': self.extract_examples(soup),
                'tags': self.extract_tags(url, soup)
            }
            
            return endpoint_data
            
        except Exception as e:
            logger.error(f"❌ Error scraping {url}: {e}")
            return None
    
    def extract_name(self, soup: BeautifulSoup, url: str) -> str:
        """Extract endpoint name"""
        # Try h1 first
        h1 = soup.find('h1')
        if h1:
            return h1.get_text().strip()
        
        # Fallback to URL
        return url.split('/')[-1].replace('-', ' ').title()
    
    def extract_method(self, soup: BeautifulSoup) -> str:
        """Extract HTTP method"""
        # Look for method in various places
        text = soup.get_text().upper()
        
        methods = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']
        for method in methods:
            if f'{method} /' in text or f'{method}\n/' in text:
                return method
        
        # Look in code blocks
        code_blocks = soup.find_all(['code', 'pre'])
        for block in code_blocks:
            block_text = block.get_text().upper()
            for method in methods:
                if f'{method} /' in block_text:
                    return method
        
        return 'GET'  # Default
    
    def extract_path(self, soup: BeautifulSoup) -> str:
        """Extract API path"""
        # Look for paths that start with /
        text = soup.get_text()
        
        # Find patterns like "GET /api/v1/something"
        import re
        path_patterns = re.findall(r'(?:GET|POST|PUT|DELETE|PATCH)\s+(/[^\s\n]+)', text)
        if path_patterns:
            return path_patterns[0]
        
        # Look in code blocks
        code_blocks = soup.find_all(['code', 'pre'])
        for block in code_blocks:
            block_text = block.get_text()
            path_patterns = re.findall(r'(?:GET|POST|PUT|DELETE|PATCH)\s+(/[^\s\n]+)', block_text)
            if path_patterns:
                return path_patterns[0]
        
        # Look for any path-like string
        path_patterns = re.findall(r'(/api/[^\s\n]+)', text)
        if path_patterns:
            return path_patterns[0]
        
        return ""
    
    def extract_description(self, soup: BeautifulSoup) -> str:
        """Extract endpoint description"""
        # Look for first paragraph after h1
        h1 = soup.find('h1')
        if h1:
            next_p = h1.find_next('p')
            if next_p:
                return next_p.get_text().strip()
        
        # Fallback to any paragraph
        p = soup.find('p')
        if p:
            return p.get_text().strip()
        
        return ""
    
    def extract_parameters(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Extract parameters from tables"""
        parameters = []
        
        # Look for parameter tables
        tables = soup.find_all('table')
        for table in tables:
            headers = [th.get_text().strip().lower() for th in table.find_all('th')]
            
            # Check if this looks like a parameters table
            if any(keyword in ' '.join(headers) for keyword in ['parameter', 'name', 'field']):
                rows = table.find_all('tr')[1:]  # Skip header
                
                for row in rows:
                    cells = [td.get_text().strip() for td in row.find_all('td')]
                    if len(cells) >= 2:
                        param = {
                            'name': cells[0],
                            'type': cells[1] if len(cells) > 1 else 'string',
                            'required': 'required' in (cells[2] if len(cells) > 2 else '').lower(),
                            'description': cells[3] if len(cells) > 3 else cells[2] if len(cells) > 2 else ''
                        }
                        parameters.append(param)
        
        return parameters
    
    def extract_request_body(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract request body examples"""
        # Look for JSON in code blocks
        code_blocks = soup.find_all(['code', 'pre'])
        
        for block in code_blocks:
            text = block.get_text().strip()
            if text.startswith('{') and text.endswith('}'):
                try:
                    return json.loads(text)
                except:
                    continue
        
        return None
    
    def extract_responses(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract response examples"""
        responses = {}
        
        # Look for response sections
        code_blocks = soup.find_all(['code', 'pre'])
        
        for block in code_blocks:
            text = block.get_text().strip()
            if text.startswith('{') and '"' in text:
                try:
                    response_data = json.loads(text)
                    responses['200'] = response_data
                    break
                except:
                    continue
        
        return responses
    
    def extract_examples(self, soup: BeautifulSoup) -> List[str]:
        """Extract code examples"""
        examples = []
        
        # Look for curl examples
        code_blocks = soup.find_all(['code', 'pre'])
        
        for block in code_blocks:
            text = block.get_text().strip()
            if 'curl' in text.lower() or 'http' in text.lower():
                examples.append(text)
        
        return examples[:3]  # Limit to 3 examples
    
    def extract_tags(self, url: str, soup: BeautifulSoup) -> List[str]:
        """Extract tags/categories"""
        tags = []
        
        # Extract from URL
        parts = url.split('/')
        for part in parts:
            if part and part not in ['reference', 'api', 'docs', 'https:', 'v1']:
                clean_part = part.replace('-', ' ').title()
                if clean_part not in tags:
                    tags.append(clean_part)
        
        return tags[:2]  # Limit to 2 tags
    
    def save_results(self, endpoints: List[Dict[str, Any]]):
        """Save scraped results to files"""
        # Save raw endpoints data
        with open("avathon_endpoints_working.json", "w") as f:
            json.dump(endpoints, f, indent=2)
        
        # Generate summary
        summary = {
            'total_endpoints': len(endpoints),
            'methods': {},
            'tags': set(),
            'endpoints_summary': []
        }
        
        for endpoint in endpoints:
            # Count methods
            method = endpoint.get('method', 'GET')
            summary['methods'][method] = summary['methods'].get(method, 0) + 1
            
            # Collect tags
            tags = endpoint.get('tags', [])
            summary['tags'].update(tags)
            
            # Add to summary
            summary['endpoints_summary'].append({
                'name': endpoint.get('name'),
                'method': method,
                'path': endpoint.get('path'),
                'url': endpoint.get('url')
            })
        
        # Convert set to list for JSON serialization
        summary['tags'] = sorted(list(summary['tags']))
        
        with open("avathon_scraping_summary.json", "w") as f:
            json.dump(summary, f, indent=2)
        
        logger.info(f"💾 Results saved:")
        logger.info(f"   📄 Raw data: avathon_endpoints_working.json")
        logger.info(f"   📊 Summary: avathon_scraping_summary.json")
        
        return summary

async def main():
    """Main function"""
    logger.info("🚀 Starting Working Avathon API Scraper...")
    
    scraper = WorkingAvathonScraper()
    
    try:
        # Test access first
        if not await scraper.test_access():
            logger.error("❌ Cannot access API documentation")
            return
        
        # Discover and scrape all endpoints
        endpoints = await scraper.discover_all_endpoints()
        
        if not endpoints:
            logger.error("❌ No endpoints were discovered")
            return
        
        # Save results
        summary = scraper.save_results(endpoints)
        
        logger.info("🎉 SUCCESS!")
        logger.info(f"📊 Scraped {summary['total_endpoints']} endpoints")
        logger.info(f"📋 Methods: {summary['methods']}")
        logger.info(f"🏷️  Categories: {summary['tags']}")
        
    except Exception as e:
        logger.error(f"❌ Scraping failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())