#!/usr/bin/env python3
"""
Fixed Avathon scraper with proper HTTP decompression handling
"""

import asyncio
import json
import logging
import gzip
import zlib
from typing import List, Dict, Any

import httpx
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DecompressionFixScraper:
    def __init__(self):
        self.docs_url = "https://docs.apm.sparkcognition.com"
        
        # Use the exact cookies from your browser session
        self.cookies = {
            'connect.sid': 's%3A05L4a8drF65NflPjahqbtCgn1QT3G7Ru.BaApdohf6tO%2FpmLmImgWILalJFdBh5KHYQwAUqG8Imw',
            '__cf_bm': 'vZKhA9UxyWORIhSV3d5.T7cPeAolwgr_6nel5mCXe48-1755893974-1.0.1.1-dUlqeWOgtc4H5pALXgfpz.FZXyxf7qNM7ilir4wm1CsEnz4lnMV38hV1jpMYxC_bTCm0o4Wh_AKuOZZsdgdc_58sNMjrshKFpKPRh7Smaw0',
            'readme_language': 'shell',
            'readme_library': '{"shell":"curl"}'
        }
        
        # Use proper headers with explicit compression handling
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:142.0) Gecko/20100101 Firefox/142.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',  # Tell server we accept compressed content
            'Referer': 'https://renewables.apm.avathon.com/',  # Critical for authentication
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'cross-site',
            'Priority': 'u=0, i'
        }
    
    def decompress_response(self, content: bytes, encoding: str) -> str:
        """Manually decompress response content based on encoding"""
        try:
            if 'gzip' in encoding:
                logger.info("🔧 Decompressing gzip content...")
                return gzip.decompress(content).decode('utf-8')
            elif 'deflate' in encoding:
                logger.info("🔧 Decompressing deflate content...")
                return zlib.decompress(content).decode('utf-8')
            elif 'br' in encoding:
                logger.info("🔧 Decompressing brotli content...")
                import brotli
                return brotli.decompress(content).decode('utf-8')
            else:
                # Not compressed or unknown compression
                return content.decode('utf-8')
        except Exception as e:
            logger.error(f"❌ Decompression failed: {e}")
            # Try as plain text
            try:
                return content.decode('utf-8', errors='ignore')
            except:
                return str(content)
    
    async def test_decompression_methods(self):
        """Test different approaches to fix the decompression issue"""
        logger.info("🧪 Testing multiple decompression approaches...")
        
        main_docs_url = f"{self.docs_url}/reference/overview-api"
        
        # Method 1: httpx with manual decompression disabled
        logger.info("📋 Method 1: httpx with manual decompression control")
        try:
            async with httpx.AsyncClient(
                cookies=self.cookies,
                headers=self.headers,
                timeout=30.0,
                follow_redirects=True
            ) as client:
                response = await client.get(main_docs_url)
                logger.info(f"Status: {response.status_code}")
                logger.info(f"Content-Encoding: {response.headers.get('content-encoding', 'none')}")
                logger.info(f"Content-Length: {len(response.content)} bytes")
                logger.info(f"Response Headers: {dict(response.headers)}")
                
                # Try httpx's automatic decompression first
                try:
                    content = response.text
                    logger.info(f"✅ Method 1A - httpx auto-decompression: {len(content)} chars")
                    
                    with open("method1a_httpx_auto.html", "w") as f:
                        f.write(content)
                    
                    # Check if it's actually HTML
                    if '<html' in content.lower() or '<!doctype' in content.lower():
                        logger.info("✅ Method 1A produced valid HTML!")
                        return content
                        
                except Exception as e:
                    logger.warning(f"Method 1A failed: {e}")
                
                # Try manual decompression
                try:
                    encoding = response.headers.get('content-encoding', '')
                    content = self.decompress_response(response.content, encoding)
                    logger.info(f"✅ Method 1B - manual decompression: {len(content)} chars")
                    
                    with open("method1b_manual_decomp.html", "w") as f:
                        f.write(content)
                    
                    if '<html' in content.lower() or '<!doctype' in content.lower():
                        logger.info("✅ Method 1B produced valid HTML!")
                        return content
                        
                except Exception as e:
                    logger.warning(f"Method 1B failed: {e}")
        
        except Exception as e:
            logger.error(f"Method 1 failed: {e}")
        
        # Method 2: Use requests library
        logger.info("📋 Method 2: Using requests library")
        try:
            import requests
            
            session = requests.Session()
            session.cookies.update(self.cookies)
            session.headers.update(self.headers)
            
            response = session.get(main_docs_url)
            logger.info(f"Requests status: {response.status_code}")
            logger.info(f"Requests content length: {len(response.text)} chars")
            
            with open("method2_requests.html", "w") as f:
                f.write(response.text)
            
            if '<html' in response.text.lower() or '<!doctype' in response.text.lower():
                logger.info("✅ Method 2 (requests) produced valid HTML!")
                return response.text
                
        except ImportError:
            logger.warning("requests library not available")
        except Exception as e:
            logger.error(f"Method 2 failed: {e}")
        
        # Method 3: curl via subprocess
        logger.info("📋 Method 3: Using curl subprocess")
        try:
            import subprocess
            
            # Build curl command with exact headers and cookies
            cookie_string = "; ".join([f"{k}={v}" for k, v in self.cookies.items()])
            
            curl_cmd = [
                'curl', '-s',  # silent
                '-H', f'User-Agent: {self.headers["User-Agent"]}',
                '-H', f'Accept: {self.headers["Accept"]}',
                '-H', f'Accept-Language: {self.headers["Accept-Language"]}',
                '-H', f'Accept-Encoding: {self.headers["Accept-Encoding"]}',
                '-H', f'Referer: {self.headers["Referer"]}',
                '-H', f'Cookie: {cookie_string}',
                '--compressed',  # Important: let curl handle decompression
                main_docs_url
            ]
            
            result = subprocess.run(curl_cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                content = result.stdout
                logger.info(f"✅ Method 3 - curl: {len(content)} chars")
                
                with open("method3_curl.html", "w") as f:
                    f.write(content)
                
                if '<html' in content.lower() or '<!doctype' in content.lower():
                    logger.info("✅ Method 3 (curl) produced valid HTML!")
                    return content
            else:
                logger.error(f"curl failed: {result.stderr}")
                
        except Exception as e:
            logger.error(f"Method 3 failed: {e}")
        
        logger.error("❌ All decompression methods failed")
        return None
    
    async def analyze_working_content(self, content: str):
        """Analyze successfully decompressed content"""
        if not content:
            return
        
        logger.info("🔍 Analyzing decompressed content...")
        
        soup = BeautifulSoup(content, 'html.parser')
        
        # Basic page info
        title = soup.find('title')
        logger.info(f"📄 Page title: {title.get_text().strip() if title else 'No title'}")
        
        # Look for API-related content
        api_indicators = [
            'api', 'endpoint', 'reference', 'documentation',
            'swagger', 'openapi', 'rest', 'json'
        ]
        
        page_text = soup.get_text().lower()
        found_indicators = [indicator for indicator in api_indicators if indicator in page_text]
        logger.info(f"🔍 API indicators found: {found_indicators}")
        
        # Look for navigation links
        links = soup.find_all('a', href=True)
        reference_links = [link['href'] for link in links if '/reference/' in link['href']]
        logger.info(f"📋 Found {len(reference_links)} reference links")
        
        # Show first few links
        for i, link in enumerate(reference_links[:5]):
            logger.info(f"  {i+1}. {link}")
        
        # Look for any obvious API endpoint patterns
        import re
        endpoint_patterns = re.findall(r'(/api/[^\s<>"]+)', content)
        if endpoint_patterns:
            unique_endpoints = list(set(endpoint_patterns))
            logger.info(f"🎯 Found {len(unique_endpoints)} API endpoint patterns:")
            for endpoint in unique_endpoints[:10]:
                logger.info(f"  - {endpoint}")
        
        # Save analysis results
        analysis = {
            'title': title.get_text().strip() if title else None,
            'content_length': len(content),
            'api_indicators': found_indicators,
            'reference_links': reference_links,
            'endpoint_patterns': list(set(endpoint_patterns)) if endpoint_patterns else []
        }
        
        with open("content_analysis.json", "w") as f:
            json.dump(analysis, f, indent=2)
        
        logger.info("💾 Content analysis saved to content_analysis.json")
        return analysis

async def main():
    """Main function to test decompression fixes"""
    logger.info("🚀 Starting Decompression Fix Test...")
    
    scraper = DecompressionFixScraper()
    
    try:
        # Test different decompression methods
        content = await scraper.test_decompression_methods()
        
        if content:
            logger.info("🎉 SUCCESS: Got readable HTML content!")
            await scraper.analyze_working_content(content)
        else:
            logger.error("❌ FAILED: Could not decompress content with any method")
            
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")

if __name__ == "__main__":
    # Install brotli if needed
    try:
        import brotli
    except ImportError:
        logger.warning("brotli not installed - install with: pip install brotli")
    
    asyncio.run(main())