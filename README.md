# Avathon API Toolset

PydanticAI toolset for the Avathon Asset Performance Management (APM) API. Converts OpenAPI 3.0.0 specifications into working PydanticAI tools for renewable energy asset management.

## Overview

This toolset provides programmatic access to Avathon's renewable energy asset management capabilities, including:

- **Asset Management**: Wind turbines, solar plants, energy storage systems
- **Performance Monitoring**: Power curves, availability tracking, performance ratios
- **Predictive Maintenance**: Health scores, component predictions, SCADA alarms
- **Operational Intelligence**: Real-time monitoring, curtailment management, forecasting
- **Raw Data Access**: Historian queries, field mappings, time-series analytics

## Features

- **54 API Endpoints**: Complete coverage of Avathon APM API
- **Type-Safe Parameters**: Automatic Pydantic model generation from OpenAPI spec
- **Authentication**: Secure API key-based access (`x-api-key` header)
- **Error Handling**: PydanticAI `ModelRetry` for agent retry logic
- **Tool Discovery**: Search, filter, and schema introspection capabilities
- **Human-Readable Names**: LLM-generated friendly tool descriptions

## Quick Start

```python
from toolset import AvathonToolset

# Initialize toolset
toolset = AvathonToolset()

# Get available tools
tools = toolset.get_available_tools()
print(f"Available: {len(tools)} tools")

# Create PydanticAI toolset for specific tools
pydantic_tools = toolset.create_toolset(['assets', 'healthAlerts', 'alarms'])

# Search for tools
health_tools = toolset.get_tools(search_terms=['health'])
wind_tools = toolset.get_tools(search_terms=['wind', 'turbine'])
```

## Authentication

Set your Avathon API key in `.env`:
```
AVATHON_API_KEY=your_api_key_here
```

## Testing

Run the comprehensive test suite:
```bash
python tests/run_tests.py
```

Individual test phases:
- `python tests/test_client.py` - API authentication
- `python tests/test_parser.py` - OpenAPI spec parsing  
- `python tests/test_toolset.py` - Tool generation
- `python tests/test_parameters.py` - Parameter handling
- `python tests/test_full_coverage.py` - All 54 endpoints
- `python tests/test_complete_validation.py` - Registry & schema validation

## Architecture

- **`client.py`**: Global API authentication and HTTP client
- **`toolset.py`**: Main toolset class with tool generation
- **`utils/spec_parser.py`**: OpenAPI specification parser
- **`utils/path_handler.py`**: URL parameter substitution
- **`display/`**: Human-readable tool name generation
- **`tests/`**: Comprehensive validation suite

## Integration

This toolset is designed for integration into `dartboard/src/tools/avathon/` alongside other API toolsets (procore, pharos). The structure follows the established pattern for seamless integration.

## Generated Tools

Human-readable tool names and descriptions are available in `display/avathon_tools_display.json` (generated via OpenAI with domain-specific context).

Examples:
- `assets` → "Retrieve Subscribed Asset Data"  
- `healthAlerts` → "Retrieve Health Alerts"
- `devicePowerCurve` → "Retrieve Device Power Curve"
- `alarms` → "Retrieve SCADA Alarms Data"