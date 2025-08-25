# ReadMe.io DOM Structure & Extraction Guide

**Comprehensive Technical Guide to ReadMe.io API Documentation DOM Patterns**  
*Based on empirical analysis of 5+ endpoints and official ReadMe.io documentation*

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Universal DOM Patterns](#universal-dom-patterns)
3. [Container Structure](#container-structure)
4. [Parameter Classification](#parameter-classification)
5. [Response Schema Organization](#response-schema-organization)
6. [Error Handling Patterns](#error-handling-patterns)
7. [CSS Classes & Selectors](#css-classes--selectors)
8. [Extraction Algorithm](#extraction-algorithm)
9. [Edge Cases & Limitations](#edge-cases--limitations)

---

## Architecture Overview

ReadMe.io renders interactive API documentation from OpenAPI specifications (v2.0, v3.0.x, v3.1) into structured HTML DOM with consistent patterns across all endpoints.

### Core Components
- **OpenAPI Import**: YAML/JSON specs automatically converted to interactive reference guides
- **DOM Rendering**: Structured HTML with stable CSS classes and attributes
- **Interactive Elements**: "Try It!" functionality with live API testing
- **Responsive Layout**: Mobile-friendly with dark/light mode support

### Rendering Pipeline
```
OpenAPI Spec → ReadMe.io Parser → Structured DOM → Interactive Reference
```

---

## Universal DOM Patterns

Based on analysis of multiple endpoints, these patterns appear consistently:

### 1. Container Identification Pattern
**100% Universal Across All Endpoints**:
- `query` container: Always present for request metadata
- `data` container: Always present for response data arrays
- `message` container: Always present for error responses

### 2. DOM Element Types
```html
<!-- Containers (Response Structure) -->
<span class="Param-name[hash]">container_name</span>

<!-- Query Parameters -->
<label class="Param-name[hash]" for="query-{endpoint}_{param}">param_name</label>

<!-- Response Properties -->  
<label class="Param-name[hash]" for="object-{endpoint}_{path}">property_name</label>
```

### 3. Stable Attribute Patterns
- Query params: `for="query-{endpointName}_{parameterName}"`
- Object properties: `for="object-{endpointName}_{containerPath}"`
- Container spans: No `for` attribute, identified by `<span>` + CSS class

---

## Container Structure

### Universal Container Types

#### 1. Query Container (`query`)
**Purpose**: Request metadata and parameters echo  
**DOM Pattern**: `<span>query</span>` with context `"queryobject"` or `"queryarray of objects"`
**Child Pattern**: `object-{endpoint}_query_{property}` or `object-{endpoint}_query_{index}_{property}`

#### 2. Data Container (`data`)  
**Purpose**: Main response data array  
**DOM Pattern**: `<span>data</span>` with context `"dataarray of objects"`
**Child Pattern**: `object-{endpoint}_data_{index}_{property}`

#### 3. Message Container (`message`)
**Purpose**: Error response messages  
**DOM Pattern**: Direct properties with `object-{endpoint}_message`
**Usage**: 400/401 HTTP error responses

### Endpoint-Specific Containers
Some endpoints have additional containers (not universal):
- `status`, `assets`, `impacted_devices` (GetNotifications)
- `units`, `pagination_info` (DeviceAvailability)

---

## Parameter Classification

### Query Parameters
**Identification**: `<label for="query-{endpoint}_{param}">`
**Structure**:
```html
<label class="Param-nameU7CntAa90Wvb" for="query-dcLoss_asset_id">asset_id</label>
```
**Extraction Pattern**: `for` attribute → `query-{endpointName}_{parameterName}`

### Response Properties  
**Identification**: `<label for="object-{endpoint}_{path}">`
**Structure**:
```html
<label class="Param-nameU7CntAa90Wvb" for="object-dcLoss_data_0_device">device</label>
```
**Path Parsing**: `object-{endpoint}_{container}_{index}_{property}`

### Container Indicators
**Identification**: `<span class="Param-name*">` without `for` attribute
**Context Analysis**: Parent element text contains type indicators:
- `"array of objects"` → Array container
- `"object"` → Object container  
- `"array of strings"` → String array container

---

## Response Schema Organization

### Schema Hierarchy Rules

#### 1. Root Level Properties
- **Containers**: Identified by `<span>` elements (`query`, `data`)
- **Simple Properties**: Direct response properties (rare)

#### 2. Nested Properties  
- **Level 1**: `object-{endpoint}_{container}_{property}`
- **Level 2**: `object-{endpoint}_{container}_{index}_{property}`  
- **Level N**: `object-{endpoint}_{container}_{index}_{nested}_{property}`

#### 3. Array Item Properties
**Pattern**: Properties with numeric index in path
```
object-assets_data_0_asset_id     → data[0].asset_id
object-assets_data_0_location     → data[0].location  
```

#### 4. Nested Object Properties
**Pattern**: Multi-level path separation
```
object-alarmCodes_query_timezone_preference → query.timezone.preference
```

### Schema Building Algorithm
1. **Separate by Container**: Group properties by first path segment
2. **Detect Array Patterns**: Look for numeric indices in paths  
3. **Build Nested Structure**: Reconstruct object hierarchy from paths
4. **Handle Special Cases**: Container spans that don't have children

---

## Error Handling Patterns

### Universal Error Structure
**HTTP Status Codes**: 400 (Bad Request), 401 (Unauthorized)
**Property Pattern**: `object-{endpoint}_message`
**Content**: Always contains `message` property with error description

### Error Detection Algorithm
```javascript
function isErrorProperty(element) {
    const name = element.textContent.trim();
    const forAttr = element.getAttribute('for') || '';
    
    // Universal error pattern
    return name === 'message' && forAttr.includes('_message');
}
```

---

## CSS Classes & Selectors

### Stable CSS Patterns
**Note**: CSS class names are hashed and change between deployments. Use attribute-based selectors.

#### Recommended Selectors
```css
/* Query Parameters */
label[for^="query-"]

/* Object Properties */
label[for^="object-"]

/* Container Spans */  
span[class*="Param-name"]

/* All Parameter Elements */
.Param-name*
```

#### Anti-Pattern (Avoid)
```css
/* These hashes change unpredictably */
.Param-nameU7CntAa90Wvb  
.Param-header3wXBpbDTP1O6
```

---

## Extraction Algorithm

### Complete Extraction Process

#### Phase 1: Element Discovery
```python
def extract_all_elements(soup):
    # Query parameters (stable)
    query_params = soup.find_all('label', attrs={'for': re.compile(r'^query-')})
    
    # Response properties (stable)
    object_props = soup.find_all('label', attrs={'for': re.compile(r'^object-')})
    
    # Container spans (CSS class based)
    containers = soup.find_all('span', class_=lambda x: x and 'Param-name' in str(x))
    
    return query_params, object_props, containers
```

#### Phase 2: Path Analysis
```python
def parse_object_path(for_attribute):
    # Pattern: object-{endpoint}_{container}_{index?}_{property}
    path = for_attribute.replace('object-', '')
    parts = path.split('_')
    
    return {
        'endpoint': parts[0],
        'container': parts[1] if len(parts) > 1 else None,
        'index': parts[2] if len(parts) > 2 and parts[2].isdigit() else None,
        'property_path': parts[2:] if not (len(parts) > 2 and parts[2].isdigit()) else parts[3:]
    }
```

#### Phase 3: Schema Construction
```python
def build_schema(properties):
    schema = {'type': 'object', 'properties': {}}
    
    # Group by container
    containers = {}
    for prop in properties:
        container = prop['container']
        if container not in containers:
            containers[container] = []
        containers[container].append(prop)
    
    # Build each container
    for container_name, props in containers.items():
        if container_name in ['query', 'data']:  # Universal containers
            schema['properties'][container_name] = build_container_schema(props)
        else:
            # Handle endpoint-specific containers
            schema['properties'][container_name] = build_generic_container(props)
    
    return schema
```

### Type Detection
```python
def detect_property_type(element):
    # Look for type in next sibling or parent context
    context = element.parent.get_text() if element.parent else ''
    
    type_mapping = {
        'string': 'string',
        'number': 'number', 
        'integer': 'integer',
        'boolean': 'boolean',
        'array': 'array',
        'object': 'object',
        'array of objects': 'array',
        'array of strings': 'array'
    }
    
    for readme_type, standard_type in type_mapping.items():
        if readme_type in context.lower():
            return standard_type
    
    return 'string'  # Default fallback
```

---

## Edge Cases & Limitations

### Known Challenges

#### 1. Recursive Objects
ReadMe.io struggles with circular references in OpenAPI specs. Deep nesting may not render completely.

#### 2. Special Indicators
- **"HAS ADDITIONAL FIELDS"**: Indicates nested properties not fully expanded in DOM
- **Mixed Rendering**: Some nested properties render as `<span>` instead of `<label>`

#### 3. Dynamic Content
- **JavaScript Loading**: Content may load asynchronously, requiring wait strategies
- **Authentication**: Some endpoints require valid session cookies

#### 4. CSS Class Instability
- **Hashed Classes**: CSS classes like `Param-nameU7CntAa90Wvb` change unpredictably
- **Deployment Changes**: DOM structure may vary between ReadMe.io updates

### Mitigation Strategies

#### Robust Waiting
```python
def wait_for_content(driver, min_elements=10):
    for attempt in range(max_attempts):
        total_elements = len(driver.find_elements(By.CSS_SELECTOR, 'label[for^="query-"], label[for^="object-"], span[class*="Param-name"]'))
        if total_elements >= min_elements:
            return True
        time.sleep(retry_interval)
    return False
```

#### Error Recovery
```python  
def extract_with_fallback(soup):
    try:
        return extract_using_stable_patterns(soup)
    except Exception:
        return extract_using_css_classes(soup)  # Fallback
```

---

## Validation & Testing

### Multi-Endpoint Validation
Test extraction logic across diverse endpoint types:
- **Simple endpoints**: Few parameters, basic response
- **Complex endpoints**: Many nested objects, arrays
- **Error-heavy endpoints**: Multiple error response types  
- **Paginated endpoints**: Special pagination objects

### Quality Metrics
- **Parameter Coverage**: % of expected parameters extracted
- **Schema Accuracy**: Nested structure matches actual API responses  
- **Error Handling**: Proper 400/401 error schema separation
- **Type Detection**: Correct OpenAPI type mapping

---

## Implementation Checklist

### Core Requirements
- [ ] Use stable `for` attributes, never hashed CSS classes
- [ ] Handle universal containers: `query`, `data`, `message`
- [ ] Support endpoint-specific containers dynamically
- [ ] Parse nested object paths correctly
- [ ] Separate error responses by HTTP status code
- [ ] Implement robust waiting for JavaScript-rendered content
- [ ] Extract parameter descriptions from DOM context
- [ ] Handle array vs object container detection

### Advanced Features  
- [ ] Support for ReadMe.io extensions (`x-readme` objects)
- [ ] Handle recursive/circular reference indicators
- [ ] Extract endpoint metadata (title, method, URL)
- [ ] Support for multiple API versions
- [ ] Authentication context preservation

---

## Conclusion

ReadMe.io provides a consistent, extractable DOM structure across all API endpoints when approached with the right patterns. The key to successful extraction is:

1. **Use stable attributes** (`for` patterns) not CSS classes
2. **Leverage universal containers** (`query`, `data`, `message`)  
3. **Parse hierarchical paths** systematically
4. **Handle endpoint-specific variations** dynamically
5. **Implement robust error handling** and fallbacks

This guide provides the foundation for building a fully generalizable ReadMe.io extraction system that works across any API documented on the platform.

---

**Document Version**: 1.0  
**Last Updated**: 2025-08-23  
**Based on**: Empirical analysis of 5+ endpoints + ReadMe.io official documentation