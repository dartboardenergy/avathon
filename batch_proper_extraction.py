#!/usr/bin/env python3
"""
Batch runner for ProperReadMeExtractor across all /reference/* endpoints.

- Reads endpoint slugs from content_analysis.json (reference_links)
- Runs Selenium-based extraction sequentially (headless)
- Saves one JSON per endpoint under proper_extractions_all/

This uses only structural rules (no endpoint-specific whitelists).
"""

import json
import os
import time
from pathlib import Path
from typing import List

from proper_extractor import ProperReadMeExtractor
from refine_extractions import refine_file  # in-place refinement


def load_reference_endpoints() -> List[str]:
    with open("content_analysis.json", "r") as f:
        analysis = json.load(f)
    links = analysis.get("reference_links", [])
    slugs = []
    # Skip non-endpoint informational pages
    skip_contains = [
        "overview",              # general docs
        "overview-api",          # observed non-schema page
        "security",              # auth/how-to
        "when-interfacing",      # guide
        "how-can-i-make",        # guide
    ]
    for link in links:
            # only keep /reference/* that are not informational
        if (
            isinstance(link, str)
            and link.startswith("/reference/")
            and not any(s in link for s in skip_contains)
        ):
            slugs.append(link)
    # Normalize and uniquify
    seen = set()
    unique = []
    for s in slugs:
        if s not in seen:
            seen.add(s)
            unique.append(s)
    return unique


def safe_name(slug: str) -> str:
    return slug.strip("/").replace("/", "_").replace("-", "_")


def main():
    # Optional single-endpoint override via env
    single = os.environ.get("SINGLE_SLUG")
    endpoints = [single] if single else load_reference_endpoints()
    out_dir = Path("proper_extractions_all")
    out_dir.mkdir(exist_ok=True)

    print(f"📋 Running proper extraction for {len(endpoints)} endpoints...")
    successes = 0
    failures = 0

    for idx, slug in enumerate(endpoints, 1):
        print(f"\n[{idx}/{len(endpoints)}] {slug}")
        name = safe_name(slug)
        out_path = out_dir / f"{name}.json"
        try:
            extr = ProperReadMeExtractor(slug)
            result = extr.run_extraction()
            if result:
                with open(out_path, "w") as f:
                    json.dump(result, f, indent=2)
                print(f"  ✅ Saved: {out_path}")
                # In-place refinement: clean descriptions and required flags
                try:
                    refine_file(out_path, out_path)
                    print("  ✨ Refined in-place")
                except Exception as e:
                    print(f"  ⚠️ Refinement skipped: {e}")
                # Cleanup legacy duplicate saved by extractor (if any)
                legacy = out_dir / f"proper_extraction__{safe_name(slug)}.json"
                if legacy.exists():
                    try:
                        legacy.unlink()
                        print(f"  🧹 Removed legacy file: {legacy.name}")
                    except Exception:
                        pass
                successes += 1
            else:
                print("  ❌ No result returned")
                failures += 1
        except Exception as e:
            print(f"  ❌ Error: {e}")
            failures += 1
        # gentle pacing to avoid rate limits
        time.sleep(0.5)

    print("\n🎉 Batch complete")
    print(f"  ✅ Successes: {successes}")
    print(f"  ❌ Failures : {failures}")
    print(f"  📁 Output   : {out_dir.resolve()}")


if __name__ == "__main__":
    main()


