#!/usr/bin/env python3
"""
Selenium-based Avathon API Documentation Scraper

Uses Selenium WebDriver to handle JavaScript-heavy SPA authentication
and then scrapes the API documentation.
"""

import os
import json
import time
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
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

class SeleniumAvathonScraper:
    """
    Selenium-based scraper for JavaScript-heavy Avathon platform
    """
    
    def __init__(self):
        self.username = os.getenv("AVATHON_USERNAME")
        self.password = os.getenv("AVATHON_PASSWORD")
        
        if not self.username or not self.password:
            raise ValueError("AVATHON_USERNAME and AVATHON_PASSWORD must be set in .env file")
        
        self.base_url = "https://renewables.apm.avathon.com"
        self.docs_url = "https://docs.apm.sparkcognition.com"
        self.driver = None
        self.discovered_endpoints = []
        
    def setup_driver(self):
        """Setup Chrome WebDriver with appropriate options"""
        logger.info("🔧 Setting up Chrome WebDriver...")
        
        chrome_options = Options()
        # chrome_options.add_argument("--headless")  # Comment out to see what's happening
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
        
        logger.info("📋 Chrome options configured:")
        for arg in chrome_options.arguments:
            logger.info(f"   {arg}")
        
        try:
            logger.info("🚀 Initializing Chrome WebDriver...")
            self.driver = webdriver.Chrome(options=chrome_options)
            logger.info("✅ Chrome WebDriver initialized successfully")
            logger.info(f"🌐 Browser session ID: {self.driver.session_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to initialize Chrome WebDriver: {e}")
            logger.info("💡 Try installing ChromeDriver: brew install chromedriver")
            return False
    
    def authenticate_with_selenium(self) -> bool:
        """
        Authenticate using Selenium WebDriver to handle SPA
        """
        if not self.driver:
            logger.error("WebDriver not initialized")
            return False
        
        try:
            logger.info("🔐 Starting Selenium-based authentication...")
            logger.info(f"📍 Target URL: {self.base_url}")
            logger.info(f"👤 Username: {self.username}")
            logger.info(f"🔑 Password: {'*' * len(self.password) if self.password else 'NOT SET'}")
            
            # Navigate to the main page
            logger.info("Step 1: Loading Avathon homepage...")
            logger.info(f"🌐 Navigating to: {self.base_url}")
            start_time = time.time()
            self.driver.get(self.base_url)
            load_time = time.time() - start_time
            logger.info(f"⏱️  Page loaded in {load_time:.2f} seconds")
            
            current_url = self.driver.current_url
            page_title = self.driver.title
            logger.info(f"📍 Current URL: {current_url}")
            logger.info(f"📄 Page title: {page_title}")
            
            logger.info("⏳ Waiting for SPA to fully load...")
            time.sleep(3)  # Let the SPA load
            
            # Look for login form elements
            logger.info("Step 2: 🔍 Looking for login form elements...")
            
            # First, let's see what's actually on the page
            logger.info("📋 Analyzing page content...")
            page_source_length = len(self.driver.page_source)
            logger.info(f"📄 Page source length: {page_source_length} characters")
            
            # Check for common login indicators in page source
            page_source = self.driver.page_source.lower()
            login_indicators = ['login', 'sign in', 'username', 'email', 'password']
            found_indicators = [indicator for indicator in login_indicators if indicator in page_source]
            logger.info(f"🔍 Found login indicators: {found_indicators}")
            
            # Try different common selectors for username/email field
            username_selectors = [
                "input[name='username']",
                "input[name='email']", 
                "input[type='email']",
                "input[placeholder*='username' i]",
                "input[placeholder*='email' i]",
                "#username",
                "#email",
                ".username-input",
                ".email-input"
            ]
            
            logger.info(f"🎯 Trying {len(username_selectors)} username field selectors...")
            username_field = None
            for i, selector in enumerate(username_selectors, 1):
                try:
                    logger.info(f"   {i}. Trying selector: {selector}")
                    username_field = self.driver.find_element(By.CSS_SELECTOR, selector)
                    logger.info(f"✅ Found username field with selector: {selector}")
                    break
                except NoSuchElementException:
                    logger.info(f"   ❌ Selector {selector} not found")
                    continue
            
            if not username_field:
                # Try to find any input field and see what's available
                logger.info("No username field found with common selectors. Analyzing all inputs...")
                inputs = self.driver.find_elements(By.TAG_NAME, "input")
                for i, input_elem in enumerate(inputs):
                    input_type = input_elem.get_attribute("type")
                    input_name = input_elem.get_attribute("name")
                    input_placeholder = input_elem.get_attribute("placeholder")
                    input_id = input_elem.get_attribute("id")
                    logger.info(f"Input {i+1}: type={input_type}, name={input_name}, placeholder={input_placeholder}, id={input_id}")
                
                logger.error("❌ Could not find username/email input field")
                return False
            
            # Try different common selectors for password field
            password_selectors = [
                "input[name='password']",
                "input[type='password']",
                "#password",
                ".password-input"
            ]
            
            password_field = None
            for selector in password_selectors:
                try:
                    password_field = self.driver.find_element(By.CSS_SELECTOR, selector)
                    logger.info(f"✅ Found password field with selector: {selector}")
                    break
                except NoSuchElementException:
                    continue
            
            if not password_field:
                logger.error("❌ Could not find password input field")
                return False
            
            # Fill in credentials
            logger.info("Step 3: Filling in credentials")
            username_field.clear()
            username_field.send_keys(self.username)
            
            password_field.clear()
            password_field.send_keys(self.password)
            
            # Look for submit button
            submit_selectors = [
                "button[type='submit']",
                "input[type='submit']",
                "button:contains('Login')",
                "button:contains('Sign In')",
                ".login-button",
                ".submit-button"
            ]
            
            submit_button = None
            for selector in submit_selectors:
                try:
                    submit_button = self.driver.find_element(By.CSS_SELECTOR, selector)
                    logger.info(f"✅ Found submit button with selector: {selector}")
                    break
                except NoSuchElementException:
                    continue
            
            if not submit_button:
                # Look for any button and see what's available
                logger.info("No submit button found with common selectors. Analyzing all buttons...")
                buttons = self.driver.find_elements(By.TAG_NAME, "button")
                for i, button in enumerate(buttons):
                    button_text = button.text
                    button_type = button.get_attribute("type")
                    logger.info(f"Button {i+1}: text='{button_text}', type={button_type}")
                    if 'login' in button_text.lower() or 'sign' in button_text.lower():
                        submit_button = button
                        logger.info(f"✅ Using button with text: {button_text}")
                        break
            
            if not submit_button:
                logger.error("❌ Could not find submit button")
                return False
            
            # Submit the form
            logger.info("Step 4: Submitting login form")
            submit_button.click()
            
            # Wait for redirect or success indication
            logger.info("Step 5: Waiting for authentication result...")
            time.sleep(5)
            
            # Check if we're successfully authenticated
            current_url = self.driver.current_url
            logger.info(f"Current URL after login attempt: {current_url}")
            
            # Look for indicators of successful login
            success_indicators = [
                "dashboard",
                "home",
                "main",
                "app"
            ]
            
            is_authenticated = any(indicator in current_url.lower() for indicator in success_indicators)
            
            if is_authenticated:
                logger.info("✅ Authentication appears successful!")
                return True
            else:
                # Check for error messages
                error_elements = self.driver.find_elements(By.CSS_SELECTOR, ".error, .alert-danger, [class*='error']")
                if error_elements:
                    error_text = error_elements[0].text
                    logger.error(f"❌ Authentication failed with error: {error_text}")
                else:
                    logger.error("❌ Authentication failed - still on login page")
                return False
                
        except Exception as e:
            logger.error(f"Error during Selenium authentication: {e}")
            return False
    
    def get_authenticated_session(self) -> Optional[httpx.AsyncClient]:
        """
        Extract cookies from Selenium session and create httpx client
        """
        if not self.driver:
            return None
        
        try:
            # Get cookies from Selenium
            selenium_cookies = self.driver.get_cookies()
            
            # Convert to httpx format
            cookies = {}
            for cookie in selenium_cookies:
                cookies[cookie['name']] = cookie['value']
            
            # Create httpx client with cookies
            client = httpx.AsyncClient(
                cookies=cookies,
                timeout=30.0,
                follow_redirects=True,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
            )
            
            logger.info(f"✅ Created authenticated httpx client with {len(cookies)} cookies")
            return client
            
        except Exception as e:
            logger.error(f"Error creating authenticated session: {e}")
            return None
    
    async def scrape_with_authenticated_session(self) -> List[APIEndpoint]:
        """
        Use authenticated session to scrape API documentation
        """
        client = self.get_authenticated_session()
        if not client:
            return []
        
        try:
            # Test access to documentation
            logger.info("Testing access to API documentation...")
            docs_response = await client.get(f"{self.docs_url}/reference/overview-api")
            
            if docs_response.status_code != 200:
                logger.error(f"❌ Cannot access docs: {docs_response.status_code}")
                return []
            
            if 'password' in docs_response.text.lower():
                logger.error("❌ Documentation still password protected")
                return []
            
            logger.info("✅ Successfully accessed API documentation!")
            
            # Parse the documentation to find all endpoints
            soup = BeautifulSoup(docs_response.text, 'html.parser')
            
            # Look for API endpoint links
            links = soup.find_all('a', href=True)
            endpoint_urls = []
            
            for link in links:
                href = link['href']
                if '/reference/' in href and href not in endpoint_urls:
                    full_url = f"{self.docs_url}{href}" if href.startswith('/') else href
                    endpoint_urls.append(full_url)
            
            logger.info(f"Found {len(endpoint_urls)} potential endpoint pages")
            
            # Scrape each endpoint page
            endpoints = []
            for url in endpoint_urls[:10]:  # Limit to first 10 for testing
                try:
                    logger.info(f"Scraping: {url}")
                    response = await client.get(url)
                    
                    if response.status_code == 200:
                        endpoint_soup = BeautifulSoup(response.text, 'html.parser')
                        endpoint = self._extract_endpoint_from_page(endpoint_soup, url)
                        if endpoint:
                            endpoints.append(endpoint)
                    
                    time.sleep(1)  # Be respectful
                    
                except Exception as e:
                    logger.error(f"Error scraping {url}: {e}")
                    continue
            
            await client.aclose()
            return endpoints
            
        except Exception as e:
            logger.error(f"Error during authenticated scraping: {e}")
            if client:
                await client.aclose()
            return []
    
    def _extract_endpoint_from_page(self, soup: BeautifulSoup, url: str) -> Optional[APIEndpoint]:
        """Extract endpoint information from a documentation page"""
        try:
            # Extract basic info
            title = soup.find('h1')
            name = title.get_text().strip() if title else url.split('/')[-1]
            
            # Look for HTTP method and path
            method = "GET"  # Default
            path = ""
            
            # Try to find method and path in the content
            text = soup.get_text()
            import re
            method_match = re.search(r'(GET|POST|PUT|DELETE|PATCH)\s+(/[^\s]+)', text)
            if method_match:
                method = method_match.group(1)
                path = method_match.group(2)
            
            # Extract description
            desc_p = soup.find('p')
            description = desc_p.get_text().strip() if desc_p else ""
            
            return APIEndpoint(
                name=name,
                method=method,
                path=path,
                description=description,
                parameters=[],
                request_body=None,
                responses={"200": {"description": "Success"}},
                tags=[url.split('/')[-2] if '/' in url else "general"],
                auth_required=True
            )
            
        except Exception as e:
            logger.error(f"Error extracting endpoint from {url}: {e}")
            return None
    
    def cleanup(self):
        """Clean up WebDriver resources"""
        if self.driver:
            self.driver.quit()
            logger.info("✅ WebDriver cleaned up")

