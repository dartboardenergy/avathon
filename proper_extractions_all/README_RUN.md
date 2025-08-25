# How to regenerate specs (extraction + refinement)

This folder is the canonical output for endpoint specs. The batch runner now does extraction and refinement in one go (no separate folder is needed).

Run for all endpoints (Composio env):

```bash
source /opt/anaconda3/etc/profile.d/conda.sh && conda activate Composio
python ../batch_proper_extraction.py
```

Run for a single endpoint:

```bash
source /opt/anaconda3/etc/profile.d/conda.sh && conda activate Composio
SINGLE_SLUG=/reference/dcloss python ../batch_proper_extraction.py
```

What it does:
- Extracts each /reference/* endpoint with `proper_extractor.py`
- Immediately refines the just-written JSON in place via `refine_extractions.py` (cleans concatenated descriptions and sets required flags when clearly present)

Outputs:
- One JSON per endpoint here in `proper_extractions_all/`
