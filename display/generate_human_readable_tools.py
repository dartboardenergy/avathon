#!/usr/bin/env python3
"""
generate_human_readable_tools.py (Avathon)

Generate human-friendly display names and descriptions for Avathon APM API endpoints
using an LLM with Avathon-specific domain knowledge and context.

Usage:
  python generate_human_readable_tools.py --output avathon_tools_display.json \
    --model gpt-4o-mini --temperature 0.8 --progress-every 10

Notes:
- Requires: openai>=1.0.0 (pip install openai)  
- Optional: python-dotenv, tqdm for progress bar
- Set environment variable OPENAI_API_KEY
- Generates {name, display_name, description} for all Avathon API endpoints
- Uses rich domain context for renewable energy asset management
"""

import argparse
import json
import os
import re
import sys
import time
from typing import Dict, List, Tuple
import xml.etree.ElementTree as ET

# Optional imports
try:
    from dotenv import load_dotenv  # type: ignore
except Exception:
    load_dotenv = None

try:
    from tqdm import tqdm  # type: ignore
except Exception:
    tqdm = None

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

# Add parent directory for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from toolset import AVATHON_EXECUTION_REGISTRY

# ---------------------------
# System Prompt (Avathon domain context)
# ---------------------------

SYSTEM_PROMPT = """You are an expert technical writer embedded with a renewable energy asset management team.
You help label and describe Avathon APM API endpoints for an internal tool registry.

# About Avathon APM Platform
Avathon Asset Performance Management (APM) Platform by SparkCognition provides Industrial AI solutions for renewable energy asset management. The platform offers flexibility for users to visualize, query and report using SCADA and alarm data from wind farms, solar plants, and other renewable energy installations. The APM platform emphasizes performance monitoring, predictive maintenance, and operational intelligence for renewable energy assets.

# Key Platform Capabilities
- **Asset Management**: Monitor wind turbines, solar inverters, energy storage systems
- **Performance Analytics**: Power curves, performance ratios, availability tracking, capacity factors
- **Predictive Maintenance**: Health scoring, component predictions, failure forecasting
- **SCADA Integration**: Real-time operational data, alarm processing, device monitoring
- **Operational Intelligence**: Curtailment management, grid performance, availability optimization
- **Data Access**: Raw historian data, field mappings, time-series analytics

# API Domain Structure
- **General Assets**: Subscribed renewable energy assets, device types, device monitoring
- **Performance Metrics**: Asset performance data, power curves, availability, DC loss analysis
- **Alarms & Alerts**: SCADA alarm processing, health alerts, notification management
- **Predictive Analytics**: Health scores, component predictions, forecast algorithms
- **Raw Data**: Historian queries, field mappings, time-series data aggregation
- **GPM Integration**: Grid Performance Manager for advanced analytics and reporting
- **Maintenance**: Component inventory, tickets, configuration management

# API Usage Patterns
- Endpoints commonly serve current, historic, and time-window queries
- Data types include real-time SCADA, processed analytics, and predictive insights
- Many endpoints support asset filtering, date ranges, and device-specific queries
- Some endpoints return raw time-series data, others return processed KPIs
- GPM endpoints provide specialized grid performance and plant-level analytics

# Your Job
Given a *single* API registry entry:
- `name`: the canonical tool key (e.g., "healthAlerts", "devicePowerCurve")
- `raw_description`: the technical description from the OpenAPI specification

Write TWO things:
1) A short, unique, human-readable **display_name** for this endpoint.
   - Use renewable energy and asset management terminology
   - Be concrete and active-voice (List/Get/Query/Retrieve/Monitor...)
   - Keep it under ~7 words
   - Include asset scope when relevant (Wind/Solar/Device/Site/Asset...)
   - Reflect data type (Real-time/Historic/Predicted/Raw...)
   - Must be globally UNIQUE across the entire registry

2) A friendly **description** (one sentence).
   - Natural language optimized for renewable energy professionals
   - Include context about data type (SCADA, predictive, performance metrics)
   - Mention asset types when relevant (wind turbines, solar plants, inverters)
   - Note key constraints (requires asset ID, date ranges, real-time vs historic)
   - 160 characters or fewer when possible

Return your answer ONLY in this exact XML format:

<tool>
  <display_name>...</display_name>
  <description>...</description>
</tool>

Do not include code fences, markdown, or any other fields.
Examples of good renewable energy terminology: turbines, inverters, SCADA, availability, curtailment, power curve, performance ratio, health scoring, predictive maintenance, grid performance, energy production.
"""

# ---------------------------
# User Prompt Template  
# ---------------------------

USER_PROMPT_TEMPLATE = """name: {name}
raw_description: {raw}"""

