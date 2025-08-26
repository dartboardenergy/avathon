#!/usr/bin/env python3
"""
Avathon OpenAPI Spec Parser - Simplified from Procore

Converts OpenAPI 3.0.0 specification into Operation objects for toolset creation.
No Postman complexity - pure OAS only.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

from pydantic import BaseModel, create_model, Field
from pydantic_ai import RunContext

# =========================
#  Core operation model
# =========================
class Operation(BaseModel):
    """Represents a single API operation from OpenAPI spec."""
    name: str
    method: str
    path_template: str
    tag_path: List[str] = Field(default_factory=list)
    description: str = ""
    parameters: List[Dict[str, Any]] = Field(default_factory=list)  # from OAS: name,in,required,schema,description
    request_body_schema: Optional[Dict[str, Any]] = None           # OAS JSON schema, if any


# =========================
#  OpenAPI extractor
# =========================
class OpenAPIExtractor:
    """Extract operations from OpenAPI 3.0.0 specification."""
    
    def __init__(self, oas: Dict[str, Any]):
        self.oas = oas

    def _schema_to_field(self, name: str, schema: Dict[str, Any], required: bool) -> Tuple[Any, Any]:
        """Convert OpenAPI schema to Python type for Pydantic model."""
        typ: Any = Any
        desc = schema.get("description", "")
        fmt = schema.get("format")
        t = schema.get("type")
        
        # Basic type mapping
        if t == "string":
            typ = str
        elif t == "integer":
            typ = int
        elif t == "number":
            typ = float
        elif t == "boolean":
            typ = bool
        elif t == "array":
            items = schema.get("items", {})
            item_type, _ = self._schema_to_field(f"{name}_item", items, False)
            typ = List[item_type]  # type: ignore
        elif t == "object":
            # Keep it generic for now; can be expanded to nested models.
            typ = Dict[str, Any]
        
        # Create field with proper optional handling
        default = Field(default=... if required else None, description=desc)
        return typ if required else Optional[typ], default  # type: ignore

    def iter_operations(self) -> Iterable[Operation]:
        """Extract all operations from OpenAPI spec."""
        oas = self.oas
        paths = oas.get("paths", {}) or {}
        global_params = oas.get("components", {}).get("parameters", {})
        
        for path, methods in paths.items():
            for method, op in methods.items():
                if method.upper() not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
                    continue
                    
                op_id = op.get("operationId") or f"{method}_{path}"
                tags = op.get("tags") or []
                description = (op.get("description") or op.get("summary") or "").strip()

                # Parameters (inline + $ref)
                params: List[Dict[str, Any]] = []
                for p in op.get("parameters", []):
                    if "$ref" in p:
                        ref = p["$ref"].split("/")[-1]
                        p = global_params.get(ref, {})
                    params.append({
                        "name": p.get("name"),
                        "in": p.get("in"),
                        "required": bool(p.get("required", False)),
                        "schema": p.get("schema", {}),
                        "description": p.get("description", ""),
                    })

                # Request body
                body_schema = None
                rb = op.get("requestBody")
                if rb:
                    if "$ref" in rb:
                        # Could resolve component requestBodies here; keeping simple
                        rb = rb  # unresolved
                    content = rb.get("content", {})
                    if "application/json" in content:
                        body_schema = content["application/json"].get("schema")

                yield Operation(
                    name=op_id,
                    method=method.upper(),
                    path_template=path,
                    tag_path=tags,
                    description=description,
                    parameters=params,
                    request_body_schema=body_schema,
                )


# =========================
#  Helper for dynamic model creation
# =========================
def _clean_name(s: str) -> str:
    """Clean parameter name for Python (minimal changes)."""
    # Only handle edge cases like names starting with digits
    if re.match(r"^\d", s):
        s = "param_" + s
    return s


def _build_input_model_from_operation(op: Operation) -> type[BaseModel]:
    """Build a Pydantic model for validating tool inputs."""
    fields: Dict[str, Tuple[Any, Any]] = {}

    # Map parameters
    for p in op.parameters:
        name = p.get("name")
        where = p.get("in")
        required = bool(p.get("required"))
        schema = p.get("schema") or {}
        desc = p.get("description") or ""
        
        # Basic type mapping
        t = schema.get("type")
        py_type: Any = str
        if t == "integer":
            py_type = int
        elif t == "number":
            py_type = float
        elif t == "boolean":
            py_type = bool
        elif t == "array":
            py_type = List[Any]
        elif t == "object":
            py_type = Dict[str, Any]
            
        if not required:
            py_type = Optional[py_type]  # type: ignore
            
        default = Field(default=... if required else None, description=f"[{where}] {desc}".strip())
        fields[_clean_name(name)] = (py_type, default)

    # Request body
    if op.request_body_schema is not None:
        fields["body"] = (Optional[Dict[str, Any]], Field(default=None, description="JSON request body"))

    # Extra headers for flexibility
    fields["extra_headers"] = (Optional[Dict[str, str]], Field(default=None, description="Optional extra headers"))

    # Pagination hint if page/per_page exists
    param_names = {p.get("name") for p in op.parameters}
    if {"page", "per_page"} & param_names or ("cursor" in param_names):
        fields["include_all"] = (Optional[bool], Field(default=False, description="If True, fetch all pages/cursor results."))

    return create_model(f"{_clean_name(op.name)}_Input", **fields)  # type: ignore


# =========================
#  Utility functions
# =========================
def load_openapi_spec(file_path: str) -> Dict[str, Any]:
    """Load OpenAPI specification from JSON file."""
    with open(file_path, 'r') as f:
        return json.load(f)