#!/usr/bin/env python3
"""
Proper ReadMe.io Extractor - Uses stable attributes instead of hashed CSS classes
Based on ReadMe.io's OpenAPI → DOM transformation patterns
"""

import json
import os
import time
import re
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import json as _json


class ProperReadMeExtractor:
    """Proper ReadMe.io extraction using stable DOM patterns"""
    
    def __init__(self, target_endpoint: str):
        self.target_endpoint = target_endpoint
        self.base_url = "https://docs.apm.sparkcognition.com"
        self.driver = None
        # Feature flag: expand Responses tabs (can cause flakiness in some environments)
        self.expand_responses = False
        # Optional output directory for saving results (used by batch runner)
        self.output_dir: str | None = None
        
        # Authentication cookies (read fresh values from environment if provided)
        env_sid = os.environ.get('README_CONNECT_SID') or os.environ.get('CONNECT_SID')
        env_cf  = os.environ.get('README_CF_BM') or os.environ.get('CF_BM') or os.environ.get('__CF_BM')
        self.cookies = {
            'connect.sid': env_sid or 's%3A05L4a8drF65NflPjahqbtCgn1QT3G7Ru.BaApdohf6tO%2FpmLmImgWILalJFdBh5KHYQwAUqG8Imw',
            '__cf_bm': env_cf or 'vZKhA9UxyWORIhSV3d5.T7cPeAolwgr_6nel5mCXe48-1755893974-1.0.1.1-dUlqeWOgtc4H5pALXgfpz.FZXyxf7qNM7ilir4wm1CsEnz4lnMV38hV1jpMYxC_bTCm0o4Wh_AKuOZZsdgdc_58sNMjrshKFpKPRh7Smaw0'
        }
    
    def setup_driver(self, headless: bool = True):
        """Setup Chrome WebDriver"""
        print(f"🔧 Setting up WebDriver (headless={headless})")
        
        chrome_options = Options()
        if headless:
            chrome_options.add_argument('--headless')
        
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36')
        
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.implicitly_wait(15)
            self.driver.set_page_load_timeout(30)
            print("✅ WebDriver started successfully")
            return True
        except Exception as e:
            print(f"❌ Failed to start WebDriver: {e}")
            return False
    
    def setup_session(self):
        """Navigate and authenticate"""
        print("🔗 Setting up authenticated session")
        
        try:
            self.driver.get(self.base_url)
            
            for name, value in self.cookies.items():
                self.driver.add_cookie({
                    'name': name,
                    'value': value,
                    'domain': '.sparkcognition.com'
                })
            
            self.driver.refresh()
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            print("✅ Session established")
            return True
            
        except Exception as e:
            print(f"❌ Failed to setup session: {e}")
            return False
    
    def navigate_to_target(self):
        """Navigate to target endpoint"""
        full_url = urljoin(self.base_url, self.target_endpoint)
        print(f"🎯 Navigating to: {full_url}")
        
        try:
            self.driver.get(full_url)
            
            # Wait for main content
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.TAG_NAME, "main"))
            )
            
            # Enhanced wait for ReadMe.io content to fully render
            print("⏳ Waiting for ReadMe.io content to render...")
            self._wait_for_reademe_content()
            # Explicitly expand Responses 200/400/401 to force schema render (opt-in)
            if self.expand_responses:
                print("⏳ Expanding 200/400/401 response sections...")
                self._expand_response_sections(["200", "400", "401"])            
            
            print("✅ Successfully navigated to target endpoint")
            return True
            
        except Exception as e:
            print(f"❌ Error navigating: {e}")
            return False
    
    def _wait_for_reademe_content(self):
        """Wait for ReadMe.io content with an emphasis on 200 Response body readiness."""
        
        max_attempts = 10
        response_ready = False
        baseline_rb = -1
        
        for attempt in range(max_attempts):
            print(f"    🔍 Checking ReadMe.io content (attempt {attempt + 1}/{max_attempts})")
            try:
                # General probes
                query_labels = self.driver.find_elements(By.CSS_SELECTOR, 'label[for^="query-"]')
                object_labels = self.driver.find_elements(By.CSS_SELECTOR, 'label[for^="object-"]')
                response_spans = self.driver.find_elements(By.CSS_SELECTOR, 'span[class*="Param-name"]')
                
                query_count = len(query_labels)
                object_count = len(object_labels)
                span_count = len(response_spans)
                total_params = query_count + object_count + span_count
                
                print(f"      • Query parameters: {query_count}")
                print(f"      • Object properties: {object_count}")
                print(f"      • Response spans: {span_count}")
                print(f"      • Total parameter elements: {total_params}")
                
                # Proactively expand 200/Response body to surface nested labels
                try:
                    self._expand_examples_and_200()
                    self._expand_response_body_deep()
                except Exception:
                    pass
                
                # Focused probe: Response body label count
                rb_count = 0
                try:
                    rb_elems = self.driver.find_elements(
                        By.XPATH,
                        "//*[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'response body')]/ancestor::*[self::div or self::section][1]"
                    )
                    if rb_elems:
                        rb_count = len(rb_elems[0].find_elements(By.CSS_SELECTOR, 'label[for^="object-"]'))
                except Exception:
                    rb_count = 0
                print(f"      • Response-body object labels: {rb_count}")
                
                # Success criteria: Response body labels present and growing or over threshold
                if rb_count > 0 and (baseline_rb == -1 or rb_count >= baseline_rb):
                    baseline_rb = max(baseline_rb, rb_count)
                    if rb_count >= 20 or (rb_count >= 5 and attempt >= 2):
                        print("    ✅ Response body appears loaded")
                        response_ready = True
                        break
                
                # Fallback success: large overall parameter surface
                if total_params >= 20 and attempt >= 1:
                    print("    ✅ ReadMe.io content appears fully loaded (fallback)")
                    response_ready = True
                    break
            except Exception as e:
                print(f"      ❌ Error checking content: {e}")
            
            print("    ⏳ Waiting 1.5 more seconds...")
            time.sleep(1.5)
        
        if not response_ready:
            print("    ⚠️ ReadMe.io 'Response body' may not be fully loaded")

    def _expand_response_sections(self, ensure_codes: Optional[List[str]] = None):
        """Expand Responses section and specific status codes to trigger full render.
        
        Attempts to click common toggle elements for the overall Responses block and
        the given status code tabs/accordions (default: ["200", "400", "401"]).
        Also performs light scrolling and waits briefly to allow DOM updates.
        """
        try:
            ensure_codes = ensure_codes or ["200", "400", "401"]
            print(f"    🔓 Expanding Responses sections for codes: {ensure_codes}")
            # First, try to open the overall Responses section if it's collapsible
            responses_selectors = [
                "//button[contains(., 'Responses') or contains(., 'responses')]",
                "//div[@role='tab' and (contains(., 'Responses') or contains(., 'responses'))]",
                "//summary[contains(., 'Responses') or contains(., 'responses')]",
            ]
            for sel in responses_selectors:
                try:
                    elems = self.driver.find_elements(By.XPATH, sel)
                    for el in elems[:3]:
                        try:
                            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", el)
                            time.sleep(0.2)
                            aria_expanded = el.get_attribute('aria-expanded')
                            if aria_expanded == 'false' or aria_expanded is None:
                                el.click()
                                time.sleep(0.3)
                        except Exception:
                            pass
                except Exception:
                    pass
            # Now, expand specific status code sections
            for code in ensure_codes:
                code_selectors = [
                    f"//button[contains(., '{code}')]",
                    f"//div[@role='tab' and contains(., '{code}')]",
                    f"//summary[contains(., '{code}')]",
                    f"//*[contains(@class,'CodeTabs') or contains(@class,'tabs')][.//*[contains(text(),'{code}')]]//*[contains(text(),'{code}')]",
                ]
                expanded = False
                for sel in code_selectors:
                    try:
                        elems = self.driver.find_elements(By.XPATH, sel)
                        for el in elems[:3]:
                            try:
                                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", el)
                                time.sleep(0.2)
                                aria_selected = el.get_attribute('aria-selected')
                                aria_expanded = el.get_attribute('aria-expanded')
                                if aria_selected != 'true' and aria_expanded != 'true':
                                    el.click()
                                    time.sleep(0.35)
                                expanded = True
                                break
                            except Exception:
                                continue
                    except Exception:
                        continue
                    if expanded:
                        break
            # Light scroll to encourage lazy render
            self.driver.execute_script('window.scrollBy(0, 200);')
            time.sleep(0.2)
            self.driver.execute_script('window.scrollBy(0, -200);')
            time.sleep(0.2)
            # Brief settling time and a quick probe for new labels
            time.sleep(0.5)
            labels = self.driver.find_elements(By.CSS_SELECTOR, 'label[for^="object-"]')
            print(f"    🏷️ object-* labels after expansion: {len(labels)}")
        except Exception as e:
            print(f"    ⚠️ Failed to expand responses: {e}")
    
    def extract_complete_api_spec(self) -> Dict[str, Any]:
        """Extract complete API specification using stable DOM patterns"""
        print("🔍 PROPER README.IO EXTRACTION")
        print("Using stable attributes, avoiding hashed CSS classes")
        
        page_source = self.driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')
        
        # Extract endpoint metadata (title, method, URL, description)
        endpoint_metadata = self._extract_endpoint_metadata(soup)
        
        # Try to expand 200 + Examples to surface example JSON before parsing
        try:
            self._expand_examples_and_200()
            time.sleep(0.5)
            page_source = self.driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
        except Exception:
            pass

        # Extract query parameters using stable for= attributes
        query_parameters = self._extract_query_parameters(soup)
        
        # Extract response schemas using stable patterns
        response_schemas = self._extract_response_schemas(soup)
        
        return {
            'endpoint': self.target_endpoint,
            'extraction_method': 'proper_readmeio',
            'endpoint_metadata': endpoint_metadata,
            'query_parameters': query_parameters,
            'response_schemas': response_schemas,
            'parameters_found': len(query_parameters),
            'response_schemas_found': len(response_schemas)
        }

    def _expand_examples_and_200(self):
        """Best-effort: select the 200 response tab and open Examples/Response code.

        This increases the chance that example JSON is present in the DOM for fallback parsing.
        """
        d = self.driver
        try:
            # Select 200 tab if present
            selectors = [
                "//div[@role='tab' and contains(normalize-space(.), '200')]",
                "//button[contains(normalize-space(.), '200')]",
                "//summary[contains(normalize-space(.), '200')]",
            ]
            for sel in selectors:
                try:
                    els = d.find_elements(By.XPATH, sel)
                    if els:
                        d.execute_script("arguments[0].scrollIntoView({block: 'center'});", els[0])
                        time.sleep(0.2)
                        els[0].click()
                        time.sleep(0.3)
                        break
                except Exception:
                    continue

            # Click Examples/Example toggle/buttons
            ex_selectors = [
                "//*[contains(normalize-space(.), 'Examples')]",
                "//*[contains(normalize-space(.), 'Example')]",
                "//button[contains(., 'Example')]",
                "//a[contains(., 'Example')]",
            ]
            for sel in ex_selectors:
                try:
                    els = d.find_elements(By.XPATH, sel)
                    for el in els[:2]:
                        d.execute_script("arguments[0].scrollIntoView({block: 'center'});", el)
                        time.sleep(0.1)
                        el.click()
                        time.sleep(0.2)
                except Exception:
                    continue
            # Aggressively scroll the response area to force lazy rendering
            try:
                # Try to find a container near "Response body"
                rb = None
                for xp in [
                    "//*[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'), 'response body')]/ancestor::*[self::section or self::div][1]",
                    "//*[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'), 'responses')]/ancestor::*[self::section or self::div][1]"
                ]:
                    try:
                        rb = d.find_element(By.XPATH, xp)
                        if rb:
                            break
                    except Exception:
                        continue
                if rb is not None:
                    d.execute_script("arguments[0].scrollTop = 0;", rb)
                    time.sleep(0.2)
                    for _ in range(6):
                        d.execute_script("arguments[0].scrollTop = arguments[0].scrollTop + 600;", rb)
                        time.sleep(0.15)
                else:
                    # Fallback to window scroll
                    for _ in range(8):
                        d.execute_script('window.scrollBy(0, 600);')
                        time.sleep(0.15)
            except Exception:
                pass
        except Exception:
            pass
    
    def _expand_response_body_deep(self):
        """Deeply expand the 200 Response body block: select 200, open details/summary, and scroll."""
        d = self.driver
        try:
            # Select 200 tab
            for sel in [
                "//div[@role='tab' and contains(normalize-space(.), '200')]",
                "//button[contains(normalize-space(.), '200')]",
                "//summary[contains(normalize-space(.), '200')]",
            ]:
                try:
                    els = d.find_elements(By.XPATH, sel)
                    if els:
                        d.execute_script("arguments[0].scrollIntoView({block: 'center'});", els[0])
                        time.sleep(0.15)
                        els[0].click()
                        time.sleep(0.2)
                        break
                except Exception:
                    continue
            # Expand nested details within the response area
            details = d.find_elements(By.XPATH, "//*[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'response body')]/ancestor::*[self::div or self::section][1]//details")
            for det in details[:80]:
                try:
                    d.execute_script("arguments[0].open = true;", det)
                except Exception:
                    pass
            # Click summaries to reveal hidden content
            summaries = d.find_elements(By.XPATH, "//*[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'response body')]/ancestor::*[self::div or self::section][1]//summary")
            for sm in summaries[:120]:
                try:
                    aria = sm.get_attribute('aria-expanded')
                    if aria != 'true':
                        d.execute_script("arguments[0].scrollIntoView({block: 'center'});", sm)
                        time.sleep(0.03)
                        sm.click()
                        time.sleep(0.03)
                except Exception:
                    continue
            # Try to scroll the specific Response body container repeatedly
            try:
                rb = d.find_element(By.XPATH, "//*[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'response body')]/ancestor::*[self::div or self::section][1]")
                d.execute_script("arguments[0].scrollTop = 0;", rb)
                for _ in range(40):
                    d.execute_script("arguments[0].scrollTop = arguments[0].scrollTop + 800;", rb)
                    time.sleep(0.05)
            except Exception:
                pass
            # Global window scroll as a fallback
            for _ in range(40):
                d.execute_script('window.scrollBy(0, 800);')
                time.sleep(0.05)
        except Exception:
            pass
    
    def _extract_endpoint_metadata(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract endpoint title, method, URL, and description"""
        print("  📖 Extracting Endpoint Metadata")
        
        metadata = {
            'title': '',
            'method': '',
            'url': '',
            'description': ''
        }
        
        # Extract title - look for the main endpoint title
        # ReadMe.io often has the endpoint name as the primary heading
        title_candidates = soup.find_all(['h1', 'h2', 'h3'])
        for candidate in title_candidates:
            text = candidate.get_text(strip=True)
            # Look for titles that seem like endpoint names (not generic guide titles)
            if text and len(text) < 50 and not any(skip in text.lower() for skip in ['getting started', 'guide', 'tutorial', 'overview']):
                metadata['title'] = text
                break
        
        # Extract method and URL (look for method badges and code blocks)
        # ReadMe.io typically shows "GET https://..." in a code block or badge
        method_indicators = soup.find_all(string=re.compile(r'(GET|POST|PUT|DELETE|PATCH)\s+https?://'))
        if method_indicators:
            method_url_text = method_indicators[0].strip()
            # Parse "GET https://example.com/api/endpoint"
            parts = method_url_text.split(' ', 1)
            if len(parts) == 2:
                metadata['method'] = parts[0]
                metadata['url'] = parts[1]
        
        # Alternative: Look for method in badges or spans
        if not metadata['method']:
            method_badges = soup.find_all(['span', 'div', 'code'], string=re.compile(r'^(GET|POST|PUT|DELETE|PATCH)$'))
            if method_badges:
                metadata['method'] = method_badges[0].get_text(strip=True)
        
        # Look for URL in code blocks or specific elements
        if not metadata['url']:
            url_candidates = soup.find_all(['code', 'pre'], string=re.compile(r'https?://.*'))
            if url_candidates:
                url_text = url_candidates[0].get_text(strip=True)
                # Extract URL from the text
                url_match = re.search(r'https?://[^\s]+', url_text)
                if url_match:
                    metadata['url'] = url_match.group()

        # Fallback: Parse method and URL from code/pre snippets if still missing
        if not metadata['method'] or not metadata['url']:
            code_blocks = soup.find_all(['code', 'pre'])
            for block in code_blocks:
                text = block.get_text(" ", strip=True)
                if not text:
                    continue
                m = re.search(r'\b(GET|POST|PUT|DELETE|PATCH)\b', text)
                u = re.search(r'https?://[^\s\'"\)]+', text)
                if m and (metadata['method'] == ''):
                    metadata['method'] = m.group(1)
                if u and (metadata['url'] == ''):
                    metadata['url'] = u.group(0)
                if metadata['method'] and metadata['url']:
                    break
        
        # Extract description using DOM structure, not hardcoded keywords
        # Look for descriptive text in main content areas
        desc_candidates = soup.find_all(['p', 'div'], string=True)
        for candidate in desc_candidates:
            text = candidate.get_text(strip=True)
            # Look for descriptive sentences (avoid overfitted English keywords)
            if (len(text) > 20 and 
                '.' in text and  # Sentences have periods
                not any(skip in text.lower() for skip in ['parameter', 'required', 'optional', 'example', 'string', 'integer', 'object'])):
                metadata['description'] = text[:300]
                break
        
        print(f"    📖 Title: {metadata['title']}")
        print(f"    📖 Method: {metadata['method']} {metadata['url']}")
        print(f"    📖 Description: {metadata['description'][:50]}...")
        
        return metadata
    
    def _extract_query_parameters(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Extract query parameters using for='query-*' pattern"""
        print("  📋 Extracting Query Parameters (using for='query-*' pattern)")
        
        parameters = []
        
        # Find all labels with for="query-*" attributes
        query_labels = soup.find_all('label', attrs={'for': re.compile(r'^query-')})
        
        print(f"    🔍 Found {len(query_labels)} query parameter labels")
        
        for label in query_labels:
            param_name = label.get_text(strip=True)
            for_attr = label.get('for', '')
            
            # Extract parameter info
            param_info = self._extract_parameter_details(label, param_name, 'query')
            
            if param_info:
                parameters.append(param_info)
                req_status = "required" if param_info['required'] else "optional"
                print(f"    ✅ {param_name} ({param_info['type']}) - {req_status}")
        
        print(f"  📊 Total query parameters: {len(parameters)}")
        return parameters
    
    def _extract_response_schemas(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract response schemas using stable patterns with proper status code separation"""
        print("  📊 Extracting Response Schemas (using stable DOM patterns)")
        
        response_schemas = {}
        
        # Aggressively expand 200 Response body to surface nested labels first
        try:
            self._expand_response_body_deep()
            time.sleep(0.3)
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
        except Exception:
            pass
        
        # Strategy 1: Look for response spans (root level properties)
        response_spans = soup.find_all('span', class_=lambda x: x and 'Param-name' in str(x) if x else False)
        
        # Strategy 2: Look for object labels with for="object-*"
        object_labels = soup.find_all('label', attrs={'for': re.compile(r'^object-')})
        
        print(f"    🔍 Found {len(response_spans)} response span elements")
        print(f"    🔍 Found {len(object_labels)} object property labels")
        
        # Separate properties by likely status codes
        success_properties = []  # 200 response
        error_properties = []    # 400/401 responses
        
        # Process spans - but only include those that will have nested properties
        # First, discover what containers actually exist based on object-* paths
        temp_properties = []
        for label in object_labels:
            name = label.get_text(strip=True)
            for_attr = label.get('for', '')
            temp_properties.append({'name': name, 'path': for_attr})
        
        actual_containers = self._discover_containers(temp_properties)
        
        # Only include spans that correspond to actual containers with properties
        for span in response_spans:
            prop_name = span.get_text(strip=True)
            prop_info = self._extract_parameter_details(span, prop_name, 'response')
            if prop_info:
                # Only add if this span corresponds to a container with actual nested properties
                if prop_name in actual_containers and len(actual_containers[prop_name]) > 0:
                    success_properties.append(prop_info)
                # OR if it's not trying to be a container (no nested properties expected)
                elif prop_name not in actual_containers:
                    # This might be a simple root property, not a container
                    # For now, skip standalone spans - they're usually containers without properties
                    pass
        
        # Process object labels (nested properties) - separate by status code context
        for label in object_labels:
            prop_name = label.get_text(strip=True)
            for_attr = label.get('for', '')
            
            # Check if this looks like an error response property
            is_error_property = self._is_error_response_property(label, prop_name, for_attr)
            
            prop_info = self._extract_parameter_details(label, prop_name, 'response')
            if prop_info:
                # Add path information from for attribute
                prop_info['path'] = for_attr
                
                if is_error_property:
                    error_properties.append(prop_info)
                else:
                    success_properties.append(prop_info)

        # Clean structural inference: map span-only properties into the nearest container
        # in document order (e.g., data or query blocks) when no object-* label exists.
        self._map_span_properties_to_nearest_container(soup, success_properties)
        
        # Remove duplicates within each category
        success_properties = self._deduplicate_properties(success_properties)
        error_properties = self._deduplicate_properties(error_properties)
        
        # Build schemas for different status codes
        if success_properties:
            schema_200 = self._build_nested_schema(success_properties)
            response_schemas['200'] = schema_200
            print(f"    ✅ Built 200 schema with {len(success_properties)} properties")
        
        if error_properties:
            # Assume error properties are for 400/401 (they often share structure)
            schema_400 = self._build_nested_schema(error_properties)
            response_schemas['400'] = schema_400
            response_schemas['401'] = schema_400  # Often same structure
            print(f"    ✅ Built 400/401 schemas with {len(error_properties)} properties")
        
        # Print schema summaries
        for status_code, schema in response_schemas.items():
            print(f"    📄 Schema {status_code}:")
            self._print_schema_summary(schema, indent="      ")
        
        print(f"  📊 Total response schemas: {len(response_schemas)}")
        # Fallback: if no 200 schema was produced, attempt to synthesize from example JSON
        if '200' not in response_schemas:
            try:
                example_schema = self._synthesize_200_from_example_json(soup)
                if example_schema:
                    response_schemas['200'] = example_schema
                    print("    🧩 Added 200 schema from example JSON fallback")
            except Exception:
                pass
        # Fallback 2: Some GPM pages have a flat "Response body" section with Param-name spans
        if '200' not in response_schemas:
            try:
                rb_schema = self._synthesize_200_from_response_body_spans(soup)
                if rb_schema:
                    response_schemas['200'] = rb_schema
                    print("    🧩 Added 200 schema from 'Response body' spans")
            except Exception:
                pass
        return response_schemas

    # ------------------------
    # Example JSON → Schema fallback
    # ------------------------
    def _synthesize_200_from_example_json(self, soup: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """If no label/span-driven 200 is found, parse example JSON code and build a schema.

        Looks for <pre>/<code> blocks that appear to contain JSON (object or array).
        Selects the largest parseable JSON snippet and converts it into a simple schema.
        """
        candidates = []
        for tag in soup.find_all(['code', 'pre']):
            txt = tag.get_text("\n", strip=True)
            if txt and ('{' in txt or '[' in txt):
                candidates.append(txt)

        best_json = None
        best_len = 0
        for raw in candidates:
            parsed = self._extract_json_from_text(raw)
            if parsed is not None:
                length = len(_json.dumps(parsed))
                if length > best_len:
                    best_len = length
                    best_json = parsed

        if best_json is None:
            return None

        return self._schema_from_json_value(best_json)

    def _extract_json_from_text(self, text: str) -> Optional[Any]:
        """Best-effort JSON extraction from a code block text."""
        s = text.strip()
        # Try direct parse
        try:
            return _json.loads(s)
        except Exception:
            pass
        # Heuristic: find first '{' or '[' and last matching bracket
        try:
            start_obj = s.find('{')
            start_arr = s.find('[')
            start = -1
            if start_obj != -1 and start_arr != -1:
                start = min(start_obj, start_arr)
            else:
                start = max(start_obj, start_arr)
            if start == -1:
                return None
            # Choose closing bracket by type
            close = '}' if s[start] == '{' else ']'
            end = s.rfind(close)
            if end == -1:
                return None
            snippet = s[start:end+1]
            return _json.loads(snippet)
        except Exception:
            return None

    def _schema_from_json_value(self, value: Any) -> Dict[str, Any]:
        """Convert a JSON value (object/array/scalar) into a schema dict."""
        def from_val(v: Any) -> Dict[str, Any]:
            if isinstance(v, dict):
                props = {k: from_val(v[k]) for k in v.keys()}
                return {"type": "object", "properties": props}
            if isinstance(v, list):
                # unify item type if possible; otherwise use anyOf-like simplification
                if not v:
                    return {"type": "array", "items": {"type": "object", "properties": {}}}
                item_schema = from_val(v[0])
                return {"type": "array", "items": item_schema}
            if isinstance(v, bool):
                return {"type": "boolean"}
            if isinstance(v, int):
                return {"type": "integer"}
            if isinstance(v, float):
                return {"type": "number"}
            if v is None:
                return {"type": "string"}
            return {"type": "string"}

        schema = from_val(value)
        # Normalize to our top-level shape with description
        if schema.get('type') == 'object':
            return {"type": "object", "properties": schema.get('properties', {}), "description": "Response schema (from example)"}
        if schema.get('type') == 'array':
            return {"type": "array", "items": schema.get('items', {"type": "object", "properties": {}}), "description": "Response schema (from example)"}
        # Scalar fallback
        return {"type": schema.get('type', 'string'), "description": "Response schema (from example)"}

    def _synthesize_200_from_response_body_spans(self, soup: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """Build a 200 schema from a 'Response body' block (GPM-style pages).

        Reuses the same path-based unnesting logic we use for data/query: parse
        label[for="object-*"] paths under the Response body and construct nested
        objects/arrays accordingly. If no labels are present, fall back to flat
        Param-name spans.
        """
        # 1) Locate a Response body container
        rb_block = None
        for tag in soup.find_all(["h2", "h3", "h4", "div", "section", "article" ]):
            txt = (tag.get_text(" ", strip=True) or "").lower()
            if "response body" in txt:
                blk = tag
                for _ in range(2):
                    if blk.parent:
                        blk = blk.parent
                rb_block = blk
                break
        if rb_block is None:
            return None

        # 2) Collect labels inside the Response body block
        labels = rb_block.find_all('label', attrs={'for': re.compile(r'^object-')})
        if labels:
            # Determine endpoint key to strip from paths
            endpoint_key = self.target_endpoint.strip('/').split('/')[-1] or 'endpoint'

            # Determine if root is an array from first label path
            root_is_array = False
            for lbl in labels:
                parts = (lbl.get('for', '') or '').replace('object-', '').split('_')
                if len(parts) >= 2:
                    # parts[0] should be endpoint key or method token; find first digit index
                    tokens = parts[1:] if parts[0] == endpoint_key else parts
                    if tokens and tokens[0].isdigit():
                        root_is_array = True
                        break

            # Prepare nested props builder (adapted from _build_data_schema)
            def add_to(target_props: Dict[str, Any], tokens: List[str], leaf: Dict[str, Any]):
                idx = 0
                cur = target_props
                while idx < len(tokens):
                    if tokens[idx].isdigit():
                        idx += 1
                        continue
                    name_parts = []
                    while idx < len(tokens) and not tokens[idx].isdigit():
                        name_parts.append(tokens[idx])
                        idx += 1
                    name = '_'.join(name_parts) if name_parts else leaf['name']
                    if idx < len(tokens) and tokens[idx].isdigit():
                        if name not in cur:
                            cur[name] = { 'type': 'array', 'items': { 'type': 'object', 'properties': {} } }
                        idx += 1
                        cur = cur[name]['items']['properties']
                        continue
                    # Leaf
                    cur[name] = { 'type': leaf['type'], 'description': leaf['description'] }
                    return

            root_props: Dict[str, Any] = {}
            for lbl in labels:
                name = lbl.get_text(strip=True)
                info = self._extract_parameter_details(lbl, name, 'response')
                if not info:
                    continue
                path = lbl.get('for', '')
                parts = path.replace('object-', '').split('_') if path else []
                # Strip endpoint key if present as first token
                if parts and parts[0] == endpoint_key:
                    parts = parts[1:]
                if not parts:
                    # place at root
                    root_props[info['name']] = { 'type': info['type'], 'description': info['description'] }
                else:
                    add_to(root_props, parts, info)

            if root_props:
                if root_is_array:
                    return { 'type': 'array', 'items': { 'type': 'object', 'properties': root_props }, 'description': 'Response schema (from Response body)' }
                else:
                    return { 'type': 'object', 'properties': root_props, 'description': 'Response schema (from Response body)' }

        # 3) Fallback to flat Param-name spans if no labels
        spans = rb_block.find_all('span', class_=lambda x: x and 'Param-name' in str(x))
        names = [sp.get_text(strip=True) for sp in spans]
        names = [n for n in names if n and n.lower() not in {'data','query','message'}]
        if names:
            props = { n: { 'type': 'string', 'description': n } for n in names }
            return { 'type': 'object', 'properties': props, 'description': 'Response schema (from Response body)' }
        return None

    def _map_span_properties_to_nearest_container(self, soup: BeautifulSoup, success_properties: List[Dict[str, Any]]):
        """Infer container for span-only properties based on document order context.

        Walks the DOM in visual order across labels and Param-name spans. Maintains a
        current container derived from the last seen object-* label path (e.g., _data_ or _query_).
        Any span-only property names not already present as labels are assigned to that container.
        """
        try:
            # Collect names already present from labels to avoid duplicates
            label_names = set()
            for_info = []
            for lbl in soup.find_all('label', attrs={'for': re.compile(r'^object-')}):
                name = lbl.get_text(strip=True)
                label_names.add(name)
                for_info.append(lbl.get('for', ''))

            endpoint_key = self.target_endpoint.strip('/').split('/')[-1] or 'endpoint'

            # Combined ordered walk: labels and Param-name spans
            def is_prop_tag(tag):
                if tag.name == 'label' and tag.get('for', '').startswith('object-'):
                    return True
                if tag.name == 'span':
                    cls = tag.get('class') or []
                    return any('Param-name' in c for c in cls)
                return False

            ordered = soup.find_all(is_prop_tag)
            current_container = None  # 'data' | 'query' | None

            for tag in ordered:
                if tag.name == 'label':
                    path = tag.get('for', '')
                    if '_data_' in path:
                        current_container = 'data'
                    elif '_query_' in path:
                        current_container = 'query'
                    else:
                        current_container = None
                    continue

                # span-only property
                name = tag.get_text(strip=True)
                # Skip known non-leaf/container names and already-captured labels
                if (not name or name.lower() in {'message', 'data', 'query'} or name in label_names):
                    continue

                # Map span-only properties into the currently proven container (query/data)
                if current_container in ('data', 'query'):
                    synthetic_path = (
                        f"object-{endpoint_key}_data_0_{name}"
                        if current_container == 'data'
                        else f"object-{endpoint_key}_query_{name}"
                    )
                    prop_info = self._extract_parameter_details(tag, name, 'response')
                    if prop_info:
                        prop_info['path'] = synthetic_path
                        success_properties.append(prop_info)
                        # If this span represents an object, attempt to discover nested children within the same container
                        if prop_info.get('type') in ('object', 'array'):
                            # Collect labels that appear to be children of this object based on path
                            all_labels = soup.find_all('label', attrs={'for': re.compile(r'^object-')})
                            found_label_child = False
                            for lbl in all_labels:
                                child_for = lbl.get('for', '')
                                if (f"_{current_container}_" in child_for) and (f"_{name}_" in child_for):
                                    child_info = self._extract_parameter_details(lbl, lbl.get_text(strip=True), 'response')
                                    if child_info:
                                        # For arrays, normalize child path to include index 0 if missing
                                        if prop_info.get('type') == 'array' and re.search(rf"_{name}_[0-9]+_", child_for) is None:
                                            child_for = child_for.replace(f"_{name}_", f"_{name}_0_")
                                        child_info['path'] = child_for
                                        success_properties.append(child_info)
                                        found_label_child = True
                            # If no label-backed children, collect span children within the same DOM block
                            if not found_label_child:
                                try:
                                    # Look for sibling/descendant Param-name spans within the same parent block
                                    parent_block = tag.parent if tag.parent else None
                                    if parent_block:
                                        span_children = parent_block.find_all(
                                            'span',
                                            class_=lambda x: x and 'Param-name' in str(x)
                                        )
                                        for sc in span_children:
                                            child_name = sc.get_text(strip=True)
                                            if not child_name or child_name in {name, 'data', 'query'}:
                                                continue
                                            child_type = self._get_parameter_type(sc)
                                            child_prop = {
                                                'name': child_name,
                                                'type': child_type,
                                                'required': False,
                                                'description': self._get_parameter_description(sc, child_name),
                                                'location': 'response',
                                                'path': (
                                                    f"object-{endpoint_key}_data_0_{name}_0_{child_name}" if prop_info.get('type') == 'array' and current_container == 'data' else
                                                    f"object-{endpoint_key}_query_{name}_0_{child_name}" if prop_info.get('type') == 'array' and current_container == 'query' else
                                                    f"object-{endpoint_key}_data_0_{name}_{child_name}" if current_container == 'data' else
                                                    f"object-{endpoint_key}_query_{name}_{child_name}"
                                                )
                                            }
                                            success_properties.append(child_prop)
                                        # If still nothing, try a generic row/column inference within the block
                                        inferred = self._infer_fields_from_block(
                                            parent_block,
                                            current_container,
                                            endpoint_key,
                                            name,
                                            is_array=(prop_info.get('type') == 'array')
                                        )
                                        success_properties.extend(inferred)
                                except Exception:
                                    pass
        except Exception:
            # Best-effort enrichment; safe to ignore errors
            pass

    def _infer_fields_from_block(self, block, container: str, endpoint_key: str, parent_name: str, is_array: bool) -> List[Dict[str, Any]]:
        """Infer field definitions from a generic block when no labels/spans exist.
        Looks for row-like elements and extracts name/type pairs in a general way.
        """
        inferred: List[Dict[str, Any]] = []
        if not block:
            return inferred

        # Prefer semantic tables if present
        tables = block.find_all('table')
        type_regex = re.compile(r'\b(string|integer|number|boolean|array|object)\b', re.I)
        name_regex = re.compile(r'^[a-z][a-z0-9_]*$', re.I)

        def make_path(field_name: str) -> str:
            return (
                f"object-{endpoint_key}_data_0_{parent_name}_0_{field_name}" if is_array and container == 'data' else
                f"object-{endpoint_key}_query_{parent_name}_0_{field_name}" if is_array and container == 'query' else
                f"object-{endpoint_key}_data_0_{parent_name}_{field_name}" if container == 'data' else
                f"object-{endpoint_key}_query_{parent_name}_{field_name}"
            )

        if tables:
            for table in tables:
                for tr in table.find_all('tr'):
                    cells = tr.find_all(['td', 'th'])
                    if len(cells) < 1:
                        continue
                    name_text = cells[0].get_text(" ", strip=True)
                    if not name_text or not name_regex.match(name_text):
                        continue
                    # Try to find a type token in remaining cells
                    remaining = " ".join(c.get_text(" ", strip=True) for c in cells[1:])
                    tmatch = type_regex.search(remaining)
                    inferred_type = 'string'
                    if tmatch:
                        inferred_type = tmatch.group(1).lower()
                        if inferred_type == 'array of objects':
                            inferred_type = 'array'
                    inferred.append({
                        'name': name_text,
                        'type': {'string':'string','integer':'integer','number':'number','boolean':'boolean','array':'array','object':'object'}.get(inferred_type,'string'),
                        'required': False,
                        'description': (remaining or name_text)[:200],
                        'location': 'response',
                        'path': make_path(name_text)
                    })
            if inferred:
                return inferred

        # Heuristic: scan descendant elements that look like rows (li/div) when tables are absent
        row_candidates = block.find_all(['li', 'div'])

        for row in row_candidates:
            text = row.get_text(" ", strip=True)
            if not text:
                continue
            # Find type hint
            tmatch = type_regex.search(text)
            if not tmatch:
                continue
            # Find a plausible field name token in the row
            tokens = [tok for tok in re.split(r'[^a-zA-Z0-9_]+', text) if tok]
            name_token = None
            for tok in tokens:
                if name_regex.match(tok) and tok.lower() not in {'data', 'query', parent_name.lower()}:
                    name_token = tok
                    break
            if not name_token:
                continue

            readme_type = tmatch.group(1).lower()
            type_mapping = {
                'string': 'string',
                'number': 'number',
                'integer': 'integer',
                'boolean': 'boolean',
                'array': 'array',
                'object': 'object'
            }
            inferred_type = type_mapping.get(readme_type, 'string')

            inferred.append({
                'name': name_token,
                'type': inferred_type,
                'required': False,
                'description': text[:200],
                'location': 'response',
                'path': make_path(name_token)
            })

        return inferred
    
    def _extract_parameter_details(self, element, param_name: str, context: str) -> Optional[Dict[str, Any]]:
        """Extract detailed parameter information from DOM element"""
        
        # Get type from next sibling
        param_type = self._get_parameter_type(element)
        
        # Get description from nearby elements
        description = self._get_parameter_description(element, param_name)
        
        # Determine if required (for query parameters)
        is_required = self._is_parameter_required(element) if context == 'query' else False
        
        return {
            'name': param_name,
            'type': param_type,
            'required': is_required,
            'description': description,
            'location': 'query' if context == 'query' else 'response'
        }
    
    def _get_parameter_type(self, element) -> str:
        """Get parameter type from DOM element context"""
        
        # Look for type in next sibling div
        next_elem = element.find_next_sibling('div')
        if next_elem:
            type_text = next_elem.get_text(strip=True).lower()
            
            # Map ReadMe.io type names to standard types
            type_mapping = {
                'string': 'string',
                'number': 'number',
                'integer': 'integer', 
                'boolean': 'boolean',
                'array': 'array',
                'object': 'object',
                'array of objects': 'array'
            }
            
            for readme_type, standard_type in type_mapping.items():
                if readme_type in type_text:
                    return standard_type
        
        return 'string'  # Default
    
    def _get_parameter_description(self, element, param_name: str) -> str:
        """Extract the natural-language description line rendered under a param row.

        Heuristics (class-agnostic to avoid hashed CSS):
        - Prefer immediate following siblings within the same parent that are <p>/<div>/<span>/<small>
          and contain descriptive phrases (e.g., 'Filter', 'Defaults', 'Supported').
        - Otherwise, scan the ancestor row container for a short paragraph that does not just repeat
          the name/type/required badges.
        - Fall back to previous generic extraction if nothing is found.
        """

        def clean(t: str) -> str:
            return re.sub(r"\s+", " ", t).strip()

        def looks_like_desc(t: str) -> bool:
            if not t:
                return False
            tl = t.lower()
            # Avoid badge concatenations
            if param_name.lower() in tl and any(tok in tl for tok in ["string", "integer", "number", "boolean", "object", "array", "required", "optional"]):
                # Likely the header line; not the NL description
                return False
            # Prefer sentences or helpful cue words
            if any(k in tl for k in ["filter", "defaults", "supported", "provide", "format", "list", "id", "level"]):
                return True
            # Otherwise accept moderately long lines that aren't just the name/type
            return len(t) >= 12 and not tl.startswith(param_name.lower())

        # 1) Try immediate next siblings within the same parent container
        try:
            parent = element.parent
            if parent is not None:
                # Check a few next siblings
                count = 0
                sib = element.next_sibling
                collected: list[str] = []
                while sib is not None and count < 6:
                    if getattr(sib, 'get_text', None):
                        txt = clean(sib.get_text(" ", strip=True))
                        if looks_like_desc(txt):
                            if txt not in collected:
                                collected.append(txt)
                    sib = sib.next_sibling
                    count += 1
                # Sometimes the helpful line is a following block sibling of the parent
                count = 0
                psib = parent.next_sibling
                while psib is not None and count < 4:
                    if getattr(psib, 'get_text', None):
                        txt = clean(psib.get_text(" ", strip=True))
                        if looks_like_desc(txt) and txt not in collected:
                            collected.append(txt)
                    psib = psib.next_sibling
                    count += 1
                if collected:
                    return ". ".join(collected)[:300]
        except Exception:
            pass

        # 2) Search descendant paragraphs/spans under the nearest container ancestor
        try:
            container = element
            for _ in range(3):
                if container and container.parent:
                    container = container.parent
            if container is not None:
                for tag in container.find_all(["p", "div", "span", "small"], limit=12):
                    txt = clean(tag.get_text(" ", strip=True))
                    if looks_like_desc(txt):
                        return txt[:300]
        except Exception:
            pass

        # 3) Fallback: previous generic parent text heuristic
        current = element
        for _ in range(3):
            if current and current.parent:
                current = current.parent
                text_content = current.get_text()
                if len(text_content) > 20 and param_name.lower() in text_content.lower():
                    return clean(text_content)[:300]

        # 4) Final fallback
        return f"Parameter {param_name}"
    
    def _is_parameter_required(self, element) -> bool:
        """Determine if query parameter is required"""
        
        # Look for "required" text in nearby elements
        parent = element.parent
        if parent:
            parent_text = parent.get_text().lower()
            if 'required' in parent_text:
                return True
        
        return False
    
    def _is_error_response_property(self, element, prop_name: str, for_attr: str) -> bool:
        """Determine if a property belongs to error response (400/401) using universal patterns"""
        
        # Universal error property validated across multiple endpoints
        if prop_name.lower() == 'message':
            return True
        
        # Look for error context indicators
        parent = element.parent
        if parent:
            context = parent.get_text().lower()
            if any(indicator in context for indicator in ['400', '401', 'error', 'bad request', 'unauthorized']):
                return True
        
        return False
    
    def _deduplicate_properties(self, properties: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate properties, keeping the most informative version"""
        
        seen = {}
        result = []
        
        def make_key(p: Dict[str, Any]) -> str:
            path = p.get('path', '') or ''
            container = ''
            if path and 'object-' in path:
                parts = path.replace('object-', '').split('_')
                if 'data' in parts:
                    i = parts.index('data') + 1
                    token_parts = []
                    while i < len(parts) and not parts[i].isdigit():
                        token_parts.append(parts[i])
                        i += 1
                    if token_parts:
                        container = '_'.join(token_parts)
                elif 'query' in parts:
                    container = 'query'
            return f"{container}::{p['name']}" if container else p['name']
        
        for prop in properties:
            key = make_key(prop)
            
            if key not in seen:
                seen[key] = prop
                result.append(prop)
            else:
                # Keep the one with more information (path info, better description)
                existing = seen[key]
                
                # Prefer the one with path information
                if 'path' in prop and 'path' not in existing:
                    seen[key] = prop
                    # Replace in result
                    for i, r in enumerate(result):
                        if r['name'] == key:
                            result[i] = prop
                            break
        
        return result
    
    def _discover_containers(self, properties: List[Dict[str, Any]]) -> Dict[str, List]:
        """Dynamically discover containers from DOM paths"""
        containers = {}
        
        for prop in properties:
            path = prop.get('path', '')
            if path and 'object-' in path:
                # Parse path: object-{endpoint}_{container}_{index?}_{property}
                path_parts = path.replace('object-', '').split('_')
                if len(path_parts) >= 2:
                    container_name = path_parts[1]  # Second part is container
                    
                    if container_name not in containers:
                        containers[container_name] = []
                    containers[container_name].append(prop)
        
        return containers
    
    def _assign_to_container(self, prop: Dict[str, Any], containers: Dict[str, List]):
        """Assign property to appropriate container based on path"""
        path = prop.get('path', '')
        if path and 'object-' in path:
            path_parts = path.replace('object-', '').split('_')
            if len(path_parts) >= 2:
                container_name = path_parts[1]
                if container_name in containers and prop not in containers[container_name]:
                    containers[container_name].append(prop)
    
    def _build_nested_schema(self, properties: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Build nested schema structure using dynamic container discovery"""
        
        schema = {
            'type': 'object',
            'properties': {},
            'description': 'Response schema'
        }
        
        # Dynamic container discovery - group by actual containers found in DOM
        containers = self._discover_containers(properties)
        root_properties = []
        
        for prop in properties:
            path = prop.get('path', '')
            
            if path and 'object-' in path:
                # Nested property - assign to discovered container
                self._assign_to_container(prop, containers)
            else:
                # Root property (span elements)
                root_properties.append(prop)
        
        # Process discovered containers dynamically
        for container_name, container_props in containers.items():
            if container_name in ['query', 'data']:
                # Universal containers with special handling
                if container_name == 'query':
                    schema['properties'][container_name] = self._build_query_schema(container_props, root_properties)
                elif container_name == 'data':
                    data_schema = self._build_data_schema(container_props)
                    schema['properties'][container_name] = data_schema
            else:
                # Endpoint-specific containers - build generically
                schema['properties'][container_name] = self._build_generic_container_schema(container_props)
        
        # Process root properties that aren't containers
        for prop in root_properties:
            prop_name = prop['name']
            prop_type = prop['type']
            
            # Skip container spans to avoid duplication
            is_container = prop_name in containers.keys()
            should_skip = is_container  # Skip all container properties regardless of element type
            
            if not should_skip:
                schema['properties'][prop_name] = {
                    'type': prop_type,
                    'description': prop['description']
                }
        
        # Additional nested properties are now handled by dynamic container discovery
        # No need for separate other_nested processing
        
        return schema
    
    def _build_schema_from_dom_hierarchy(self, properties: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Build schema by preserving actual DOM hierarchy instead of flattening"""
        
        schema = {
            'type': 'object', 
            'properties': {},
            'description': 'Response schema'
        }
        
        # Group elements by their DOM position and parent context
        # This preserves the actual hierarchy ReadMe.io renders
        
        for prop in properties:
            name = prop['name']
            
            # Use DOM element context to determine actual nesting
            if prop.get('element_html', '').startswith('<span'):
                # Span elements are container indicators
                if name in ['query', 'data']:
                    # Create container
                    schema['properties'][name] = {
                        'type': 'array' if 'array' in prop.get('type', '') else 'object',
                        'description': f'{name.title()} container'
                    }
            elif 'for="object-' in prop.get('element_html', ''):
                # Label elements with object paths show nested structure
                path = prop.get('path', '')
                self._add_nested_property(schema['properties'], prop, path)
        
        return schema
    
    def _build_query_schema(self, query_nested: List[Dict], root_properties: List[Dict] = None) -> Dict[str, Any]:
        """Build query schema from discovered properties"""
        
        query_properties = {}
        
        # Add nested properties found in DOM
        for prop in query_nested:
            query_properties[prop['name']] = {
                'type': prop['type'],
                'description': prop['description']
            }
        
        return {
            'type': 'array',
            'items': {
                'type': 'object', 
                'properties': query_properties
            },
            'description': f'Query container'
        }
    
    def _build_data_schema(self, data_nested: List[Dict]) -> Dict[str, Any]:
        """Build data array schema from DOM structure"""
        
        data_item_properties = {}

        def add_to_schema(target_props: Dict[str, Any], tokens: List[str], leaf_prop: Dict[str, Any]):
            """Add a property into target_props following tokens that may indicate arrays/objects.

            Example tokens after 'data': ['0', 'device', '0', 'timestamp']
            → creates device: { type: 'array', items: { properties: { timestamp: ... } } }
            """
            idx = 0
            current_props = target_props
            while idx < len(tokens):
                # Skip any standalone indices
                if tokens[idx].isdigit():
                    idx += 1
                    continue
                # Group contiguous non-digit tokens into a single name
                name_parts = []
                while idx < len(tokens) and not tokens[idx].isdigit():
                    name_parts.append(tokens[idx])
                    idx += 1
                name = '_'.join(name_parts) if name_parts else leaf_prop['name']
                # If next token exists and is a digit, this name denotes an array container
                if idx < len(tokens) and tokens[idx].isdigit():
                    if name not in current_props:
                        current_props[name] = {
                            'type': 'array',
                            'items': {
                                'type': 'object',
                                'properties': {}
                            }
                        }
                    # Skip the index and descend into items.properties
                    idx += 1
                    current_props = current_props[name]['items']['properties']
                    continue
                # Otherwise this is the leaf
                current_props[name] = {
                    'type': leaf_prop['type'],
                    'description': leaf_prop['description']
                }
                return

        # Process all data container properties with path-aware nesting
        for prop in data_nested:
            path = prop.get('path', '')
            if path and 'object-' in path:
                parts = path.replace('object-', '').split('_')
                # Find 'data' segment and use the remaining tokens
                if 'data' in parts:
                    data_idx = parts.index('data')
                    tokens_after_data = parts[data_idx + 1:]
                    # If no tokens after 'data', place directly
                    if not tokens_after_data:
                        data_item_properties[prop['name']] = {
                            'type': prop['type'],
                            'description': prop['description']
                        }
                    else:
                        # If tokens resolve directly to a leaf (e.g., ['0','timestamp'])
                        # add under the leaf name at root; otherwise follow containers
                        # Build leaf definition
                        add_to_schema(data_item_properties, tokens_after_data, prop)
                else:
                    # Fallback if path missing expected structure
                    data_item_properties[prop['name']] = {
                        'type': prop['type'],
                        'description': prop['description']
                    }
            else:
                # No path info; flat add
                data_item_properties[prop['name']] = {
                    'type': prop['type'],
                    'description': prop['description']
                }
        
        return {
            'type': 'array',
            'items': {
                'type': 'object',
                'properties': data_item_properties
            },
            'description': 'Data array container'
        }
    
    def _build_generic_container_schema(self, container_props: List[Dict]) -> Dict[str, Any]:
        """Build schema for endpoint-specific containers dynamically"""
        
        properties = {}
        has_indexed_props = False
        
        for prop in container_props:
            path = prop.get('path', '')
            # Check if this container has indexed properties (array items)
            if path and len(path.split('_')) > 2:
                path_parts = path.split('_')
                if len(path_parts) > 2 and path_parts[2].isdigit():
                    has_indexed_props = True
            
            properties[prop['name']] = {
                'type': prop['type'],
                'description': prop['description']
            }
        
        if has_indexed_props:
            # Array container
            return {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'properties': properties
                },
                'description': f'Array container with {len(properties)} properties'
            }
        else:
            # Object container
            return {
                'type': 'object',
                'properties': properties,
                'description': f'Object container with {len(properties)} properties'
            }
    
    def _add_nested_property(self, schema_props: Dict, prop: Dict, path: str):
        """Add nested property to schema using path information"""
        
        # Parse path: object-dcLoss_query_0_asset -> ['query', '0', 'asset']  
        if 'object-' in path:
            path_part = path.split('object-', 1)[1]  # Remove object- prefix
            path_parts = path_part.split('_')[1:]  # Remove method name, get path
            
            if not path_parts:
                return
            
            # Navigate/create nested structure
            current = schema_props
            
            for i, part in enumerate(path_parts[:-1]):  # All except last part
                if part.isdigit():
                    # Array index - previous part should be array
                    continue
                else:
                    # Property name
                    if part not in current:
                        # Check if next part is digit (array)
                        is_array = (i + 1 < len(path_parts) - 1 and path_parts[i + 1].isdigit())
                        
                        if is_array:
                            current[part] = {
                                'type': 'array',
                                'items': {
                                    'type': 'object',
                                    'properties': {}
                                }
                            }
                            current = current[part]['items']['properties']
                        else:
                            current[part] = {
                                'type': 'object',
                                'properties': {}
                            }
                            current = current[part]['properties']
                    else:
                        # Navigate to existing property
                        if current[part]['type'] == 'array' and 'items' in current[part]:
                            current = current[part]['items']['properties']
                        elif 'properties' in current[part]:
                            current = current[part]['properties']
                        else:
                            # Create properties if they don't exist
                            current[part]['properties'] = {}
                            current = current[part]['properties']
            
            # Add final property
            final_prop_name = path_parts[-1]
            current[final_prop_name] = {
                'type': prop['type'],
                'description': prop['description']
            }
    
    def _print_schema_summary(self, schema: Dict[str, Any], indent: str = "    "):
        """Print a summary of the extracted schema"""
        
        properties = schema.get('properties', {})
        print(f"{indent}📄 Schema structure:")
        
        for prop_name, prop_info in properties.items():
            prop_type = prop_info.get('type', 'unknown')
            print(f"{indent}  • {prop_name} ({prop_type})")
            
            if prop_type == 'array' and 'items' in prop_info:
                items_props = prop_info['items'].get('properties', {})
                for sub_name, sub_info in list(items_props.items())[:3]:  # Show first 3
                    print(f"{indent}    └─ {sub_name} ({sub_info.get('type', 'unknown')})")
                if len(items_props) > 3:
                    print(f"{indent}    └─ ... and {len(items_props) - 3} more")
            
            elif prop_type == 'object' and 'properties' in prop_info:
                obj_props = prop_info.get('properties', {})
                for sub_name, sub_info in list(obj_props.items())[:3]:  # Show first 3
                    print(f"{indent}    └─ {sub_name} ({sub_info.get('type', 'unknown')})")
                if len(obj_props) > 3:
                    print(f"{indent}    └─ ... and {len(obj_props) - 3} more")
    
    def run_extraction(self):
        """Run complete extraction process"""
        print("🎯 PROPER README.IO EXTRACTOR")
        print(f"Target endpoint: {self.target_endpoint}")
        print("=" * 60)
        
        try:
            if not self.setup_driver(headless=True):
                return None
            
            if not self.setup_session():
                return None
            
            if not self.navigate_to_target():
                return None
            
            # Extract complete API specification
            results = self.extract_complete_api_spec()
            
            # Save results (respect optional output directory)
            filename = f"proper_extraction_{self.target_endpoint.replace('/', '_').replace('-', '_')}.json"
            output_path = filename
            if self.output_dir:
                os.makedirs(self.output_dir, exist_ok=True)
                output_path = os.path.join(self.output_dir, filename)
            with open(output_path, 'w') as f:
                json.dump(results, f, indent=2)
            
            # Print summary
            print("\n" + "=" * 60)
            print("📊 PROPER EXTRACTION RESULTS")
            print("=" * 60)
            
            print(f"Endpoint: {self.target_endpoint}")
            print(f"Query parameters found: {results['parameters_found']}")
            print(f"Response schemas found: {results['response_schemas_found']}")
            
            # Print query parameters
            if results['query_parameters']:
                print(f"\n📝 QUERY PARAMETERS:")
                for param in results['query_parameters']:
                    req_badge = "🔴 REQUIRED" if param['required'] else "🟢 OPTIONAL"
                    print(f"  • {param['name']} ({param['type']}) {req_badge}")
                    print(f"    {param['description']}")
            
            # Print response schema summary  
            if results['response_schemas']:
                print(f"\n📊 RESPONSE SCHEMAS:")
                for status_code, schema in results['response_schemas'].items():
                    print(f"  Status {status_code}: {len(schema.get('properties', {}))} properties")
            
            print(f"\n📄 Results saved to: {output_path}")
            
            return results
            
        except Exception as e:
            print(f"❌ Extraction failed: {e}")
            return None
        
        finally:
            if self.driver:
                self.driver.quit()


def main():
    """Test proper extractor on DC Loss endpoint"""
    
    extractor = ProperReadMeExtractor("/reference/dcloss")
    results = extractor.run_extraction()
    
    if results:
        print("\n✅ Proper extraction completed successfully!")
    else:
        print("\n❌ Proper extraction failed")


if __name__ == "__main__":
    main()