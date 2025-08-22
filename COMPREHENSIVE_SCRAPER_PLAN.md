# Comprehensive Avathon API Scraper Plan

## Objective
Build a fully programmatic scraper that extracts detailed API specifications from all 75+ discovered endpoints and generates a complete OpenAPI specification without any generative/LLM processing.

## Architecture Overview

### 1. **Endpoint Scraper Class**
```python
class ComprehensiveAvathonScraper:
    - Uses working authentication (connect.sid cookie + headers)
    - Processes all 75+ reference links discovered
    - Extracts structured data from each endpoint page
    - Handles rate limiting and error recovery
```

### 2. **Data Extraction Pipeline**

#### **Stage 1: Page Content Extraction**
- **HTTP Method Detection**: Parse page for `GET`, `POST`, `PUT`, `DELETE`, `PATCH`
- **URL Path Extraction**: Extract actual API paths (e.g., `/api/v1/assets`)
- **Description Parsing**: Extract endpoint descriptions from headers/paragraphs
- **Parameter Tables**: Parse HTML tables for parameter specifications
- **Request/Response Examples**: Extract JSON examples from code blocks

#### **Stage 2: Structured Data Parsing**
- **Parameter Schema**: Extract name, type, required, description, location (query/path/body)
- **Request Body Schema**: Parse JSON schemas and examples
- **Response Schema**: Extract response formats and status codes
- **Authentication Requirements**: Detect auth patterns
- **Rate Limiting Info**: Extract any rate limit documentation

#### **Stage 3: OpenAPI Generation**
- **Schema Validation**: Ensure all extracted data conforms to OpenAPI 3.0.3
- **Path Consolidation**: Group operations by path
- **Component Extraction**: Identify reusable schemas and components
- **Security Scheme Definition**: Define authentication methods

## Implementation Strategy

### **Core Scraping Logic**
1. **HTML Parser**: BeautifulSoup for reliable HTML parsing
2. **Pattern Matching**: Regex patterns for HTTP methods, paths, parameters
3. **Table Processing**: Systematic extraction from parameter/response tables
4. **JSON Parsing**: Extract and validate JSON examples
5. **Schema Inference**: Infer types from examples and descriptions

### **Data Structures**
```python
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
    
@dataclass  
class Parameter:
    name: str
    location: str  # query, path, header
    type: str
    required: bool
    description: str
    example: Optional[str]
```

### **OpenAPI Generation**
- **Programmatic Assembly**: No template generation, pure data structure building
- **Validation**: JSON Schema validation of final OpenAPI spec
- **Component Deduplication**: Identify and extract common schemas
- **Path Organization**: Group by resource type (assets, devices, etc.)

### **Error Handling & Robustness**
- **Retry Logic**: Handle network failures with exponential backoff
- **Partial Success**: Continue processing if individual endpoints fail
- **Data Validation**: Validate extracted data at each stage
- **Progress Tracking**: Detailed logging of processing status

### **Output Artifacts**
1. **`avathon_api_complete.json`**: Full OpenAPI 3.0.3 specification
2. **`endpoint_details.json`**: Raw extracted data for debugging
3. **`scraping_report.json`**: Processing statistics and any failures
4. **`parameter_catalog.json`**: Catalog of all parameters across endpoints

## Key Features

### **Intelligent Parsing**
- **Multi-format Support**: Handle different documentation layouts
- **Context-aware Extraction**: Use surrounding HTML context for better parsing
- **Example-driven Schema**: Infer schemas from actual examples where possible
- **Fallback Strategies**: Multiple parsing approaches for robustness

### **Quality Assurance**
- **Data Completeness Checks**: Ensure critical fields are extracted
- **Schema Validation**: Validate against OpenAPI specification
- **Cross-reference Validation**: Check consistency across related endpoints
- **Manual Review Flags**: Mark endpoints needing human verification

This approach ensures 100% programmatic extraction with no generative components, producing a production-ready OpenAPI specification for PydanticAI integration.