#!/usr/bin/env python3
"""
Refine extracted ReadMe.io specs by cleaning concatenated description fields.

Behavior
- Reads each `reference_*.json` in `proper_extractions_all/`.
- Cleans description strings that look like "asset_idintegerrequired..." by:
  - Removing the repeated parameter/property name at the start
  - Removing the type token (string|integer|number|boolean|object|array)
  - Detecting "required" / "optional" tokens and setting required flag (for query params)
  - Preserving any trailing helpful text (e.g., "Defaults to production")
- Applies to:
  - `query_parameters` entries
  - Response schema properties under `response_schemas` (all status codes)
- Writes refined JSONs to `proper_extractions_refined/` with the same filenames.

Notes
- The script is idempotent; safe to rerun.
- It avoids changing structure, only normalizes descriptions and (for query params)
  may adjust the `required` boolean based on parsed tokens.
"""

from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Dict, List, Optional, Tuple


PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "proper_extractions_all"
DST_DIR = PROJECT_ROOT / "proper_extractions_refined"


TYPE_TOKENS = ("string", "integer", "number", "boolean", "object", "array")


def _strip_prefix(text: str, prefix: str) -> Tuple[str, bool]:
    """Remove prefix from start of text if present (case-sensitive)."""
    if text.startswith(prefix):
        return text[len(prefix) :], True
    return text, False


def _strip_prefix_ci(text: str, prefix: str) -> Tuple[str, bool]:
    """Remove prefix from start of text if present (case-insensitive)."""
    if text.lower().startswith(prefix.lower()):
        return text[len(prefix) :], True
    return text, False


def _normalize_spaces(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def parse_description(name: str, type_hint: Optional[str], raw: Optional[str]) -> Tuple[Optional[str], Optional[bool]]:
    """Parse a concatenated description string.

    Returns (clean_description, required_flag) where required_flag is:
      - True/False if we detected an explicit token
      - None if not detected
    """
    if not raw or not isinstance(raw, str):
        return raw, None

    s = raw.strip()

    # Remove trivial "Parameter <name>" prefix
    s = re.sub(rf"(?i)^\s*parameter\s*{re.escape(name)}\b", "", s).strip()

    # Remove repeated name prefix (exact)
    s, _ = _strip_prefix(s, name)

    # Sometimes tokens are concatenated without spaces, e.g., "objectHas..."
    # After removing name, remove type token if present at start (case-insensitive)
    lowered = s.lower()
    removed_any = True
    while removed_any and s:
        removed_any = False
        # Remove known type tokens at start (even when glued to next word)
        for tok in TYPE_TOKENS:
            if lowered.startswith(tok):
                s = s[len(tok) :]
                lowered = s.lower()
                removed_any = True
                break
        # Remove explicit "required" or "optional" tokens at start
        # Track the detected requirement
        if lowered.startswith("required"):
            s = s[len("required") :]
            lowered = s.lower()
            required_detected = True
            # Return required flag via outer scope by storing on function attribute
            # We'll instead track via local and return later; set flag here
            # We'll manage in outer logic below
            # stop additional loop to avoid removing meaningful text repeatedly
        elif lowered.startswith("optional"):
            s = s[len("optional") :]
            lowered = s.lower()
        # Leave loop condition controlled by type token removal

    # At this point, s may still contain standalone tokens "required" or "optional"
    req_flag: Optional[bool] = None
    # Extract first occurrence and remove it
    m = re.match(r"(?i)\s*(required|optional)\b", s)
    if m:
        tok = m.group(1).lower()
        s = s[m.end() :]
        req_flag = True if tok == "required" else False

    # If we didn't detect above, also look for glued forms like "requiredDefaults"
    if req_flag is None:
        if s.lower().startswith("required"):
            s = s[len("required") :]
            req_flag = True
        elif s.lower().startswith("optional"):
            s = s[len("optional") :]
            req_flag = False

    clean = _normalize_spaces(s)
    if not clean:
        clean = None
    return clean, req_flag


def refine_query_parameters(params: List[Dict]) -> List[Dict]:
    refined: List[Dict] = []
    for p in params:
        p2 = deepcopy(p)
        name = p2.get("name", "")
        type_hint = p2.get("type")
        desc = p2.get("description")
        clean_desc, req_flag = parse_description(name, type_hint, desc)
        if clean_desc is not None:
            p2["description"] = clean_desc
        else:
            # Remove empty, unhelpful description field
            p2.pop("description", None)
        if req_flag is not None:
            # Only set if we parsed an explicit marker
            p2["required"] = bool(req_flag)
        refined.append(p2)
    return refined


def refine_schema_node(prop_name: str, node: Dict) -> None:
    """Refine a schema node in-place.

    We only alter description text; structure and types remain unchanged.
    """
    # Refine this node's description if present
    if "description" in node and isinstance(node["description"], str):
        type_hint = node.get("type")
        clean_desc, _ = parse_description(prop_name, type_hint, node.get("description"))
        if clean_desc is not None:
            node["description"] = clean_desc
        else:
            node.pop("description", None)

    # Recurse into object properties
    props = node.get("properties")
    if isinstance(props, dict):
        for child_name, child_node in list(props.items()):
            if isinstance(child_node, dict):
                refine_schema_node(child_name, child_node)

    # Recurse into array items
    if node.get("type") == "array" and isinstance(node.get("items"), dict):
        refine_schema_node(prop_name, node["items"])  # prop_name context retained


def refine_response_schemas(schemas: Dict) -> Dict:
    refined = deepcopy(schemas)
    for code, schema in refined.items():
        if isinstance(schema, dict):
            # top-level schema has a synthetic name context
            refine_schema_node(f"response_{code}", schema)
    return refined


def refine_file(src_path: Path, dst_path: Path) -> None:
    data = json.loads(src_path.read_text(encoding="utf-8"))
    out = deepcopy(data)

    # Query parameters
    if isinstance(out.get("query_parameters"), list):
        out["query_parameters"] = refine_query_parameters(out["query_parameters"]) 

    # Response schemas
    if isinstance(out.get("response_schemas"), dict):
        out["response_schemas"] = refine_response_schemas(out["response_schemas"])

    dst_path.parent.mkdir(parents=True, exist_ok=True)
    dst_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    files = sorted(SRC_DIR.glob("reference_*.json"))
    if not files:
        print(f"No input files in {SRC_DIR}")
        return
    print(f"Refining {len(files)} files → {DST_DIR}")
    for src in files:
        dst = DST_DIR / src.name
        try:
            refine_file(src, dst)
            print(f"  ✓ {src.name}")
        except Exception as e:
            print(f"  ✗ {src.name}: {e}")


if __name__ == "__main__":
    main()