# ---------------------------
# Helper Functions
# ---------------------------

def call_llm(client, model: str, temperature: float, name: str, raw: str) -> Tuple[str, str]:
    """Call LLM to generate display name and description."""
    user_prompt = USER_PROMPT_TEMPLATE.format(name=name, raw=raw or "")
    
    for attempt in range(3):
        try:
            resp = client.chat.completions.create(
                model=model,
                temperature=temperature,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
            )
            text = resp.choices[0].message.content.strip()
            return parse_xml_payload(text)
        except Exception as e:
            print(f"LLM call failed (attempt {attempt + 1}): {e}")
            time.sleep(2)
    
    # Fallback if all attempts fail
    return f"Tool {name}", raw or ""

def parse_xml_payload(text: str) -> Tuple[str, str]:
    """Parse XML response from LLM."""
    text = text.strip()
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        # Try cleaning markdown code fences
        cleaned = re.sub(r"^```[a-zA-Z0-9]*\s*|\s*```$", "", text.strip())
        try:
            root = ET.fromstring(cleaned)
        except ET.ParseError:
            print(f"XML parsing failed for: {text[:100]}...")
            return "Unknown Tool", "Description unavailable"
    
    dn_node = root.find("display_name")
    desc_node = root.find("description")
    
    display_name = (dn_node.text or "").strip() if dn_node is not None else "Unknown Tool"
    description = (desc_node.text or "").strip() if desc_node is not None else "Description unavailable"
    
    return display_name, description

def make_unique(display_name: str, seen: Dict[str, int]) -> str:
    """Ensure display names are unique by adding suffixes if needed."""
    if display_name not in seen:
        seen[display_name] = 0
        return display_name
    
    seen[display_name] += 1
    return f"{display_name} #{seen[display_name]}"

def main():
    """Generate human-readable display names for all Avathon tools."""
    parser = argparse.ArgumentParser(description="Generate human-readable Avathon tool descriptions")
    parser.add_argument("--output", required=True, help="Output JSON file path")
    parser.add_argument("--model", default="gpt-4o-mini", help="OpenAI model to use")
    parser.add_argument("--temperature", type=float, default=0.8, help="LLM temperature")
    parser.add_argument("--progress-every", type=int, default=10, help="Progress update frequency")
    args = parser.parse_args()

    # Load environment
    if load_dotenv is not None:
        load_dotenv()

    # Validate dependencies
    if OpenAI is None:
        print("❌ Error: Install openai package: pip install openai", file=sys.stderr)
        sys.exit(2)
    
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ Error: OPENAI_API_KEY environment variable not set", file=sys.stderr)
        sys.exit(2)

    # Initialize OpenAI client
    client = OpenAI()
    
    # Get Avathon registry
    registry = AVATHON_EXECUTION_REGISTRY
    if not registry:
        print("❌ Error: AVATHON_EXECUTION_REGISTRY is empty", file=sys.stderr)
        sys.exit(1)
    
    items = sorted(registry.items(), key=lambda kv: kv[0])
    print(f"🧪 Generating human-readable descriptions for {len(items)} Avathon tools...")

    # Results tracking
    out_list: List[Dict[str, str]] = []
    seen_display: Dict[str, int] = {}

    # Progress bar
    pbar = tqdm(total=len(items), disable=(tqdm is None))
    if pbar:
        pbar.set_description("Generating Avathon tools")

    # Process each tool
    for idx, (name, raw) in enumerate(items, 1):
        display_name, description = call_llm(client, args.model, args.temperature, name, raw)
        unique_display = make_unique(display_name, seen_display)
        
        out_list.append({
            "name": name,
            "display_name": unique_display,
            "description": description
        })
        
        # Progress updates
        if args.progress_every and (idx % args.progress_every == 0 or idx == len(items)):
            pct = (idx / len(items)) * 100
            print(f"[{idx}/{len(items)}] {pct:5.1f}% last={name}")
        
        if pbar:
            pbar.update(1)
            pbar.set_postfix_str(name[:40])
        
        # Save intermediate results every 25 tools
        if idx % 25 == 0 or idx == len(items):
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(out_list, f, ensure_ascii=False, indent=2)

    # Final save and cleanup
    if pbar:
        pbar.close()
        
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(out_list, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Generated human-readable descriptions for {len(out_list)} tools")
    print(f"📄 Results saved to: {args.output}")
    
    # Show sample results
    if out_list:
        print(f"\n📋 Sample results:")
        for item in out_list[:5]:
            print(f"  • {item['name']}")
            print(f"    Display: {item['display_name']}")
            print(f"    Desc: {item['description']}")
            print()

if __name__ == "__main__":
    main()