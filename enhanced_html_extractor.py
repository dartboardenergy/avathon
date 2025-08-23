#!/usr/bin/env python3
"""
Enhanced HTML Extractor for Avathon API Documentation
Phase 1: Static HTML Content Extraction

Extracts maximum possible information from ReadMe.io HTML files including:
- Complete navigation hierarchy and endpoint catalog
- ReadMe.io configuration metadata  
- Content gap analysis for JavaScript-rendered areas
"""

import json
import os
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
from urllib.parse import unquote
import html

from bs4 import BeautifulSoup, Tag


@dataclass
class Endpoint:
    """Individual API endpoint definition"""
    name: str
    url: str
    method: str
    category: str
    subcategory: Optional[str] = None
    file_path: str = ""
    is_active: bool = False
    html_title: str = ""
    canonical_url: str = ""


@dataclass
class NavigationCategory:
    """Navigation category with hierarchical structure"""
    name: str
    endpoints: List[Endpoint]
    subcategories: Dict[str, List[Endpoint]]
    parent_url: Optional[str] = None


@dataclass
class ReadMeConfig:
    """ReadMe.io project configuration"""
    subdomain: str = ""
    repo_id: str = ""
    version: str = ""
    release_version: str = ""
    project_title: str = ""
    domain: str = ""
    algolia_index: str = ""
    asset_url: str = ""
    proxy_url: str = ""
    raw_config: Dict[str, Any] = None


@dataclass
class ExtractionStats:
    """Statistics on extraction coverage"""
    total_files: int = 0
    processed_files: int = 0
    total_endpoints: int = 0
    categories: int = 0
    subcategories: int = 0
    methods_found: Set[str] = None
    javascript_dependent_areas: List[str] = None

    def __post_init__(self):
        if self.methods_found is None:
            self.methods_found = set()
        if self.javascript_dependent_areas is None:
            self.javascript_dependent_areas = []


class SidebarParser:
    """Extracts navigation hierarchy from ReadMe.io sidebar"""
    
    def __init__(self):
        self.endpoints = []
        self.categories = {}
    
    def parse_sidebar(self, soup: BeautifulSoup, file_path: str) -> List[Endpoint]:
        """Extract all endpoints from sidebar navigation"""
        sidebar = soup.find('nav', {'id': 'reference-sidebar'})
        if not sidebar:
            return []
        
        endpoints = []
        current_category = "Uncategorized"
        
        # Find all sidebar sections
        sections = sidebar.find_all('section', class_='Sidebar-listWrapper6Q9_yUrG906C')
        
        for section in sections:
            # Get section heading (category)
            heading = section.find('h2', class_='Sidebar-headingTRQyOa2pk0gh')
            if heading:
                current_category = heading.get_text(strip=True)
            
            # Parse endpoints in this category
            category_endpoints = self._parse_category_endpoints(section, current_category, file_path)
            endpoints.extend(category_endpoints)
        
        return endpoints
    
    def _parse_category_endpoints(self, section: Tag, category: str, file_path: str) -> List[Endpoint]:
        """Parse endpoints within a category section"""
        endpoints = []
        
        # Find all sidebar links in this section
        links = section.find_all('a', class_='Sidebar-link2Dsha-r-GKh2')
        
        for link in links:
            endpoint = self._parse_endpoint_link(link, category, file_path)
            if endpoint:
                endpoints.append(endpoint)
        
        return endpoints
    
    def _parse_endpoint_link(self, link: Tag, category: str, file_path: str) -> Optional[Endpoint]:
        """Parse individual endpoint link"""
        # Get URL
        url = link.get('href', '')
        if not url.startswith('/reference/'):
            return None
        
        # Get endpoint name
        name_span = link.find('span', class_='Sidebar-link-text_label1gCT_uPnx7Gu')
        name = name_span.get_text(strip=True) if name_span else ""
        
        # Get HTTP method - improved extraction
        method = "GET"  # default
        method_span = link.find('span', attrs={'data-testid': 'http-method'})
        if method_span:
            method = method_span.get_text(strip=True).upper()
        else:
            # Fallback: look for APIMethod classes
            method_span = link.find('span', class_='rm-APIMethod')
            if method_span:
                method_classes = method_span.get('class', [])
                for cls in method_classes:
                    if cls.startswith('APIMethod_') and cls not in ['APIMethod_fixedWidth', 'APIMethod_fixedWidth_md', 'APIMethod_md']:
                        method = cls.replace('APIMethod_', '').upper()
                        break
        
        # Check if this is the active page
        is_active = 'active' in link.get('class', [])
        
        # Determine subcategory (if it's a subpage)
        subcategory = None
        if 'subpage' in link.get('class', []):
            # Find parent category by looking up the DOM
            parent_link = link.find_parent('ul', class_='subpages')
            if parent_link:
                parent = parent_link.find_previous_sibling('a', class_='Sidebar-link2Dsha-r-GKh2')
                if parent:
                    parent_name_span = parent.find('span', class_='Sidebar-link-text_label1gCT_uPnx7Gu')
                    subcategory = parent_name_span.get_text(strip=True) if parent_name_span else None
        
        return Endpoint(
            name=name,
            url=url,
            method=method,
            category=category,
            subcategory=subcategory,
            file_path=file_path,
            is_active=is_active
        )


