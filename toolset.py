#!/usr/bin/env python3
"""
Avathon Toolset for PydanticAI Integration

Creates Avathon API tools on-demand with automatic parameter handling.
Simplified from Procore - pure OpenAPI, no Postman complexity.
"""

import json
import logging
import os
from typing import Dict, Any, List, Optional
from pydantic_ai.toolsets import FunctionToolset
from pydantic_ai import RunContext, ModelRetry

from client import get_avathon_client
from utils.path_handler import PathParameterHandler
from utils.spec_parser import (
    OpenAPIExtractor,
    Operation,
    _clean_name,
    _build_input_model_from_operation,
    load_openapi_spec
)

logger = logging.getLogger(__name__)


class AvathonToolset:
    """
    Avathon toolset that creates tools on-demand for PydanticAI.
    Handles all parameter formats gracefully with simplified architecture.
    """
    
    def __init__(self):
        """Initialize by loading operation definitions."""
        self._operations_by_name: Dict[str, Operation] = {}
        self._registry: Dict[str, str] = {}
        self._load_operations()
    
    def _load_operations(self):
        """Load all operation definitions from OpenAPI spec."""
        try:
            # Load from S3 first, fall back to local file
            oas_spec = self._load_spec_file('avathon_OAS.json', 'avathon_OAS.json')
            
            # Extract operations from OpenAPI spec only (no Postman)
            oas_ops = list(OpenAPIExtractor(oas_spec).iter_operations())
            
            # Build operations registry
            for op in oas_ops:
                tool_name = _clean_name(op.name)
                self._operations_by_name[tool_name] = op
                self._registry[tool_name] = op.description or f"{op.method} {op.path_template}"
            
            logger.info(f"Loaded {len(self._operations_by_name)} Avathon operations")
            
        except Exception as e:
            logger.error(f"Failed to load Avathon operations: {e}")
            self._operations_by_name = {}
            self._registry = {}
    
    def _load_spec_file(self, s3_filename: str, local_filename: str) -> dict:
        """
        Load spec file from S3 if available, otherwise from local filesystem.
        
        Args:
            s3_filename: Filename in S3 bucket (e.g., 'avathon_OAS.json')
            local_filename: Filename in local specs directory
            
        Returns:
            Parsed JSON spec
        """
        import os
        
        # First try S3
        try:
            import boto3
            from botocore.exceptions import NoCredentialsError, ClientError
            
            s3_client = boto3.client('s3')
            s3_bucket = os.getenv('S3_BUCKET_NAME')
            s3_key = f'Joule/mcp/avathon/{s3_filename}'
            
            logger.info(f"Attempting to load spec from S3: s3://{s3_bucket}/{s3_key}")
            response = s3_client.get_object(Bucket=s3_bucket, Key=s3_key)
            content = response['Body'].read()
            spec = json.loads(content)
            logger.info(f"Successfully loaded {s3_filename} from S3")
            return spec
            
        except (NoCredentialsError, ClientError) as e:
            logger.info(f"S3 load failed ({type(e).__name__}), falling back to local file")
        except ImportError:
            logger.info("boto3 not installed, using local file")
        except Exception as e:
            logger.warning(f"Unexpected error loading from S3: {e}, falling back to local file")
        
        # Fall back to local file
        base_dir = os.path.dirname(__file__)
        local_path = os.path.join(base_dir, 'specs', local_filename)
        logger.info(f"Loading spec from local file: {local_path}")
        
        with open(local_path, 'r') as f:
            spec = json.load(f)
        logger.info(f"Successfully loaded {local_filename} from local filesystem")
        return spec
    
    def get_available_tools(self) -> Dict[str, str]:
        """Get all available tool names and descriptions."""
        return self._registry.copy()
    
    def get_registry(self) -> Dict[str, str]:
        """Get tool registry for discovery."""
        return self._registry.copy()
    
    def get_tools(
        self,
        search_terms: Optional[List[str]] = None,
        categories: Optional[List[str]] = None,
        methods: Optional[List[str]] = None,
        limit: int = 100
    ) -> Dict[str, str]:
        """
        Search and filter tools for discovery.
        
        Used by PlanningJoule to find relevant tools.
        
        Args:
            search_terms: Terms to search in tool names and descriptions
            categories: Filter by API categories (matches against tags)
            methods: Filter by HTTP methods (GET, POST, etc.)
            limit: Maximum number of results
            
        Returns:
            Dict mapping tool names to descriptions
        """
        results = {}
        
        for tool_name, description in self._registry.items():
            if len(results) >= limit:
                break
            
            # Apply search filter
            if search_terms:
                text = f"{tool_name} {description}".lower()
                if not any(term.lower() in text for term in search_terms):
                    continue
            
            # Apply method filter
            if methods:
                op = self._operations_by_name.get(tool_name)
                if op and op.method not in [m.upper() for m in methods]:
                    continue
            
            # Apply category filter (match against tags)
            if categories:
                op = self._operations_by_name.get(tool_name)
                if op:
                    op_tags = [tag.lower() for tag in op.tag_path]
                    if not any(cat.lower() in op_tags for cat in categories):
                        continue
            
            results[tool_name] = description
        
        return results
    
    def get_tool_schema(self, tool_name: str) -> Dict[str, Any]:
        """
        Get schema for a specific tool.
        
        Used by PlanningJoule to understand tool parameters.
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            Schema dictionary with tool details
        """
        if tool_name not in self._operations_by_name:
            return {"error": f"Tool '{tool_name}' not found"}
        
        op = self._operations_by_name[tool_name]
        
        return {
            "name": tool_name,
            "description": op.description or f"{op.method} {op.path_template}",
            "method": op.method,
            "path": op.path_template,
            "tags": op.tag_path,
            "parameters": [
                {
                    "name": p.get("name"),
                    "in": p.get("in"),
                    "required": p.get("required", False),
                    "type": p.get("schema", {}).get("type", "string"),
                    "description": p.get("description", "")
                }
                for p in op.parameters
            ],
            "has_request_body": op.request_body_schema is not None
        }
    
    def create_toolset(self, tool_names: List[str]) -> FunctionToolset:
        """
        Create a toolset with exactly the specified tools.
        
        Args:
            tool_names: List of tool names to include
            
        Returns:
            FunctionToolset with only the requested tools
        """
        toolset = FunctionToolset()
        created = []
        missing = []
        
        for tool_name in tool_names:
            if tool_name not in self._operations_by_name:
                missing.append(tool_name)
                logger.warning(f"Tool '{tool_name}' not found in registry")
                continue
            
            op = self._operations_by_name[tool_name]
            tool_func = self._create_tool_function(op)
            toolset.add_function(tool_func)
            created.append(tool_name)
        
        logger.info(f"Created toolset: {len(created)} tools created, {len(missing)} not found")
        if missing:
            logger.warning(f"Missing tools: {missing}")
            
        return toolset
    
    def _create_tool_function(self, op: Operation):
        """
        Create a tool function with automatic parameter handling.
        """
        tool_name = _clean_name(op.name)
        InputModel = _build_input_model_from_operation(op)
        
        async def tool_func(ctx: RunContext[Any], input_data: InputModel) -> Dict[str, Any]:
            """
            Execute Avathon API operation.
            
            Args:
                ctx: PydanticAI run context
                input_data: Validated input parameters for the API operation
            """
            try:
                client = get_avathon_client()
                
                # Convert Pydantic model to dict for processing
                kwargs = input_data.model_dump(exclude_none=True)
                
                # Use parameter handler for path substitution
                path, missing = PathParameterHandler.substitute_parameters(
                    op.path_template,
                    kwargs,
                    snake_case_keys=False  # We don't use snake_case anymore
                )
                
                if missing:
                    raise ModelRetry(f"Missing required path parameters: {', '.join(missing)}. Please provide values for: {missing}")
                
                # Validate that all path parameters were substituted
                is_valid, remaining = PathParameterHandler.validate_path(path)
                if not is_valid:
                    raise ModelRetry(f"Failed to substitute all parameters in {op.name}. Unresolved: {', '.join(remaining)}")
                
                # Separate parameters by type
                query_params = {}
                request_headers = {}
                request_body = kwargs.pop("body", None)
                extra_headers = kwargs.pop("extra_headers", None)
                
                # Process operation parameters
                for param in op.parameters:
                    param_name = param.get("name")
                    clean_name = _clean_name(param_name)
                    param_in = param.get("in")
                    
                    if clean_name in kwargs:
                        value = kwargs[clean_name]
                        if value is not None:
                            if param_in == "query":
                                query_params[param_name] = value
                            elif param_in == "header":
                                request_headers[param_name] = str(value)
                            # path parameters already handled above
                
                # Add extra headers if provided
                if extra_headers:
                    request_headers.update(extra_headers)
                
                # Make the API request
                response = await client.request(
                    method=op.method,
                    path=path,
                    params=query_params if query_params else None,
                    json_body=request_body,
                    headers=request_headers if request_headers else None
                )
                
                # Use httpx error handling with ModelRetry
                try:
                    response.raise_for_status()
                    
                    # Success - return the data
                    try:
                        return response.json()
                    except:
                        return {"data": response.text, "status_code": response.status_code}
                        
                except Exception as http_error:
                    import httpx
                    
                    if isinstance(http_error, httpx.HTTPStatusError):
                        status = http_error.response.status_code
                        
                        if status == 401:
                            raise ModelRetry("Authentication failed (401). Please check your AVATHON_API_KEY.")
                        elif status == 403:
                            raise ModelRetry(f"Access denied (403). You may not have permission for this resource in {op.name}.")
                        elif status == 404:
                            raise ModelRetry(f"Resource not found (404). Please verify the parameters are correct for {op.name}.")
                        elif status == 400:
                            try:
                                error_data = http_error.response.json()
                                error_msg = error_data.get('message', 'Bad request')
                            except:
                                error_msg = "Bad request"
                            raise ModelRetry(f"Invalid request (400): {error_msg}. Please check your parameters for {op.name}.")
                        elif status >= 500:
                            raise ModelRetry(f"Avathon server error ({status}). The service may be temporarily unavailable.")
                        else:
                            raise ModelRetry(f"API error ({status}) for {op.name}. Please check your request.")
                    else:
                        # Re-raise other HTTP errors as ModelRetry
                        raise ModelRetry(f"HTTP error for {op.name}: {str(http_error)}")
                
            except ModelRetry:
                # Re-raise ModelRetry exceptions (they contain retry instructions)
                raise
            except Exception as e:
                # For unexpected errors, use ModelRetry with helpful message
                raise ModelRetry(f"Tool execution failed for {op.name}: {str(e)}. Please check your parameters and try again.")
        
        # Set function metadata for PydanticAI
        tool_func.__name__ = tool_name
        tool_func.__doc__ = f"{op.description}\n\nMethod: {op.method}\nPath: {op.path_template}"
        
        # CRITICAL: Set annotations so PydanticAI can extract parameter schema
        tool_func.__annotations__ = {
            'ctx': RunContext[Any],
            'input_data': InputModel,
            'return': Dict[str, Any]
        }
        
        return tool_func


# Export registry for display tools (Phase 6)
AVATHON_EXECUTION_REGISTRY = {}

def _initialize_registry():
    """Initialize the execution registry."""
    try:
        toolset = AvathonToolset()
        global AVATHON_EXECUTION_REGISTRY
        AVATHON_EXECUTION_REGISTRY = toolset.get_available_tools()
    except Exception as e:
        logger.error(f"Failed to initialize registry: {e}")
        AVATHON_EXECUTION_REGISTRY = {}

# Initialize registry on import
_initialize_registry()