async def main():
    """Main function"""
    logger.info("=" * 60)
    logger.info("🚀 AVATHON API SCRAPER STARTING")
    logger.info("=" * 60)
    
    scraper = SeleniumAvathonScraper()
    
    try:
        # Setup WebDriver
        logger.info("🔧 PHASE 1: Setting up WebDriver...")
        if not scraper.setup_driver():
            logger.error("❌ PHASE 1 FAILED: WebDriver setup failed")
            return
        logger.info("✅ PHASE 1 COMPLETE: WebDriver ready")
        
        # Authenticate
        logger.info("🔐 PHASE 2: Authenticating with Avathon...")
        if not scraper.authenticate_with_selenium():
            logger.error("❌ PHASE 2 FAILED: Authentication failed")
            return
        logger.info("✅ PHASE 2 COMPLETE: Authentication successful")
        
        # Scrape with authenticated session
        logger.info("📚 PHASE 3: Scraping API documentation...")
        endpoints = await scraper.scrape_with_authenticated_session()
        
        if endpoints:
            # Save results
            output_file = "avathon_api_spec_selenium.json"
            logger.info(f"💾 Saving results to {output_file}...")
            with open(output_file, 'w') as f:
                json.dump([asdict(endpoint) for endpoint in endpoints], f, indent=2)
            
            logger.info("=" * 60)
            logger.info("✅ SCRAPING COMPLETE!")
            logger.info(f"📊 Successfully scraped {len(endpoints)} endpoints")
            logger.info(f"📄 Results saved to: {output_file}")
            logger.info("=" * 60)
        else:
            logger.error("❌ PHASE 3 FAILED: No endpoints were scraped")
    
    except Exception as e:
        logger.error(f"💥 FATAL ERROR: {e}", exc_info=True)
    
    finally:
        logger.info("🧹 Cleaning up WebDriver...")
        scraper.cleanup()
        logger.info("👋 Scraper finished")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())