class MetadataExtractor:
    """Extracts ReadMe.io metadata and configuration"""
    
    def extract_page_metadata(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract page-level metadata"""
        metadata = {}
        
        # Extract title
        title_tag = soup.find('title')
        if title_tag:
            metadata['title'] = title_tag.get_text(strip=True)
        
        # Extract canonical URL
        canonical = soup.find('link', {'rel': 'canonical'})
        if canonical:
            metadata['canonical_url'] = canonical.get('href', '')
        
        # Extract meta description
        description = soup.find('meta', {'name': 'description'})
        if description:
            metadata['description'] = description.get('content', '')
        
        # Extract ReadMe.io specific meta tags
        readme_meta = {}
        for meta in soup.find_all('meta'):
            name = meta.get('name', '')
            if name.startswith('readme-'):
                readme_meta[name] = meta.get('content', '')
        
        metadata['readme_meta'] = readme_meta
        return metadata
    
    def extract_readme_config(self, soup: BeautifulSoup) -> ReadMeConfig:
        """Extract ReadMe.io configuration from embedded JSON"""
        config_script = soup.find('script', {'id': 'config'})
        
        if not config_script:
            return ReadMeConfig()
        
        # Get the data-json attribute
        data_json = config_script.get('data-json', '')
        if not data_json:
            return ReadMeConfig()
        
        try:
            # Decode HTML entities and parse JSON
            decoded_json = html.unescape(data_json)
            config_data = json.loads(decoded_json)
            
            return ReadMeConfig(
                subdomain=self._extract_from_meta(soup, 'readme-subdomain'),
                repo_id=self._extract_from_meta(soup, 'readme-repo'),
                version=self._extract_from_meta(soup, 'readme-version'),
                release_version=config_data.get('releaseVersion', ''),
                domain=config_data.get('domain', ''),
                algolia_index=config_data.get('algoliaIndex', ''),
                asset_url=config_data.get('asset_url', ''),
                proxy_url=config_data.get('proxyUrl', ''),
                raw_config=config_data
            )
            
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Error parsing ReadMe config JSON: {e}")
            return ReadMeConfig()
    
    def _extract_from_meta(self, soup: BeautifulSoup, name: str) -> str:
        """Extract value from meta tag"""
        meta = soup.find('meta', {'name': name})
        return meta.get('content', '') if meta else ''


class ContentAnalyzer:
    """Analyzes content patterns and identifies JavaScript-dependent areas"""
    
    def analyze_content_gaps(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Identify areas that require JavaScript rendering"""
        gaps = {
            'parameter_tables': self._find_parameter_areas(soup),
            'request_response_schemas': self._find_schema_areas(soup),
            'code_examples': self._find_code_example_areas(soup),
            'interactive_elements': self._find_interactive_elements(soup),
            'dynamic_content_containers': self._find_dynamic_containers(soup)
        }
        
        return gaps
    
    def _find_parameter_areas(self, soup: BeautifulSoup) -> List[str]:
        """Find areas where parameter tables would be rendered"""
        areas = []
        
        # Look for common parameter table containers
        selectors = [
            '[class*="parameter"]',
            '[class*="schema"]',
            '[class*="table"]',
            '[id*="param"]'
        ]
        
        for selector in selectors:
            elements = soup.select(selector)
            for element in elements:
                if element.get_text(strip=True) == "":
                    areas.append(f"Empty {selector}: {element.get('class', [])}")
        
        return areas
    
    def _find_schema_areas(self, soup: BeautifulSoup) -> List[str]:
        """Find areas where request/response schemas would be rendered"""
        areas = []
        
        # Look for schema-related containers
        schema_indicators = soup.find_all(attrs={'class': re.compile(r'.*(schema|response|request).*', re.I)})
        
        for element in schema_indicators:
            if not element.get_text(strip=True):
                areas.append(f"Empty schema area: {element.get('class', [])}")
        
        return areas
    
    def _find_code_example_areas(self, soup: BeautifulSoup) -> List[str]:
        """Find areas where code examples would be rendered"""
        areas = []
        
        # Look for code blocks and example containers
        code_areas = soup.find_all(['pre', 'code'])
        code_areas.extend(soup.find_all(attrs={'class': re.compile(r'.*(example|code|sample).*', re.I)}))
        
        for element in code_areas:
            if not element.get_text(strip=True):
                areas.append(f"Empty code area: {element.name} {element.get('class', [])}")
        
        return areas
    
    def _find_interactive_elements(self, soup: BeautifulSoup) -> List[str]:
        """Find interactive elements that require JavaScript"""
        areas = []
        
        # Look for buttons, forms, and interactive widgets
        interactive = soup.find_all(['button', 'form', 'input'])
        interactive.extend(soup.find_all(attrs={'class': re.compile(r'.*(try|test|interactive).*', re.I)}))
        
        for element in interactive:
            areas.append(f"Interactive: {element.name} {element.get('class', [])}")
        
        return areas
    
    def _find_dynamic_containers(self, soup: BeautifulSoup) -> List[str]:
        """Find containers that are likely populated by JavaScript"""
        areas = []
        
        # Look for empty divs with specific class patterns
        containers = soup.find_all('div')
        
        for div in containers:
            classes = div.get('class', [])
            class_str = ' '.join(classes)
            
            # Check if it's likely a React component container
            if (any(keyword in class_str.lower() for keyword in ['react', 'component', 'dynamic', 'render']) 
                and not div.get_text(strip=True)):
                areas.append(f"Dynamic container: {classes}")
        
        return areas


class EnhancedHTMLExtractor:
    """Main class orchestrating the extraction process"""
    
    def __init__(self, html_directory: str):
        self.html_directory = Path(html_directory)
        self.sidebar_parser = SidebarParser()
        self.metadata_extractor = MetadataExtractor()
        self.content_analyzer = ContentAnalyzer()
        
        self.all_endpoints = []
        self.categories = {}
        self.metadata_by_file = {}
        self.readme_config = None
        self.extraction_stats = ExtractionStats()
    
    def extract_all(self) -> Dict[str, Any]:
        """Extract all available information from HTML files"""
        html_files = list(self.html_directory.glob('*.html'))
        self.extraction_stats.total_files = len(html_files)
        
        print(f"Processing {len(html_files)} HTML files...")
        
        # Extract navigation structure from first file only (it's the same on all pages)
        navigation_extracted = False
        
        for html_file in html_files:
            print(f"  Processing: {html_file.name}")
            self._process_html_file(html_file, extract_navigation=not navigation_extracted)
            if not navigation_extracted:
                navigation_extracted = True
            self.extraction_stats.processed_files += 1
        
        # Build category structure
        self._build_category_structure()
        
        # Calculate final stats
        self.extraction_stats.total_endpoints = len(self.all_endpoints)
        self.extraction_stats.categories = len(self.categories)
        
        print(f"Extraction complete: {self.extraction_stats.total_endpoints} endpoints across {self.extraction_stats.categories} categories")
        
        return {
            'endpoints': [asdict(ep) for ep in self.all_endpoints],
            'categories': {name: asdict(cat) for name, cat in self.categories.items()},
            'metadata': self.metadata_by_file,
            'readme_config': asdict(self.readme_config) if self.readme_config else {},
            'extraction_stats': asdict(self.extraction_stats)
        }
    
    def _process_html_file(self, html_file: Path, extract_navigation: bool = True):
        """Process individual HTML file"""
        try:
            with open(html_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            soup = BeautifulSoup(content, 'html.parser')
            
            # Extract endpoints from sidebar (only from first file to avoid duplicates)
            if extract_navigation:
                endpoints = self.sidebar_parser.parse_sidebar(soup, str(html_file))
                for endpoint in endpoints:
                    # For navigation endpoints, we'll set metadata from the actual endpoint file later
                    pass
                
                self.all_endpoints.extend(endpoints)
                
                # Update stats for navigation endpoints
                for endpoint in endpoints:
                    self.extraction_stats.methods_found.add(endpoint.method)
            
            # Always extract page-specific metadata
            metadata = self.metadata_extractor.extract_page_metadata(soup)
            metadata['content_gaps'] = self.content_analyzer.analyze_content_gaps(soup)
            self.metadata_by_file[html_file.name] = metadata
            
            # Extract ReadMe config (from first file that has it)
            if not self.readme_config:
                config = self.metadata_extractor.extract_readme_config(soup)
                if config.raw_config:
                    self.readme_config = config
            
        except Exception as e:
            print(f"Error processing {html_file.name}: {e}")
    
    def _build_category_structure(self):
        """Build hierarchical category structure"""
        for endpoint in self.all_endpoints:
            category_name = endpoint.category
            
            if category_name not in self.categories:
                self.categories[category_name] = NavigationCategory(
                    name=category_name,
                    endpoints=[],
                    subcategories={}
                )
            
            category = self.categories[category_name]
            
            if endpoint.subcategory:
                # Add to subcategory
                if endpoint.subcategory not in category.subcategories:
                    category.subcategories[endpoint.subcategory] = []
                category.subcategories[endpoint.subcategory].append(endpoint)
                self.extraction_stats.subcategories += 1
            else:
                # Add to main category
                category.endpoints.append(endpoint)
    
    def export_results(self, output_dir: str = "."):
        """Export extraction results to files"""
        output_path = Path(output_dir)
        
        # Get all extracted data
        all_data = self.extract_all() if not self.all_endpoints else {
            'endpoints': [asdict(ep) for ep in self.all_endpoints],
            'categories': {name: asdict(cat) for name, cat in self.categories.items()},
            'metadata': self.metadata_by_file,
            'readme_config': asdict(self.readme_config) if self.readme_config else {},
            'extraction_stats': asdict(self.extraction_stats)
        }
        
        # Export main catalog
        with open(output_path / 'avathon_static_catalog.json', 'w') as f:
            json.dump(all_data, f, indent=2, default=str)
        
        # Export navigation hierarchy separately
        with open(output_path / 'navigation_hierarchy.json', 'w') as f:
            json.dump(all_data['categories'], f, indent=2, default=str)
        
        # Export metadata analysis
        with open(output_path / 'metadata_analysis.json', 'w') as f:
            json.dump({
                'readme_config': all_data['readme_config'],
                'file_metadata': all_data['metadata'],
                'extraction_stats': all_data['extraction_stats']
            }, f, indent=2, default=str)
        
        print(f"Results exported to {output_path}")
        return all_data


if __name__ == "__main__":
    # Run extraction
    extractor = EnhancedHTMLExtractor("html_dumps_all")
    results = extractor.export_results()
    
    print(f"\n=== EXTRACTION SUMMARY ===")
    stats = results['extraction_stats']
    print(f"Files processed: {stats['processed_files']}/{stats['total_files']}")
    print(f"Endpoints found: {stats['total_endpoints']}")
    print(f"Categories: {stats['categories']}")
    print(f"HTTP methods: {', '.join(sorted(stats['methods_found']))}")
    print(f"Files exported: avathon_static_catalog.json, navigation_hierarchy.json, metadata_analysis.json")