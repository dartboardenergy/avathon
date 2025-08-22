#!/usr/bin/env python3
"""
Simple Selenium-based Avathon scraper with fixed selectors
"""

import os
import json
import time
import logging
from typing import List, Dict, Any

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import NoSuchElementException
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SimpleAvathonScraper:
    def __init__(self):
        self.username = os.getenv("AVATHON_USERNAME")
        self.password = os.getenv("AVATHON_PASSWORD")
        
        if not self.username or not self.password:
            raise ValueError("AVATHON_USERNAME and AVATHON_PASSWORD must be set in .env")
        
        self.driver = None
        
    def setup_driver(self):
        """Setup Chrome with simple options"""
        chrome_options = Options()
        # Comment out headless to see what's happening
        # chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            logger.info("✅ Chrome WebDriver initialized")
            return True
        except Exception as e:
            logger.error(f"❌ WebDriver failed: {e}")
            return False
    
    def find_login_elements(self):
        """Find login elements by analyzing all inputs on the page"""
        logger.info("🔍 Analyzing all input elements on the page...")
        
        inputs = self.driver.find_elements(By.TAG_NAME, "input")
        logger.info(f"Found {len(inputs)} input elements")
        
        username_field = None
        password_field = None
        
        for i, input_elem in enumerate(inputs):
            try:
                input_type = input_elem.get_attribute("type") or ""
                input_name = input_elem.get_attribute("name") or ""
                input_placeholder = input_elem.get_attribute("placeholder") or ""
                input_id = input_elem.get_attribute("id") or ""
                input_class = input_elem.get_attribute("class") or ""
                
                logger.info(f"Input {i+1}:")
                logger.info(f"  Type: {input_type}")
                logger.info(f"  Name: {input_name}")
                logger.info(f"  Placeholder: {input_placeholder}")
                logger.info(f"  ID: {input_id}")
                logger.info(f"  Class: {input_class}")
                
                # Check if this looks like a username/email field
                if (input_type.lower() == "email" or 
                    "email" in input_name.lower() or 
                    "email" in input_placeholder.lower() or
                    "username" in input_name.lower() or
                    "username" in input_placeholder.lower()):
                    username_field = input_elem
                    logger.info(f"  ✅ This looks like the USERNAME field!")
                
                # Check if this looks like a password field
                if input_type.lower() == "password":
                    password_field = input_elem
                    logger.info(f"  ✅ This looks like the PASSWORD field!")
                
            except Exception as e:
                logger.error(f"Error analyzing input {i+1}: {e}")
        
        return username_field, password_field
    
    def authenticate(self):
        """Try to authenticate with found credentials"""
        try:
            logger.info("🚀 Starting authentication...")
            logger.info(f"Username: {self.username}")
            logger.info(f"Password: {'*' * len(self.password)}")
            
            # Navigate to login page
            logger.info("📍 Navigating to Avathon...")
            self.driver.get("https://renewables.apm.avathon.com")
            
            # Wait for page to load
            logger.info("⏳ Waiting for page to load...")
            time.sleep(5)
            
            current_url = self.driver.current_url
            page_title = self.driver.title
            logger.info(f"📍 Current URL: {current_url}")
            logger.info(f"📄 Page title: {page_title}")
            
            # Find login elements
            username_field, password_field = self.find_login_elements()
            
            if not username_field:
                logger.error("❌ No username field found")
                return False
                
            if not password_field:
                logger.error("❌ No password field found")
                return False
            
            # Fill in credentials
            logger.info("📝 Filling in credentials...")
            username_field.clear()
            username_field.send_keys(self.username)
            logger.info("✅ Username entered")
            
            password_field.clear()
            password_field.send_keys(self.password)
            logger.info("✅ Password entered")
            
            # Look for submit button
            logger.info("🔍 Looking for submit button...")
            buttons = self.driver.find_elements(By.TAG_NAME, "button")
            submit_button = None
            
            for i, button in enumerate(buttons):
                try:
                    button_text = button.text.strip()
                    button_type = button.get_attribute("type") or ""
                    button_class = button.get_attribute("class") or ""
                    
                    logger.info(f"Button {i+1}:")
                    logger.info(f"  Text: '{button_text}'")
                    logger.info(f"  Type: {button_type}")
                    logger.info(f"  Class: {button_class}")
                    
                    # Look for submit-like buttons
                    if (button_type.lower() == "submit" or
                        "login" in button_text.lower() or
                        "sign in" in button_text.lower() or
                        "continue" in button_text.lower() or
                        "submit" in button_class.lower()):
                        submit_button = button
                        logger.info(f"  ✅ This looks like the SUBMIT button!")
                        break
                        
                except Exception as e:
                    logger.error(f"Error analyzing button {i+1}: {e}")
            
            if not submit_button:
                logger.error("❌ No submit button found")
                return False
            
            # Submit the form
            logger.info("🚀 Clicking submit button...")
            submit_button.click()
            
            # Wait for redirect
            logger.info("⏳ Waiting for authentication result...")
            time.sleep(5)
            
            new_url = self.driver.current_url
            logger.info(f"📍 New URL after login: {new_url}")
            
            # Check if we successfully logged in (should redirect to storage/overview)
            if "storage" in new_url or "dashboard" in new_url or "overview" in new_url:
                logger.info("✅ Authentication successful! Redirected to dashboard")
                return True
            elif new_url != current_url and "auth" not in new_url:
                logger.info("✅ Authentication appears successful - redirected to new page")
                return True
            else:
                logger.error("❌ Authentication failed - still on login page")
                return False
                
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return False
    
    def navigate_to_api_docs(self):
        """Navigate to API documentation via profile dropdown"""
        try:
            logger.info("🔍 Looking for profile dropdown to access API docs...")
            
            # Look for profile/user icon (usually a circle or user icon in top right)
            profile_selectors = [
                "button[aria-label*='profile']",
                "button[aria-label*='Profile']",
                "button[aria-label*='user']", 
                "button[aria-label*='User']",
                "[data-testid*='profile']",
                "[data-testid*='user']",
                ".profile-button",
                ".user-menu",
                # Look for elements that might be in top-right area
                "div[class*='profile']",
                "button[class*='profile']"
            ]
            
            profile_button = None
            for selector in profile_selectors:
                try:
                    profile_button = self.driver.find_element(By.CSS_SELECTOR, selector)
                    logger.info(f"✅ Found profile button with selector: {selector}")
                    break
                except NoSuchElementException:
                    continue
            
            if not profile_button:
                # Let's look for ANY clickable element in the top right that might be the profile
                logger.info("🔍 Profile button not found with standard selectors. Analyzing all clickable elements...")
                
                # Try looking for div elements that might be clickable (profile avatars are often divs)
                clickable_elements = (
                    self.driver.find_elements(By.TAG_NAME, "button") + 
                    self.driver.find_elements(By.TAG_NAME, "div") +
                    self.driver.find_elements(By.TAG_NAME, "a")
                )
                
                logger.info(f"Found {len(clickable_elements)} clickable elements to analyze")
                
                for i, element in enumerate(clickable_elements):
                    try:
                        element_class = element.get_attribute("class") or ""
                        element_aria_label = element.get_attribute("aria-label") or ""
                        element_text = element.text.strip()
                        element_tag = element.tag_name
                        element_role = element.get_attribute("role") or ""
                        
                        # Log first 10 elements for debugging
                        if i < 10:
                            logger.info(f"Element {i+1} ({element_tag}):")
                            logger.info(f"  Class: {element_class[:100]}...")
                            logger.info(f"  Text: '{element_text}'")
                            logger.info(f"  Role: {element_role}")
                            logger.info(f"  Aria-label: {element_aria_label}")
                        
                        # Look for profile-like characteristics
                        profile_indicators = [
                            "profile" in element_class.lower(),
                            "user" in element_class.lower(), 
                            "avatar" in element_class.lower(),
                            "profile" in element_aria_label.lower(),
                            "user" in element_aria_label.lower(),
                            element_role == "button" and not element_text,  # Empty button (likely an icon)
                            # Look for elements that might be in header/navbar area
                            "header" in element_class.lower(),
                            "nav" in element_class.lower()
                        ]
                        
                        if any(profile_indicators):
                            # Check if this element is likely to be clickable
                            is_clickable = (
                                element_tag == "button" or 
                                element_role == "button" or
                                "cursor-pointer" in element_class or
                                "clickable" in element_class.lower()
                            )
                            
                            if is_clickable:
                                profile_button = element
                                logger.info(f"✅ Found potential profile element: {element_tag} with class: {element_class[:50]}...")
                                break
                                
                    except Exception as e:
                        logger.debug(f"Error analyzing element {i}: {e}")
                        continue
            
            if not profile_button:
                logger.warning("⚠️ Could not find profile dropdown button with heuristics...")
                logger.info("🎯 Trying to find elements with specific profile-related characteristics...")
                
                # Last attempt - look for any element that might contain user info or be in top-right
                all_elements = self.driver.find_elements(By.XPATH, "//*[contains(text(), 'Bhasi') or contains(text(), 'bhasi') or contains(@class, 'avatar') or contains(@class, 'user')]")
                
                for element in all_elements:
                    try:
                        # Check if this element or its parent is clickable
                        if element.is_displayed() and element.is_enabled():
                            logger.info(f"🎯 Trying element with user info: {element.tag_name} - {element.text}")
                            profile_button = element
                            break
                    except:
                        continue
                
                if not profile_button:
                    logger.error("❌ Could not find profile dropdown button. Trying direct navigation...")
                    return self.test_direct_api_docs_access()
            
            # Click the profile button to open dropdown
            logger.info("👤 Clicking profile button to open dropdown...")
            profile_button.click()
            time.sleep(2)  # Wait for dropdown to appear
            
            # Look for "API Documentation" link in the dropdown
            api_doc_selectors = [
                "a[href*='docs']",
                "[data-testid*='api']",
                "[data-testid*='docs']"
            ]
            
            api_doc_link = None
            # First try to find by text content
            links = self.driver.find_elements(By.TAG_NAME, "a")
            for link in links:
                link_text = link.text.strip()
                if "api" in link_text.lower() and "documentation" in link_text.lower():
                    api_doc_link = link
                    logger.info(f"✅ Found API Documentation link: {link_text}")
                    break
            
            if not api_doc_link:
                logger.error("❌ Could not find API Documentation link in dropdown")
                return False
            
            # Click the API Documentation link
            logger.info("📚 Clicking API Documentation link...")
            api_doc_link.click()
            time.sleep(3)
            
            return True
            
        except Exception as e:
            logger.error(f"Error navigating to API docs: {e}")
            return False
    
    def test_direct_api_docs_access(self):
        """Test direct access to API docs with existing session"""
        try:
            logger.info("🌐 Testing direct API documentation access...")
            
            # Get all cookies from the authenticated session
            cookies = self.driver.get_cookies()
            logger.info(f"📋 Session has {len(cookies)} cookies")
            for cookie in cookies:
                logger.info(f"  Cookie: {cookie['name']} = {cookie['value'][:20]}...")
            
            # Try to navigate to docs directly
            docs_url = "https://docs.apm.sparkcognition.com/reference/overview-api"
            logger.info(f"📍 Navigating directly to: {docs_url}")
            self.driver.get(docs_url)
            
            time.sleep(3)
            
            final_url = self.driver.current_url
            page_title = self.driver.title
            page_source_snippet = self.driver.page_source[:500]
            
            logger.info(f"📍 Final URL: {final_url}")
            logger.info(f"📄 Page title: {page_title}")
            logger.info(f"📄 Page content preview: {page_source_snippet}")
            
            # Check if we can access the docs (not password protected)
            if "password" not in self.driver.page_source.lower():
                logger.info("✅ API documentation is accessible!")
                
                # Save the page source for analysis
                with open("api_docs_page.html", "w") as f:
                    f.write(self.driver.page_source)
                logger.info("💾 Saved API docs page to api_docs_page.html")
                
                return True
            else:
                logger.error("❌ API documentation is still password protected")
                return False
                
        except Exception as e:
            logger.error(f"Error accessing API docs: {e}")
            return False
    
    def cleanup(self):
        """Clean up resources"""
        if self.driver:
            self.driver.quit()
            logger.info("🧹 WebDriver cleaned up")

def main():
    logger.info("🚀 Starting Simple Avathon Scraper...")
    
    scraper = SimpleAvathonScraper()
    
    try:
        # Setup browser
        if not scraper.setup_driver():
            return
        
        # Authenticate
        if not scraper.authenticate():
            return
        
        # Navigate to API documentation
        if scraper.navigate_to_api_docs():
            logger.info("🎉 SUCCESS: Navigated to API documentation!")
            
            # Now test if we can access it
            if scraper.test_api_docs_access():
                logger.info("🎉 SUCCESS: We can access the API documentation!")
            else:
                logger.error("❌ FAILED: Could not access API documentation")
        else:
            logger.error("❌ FAILED: Could not navigate to API documentation")
            
    finally:
        scraper.cleanup()

if __name__ == "__main__":
    main()