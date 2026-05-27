"""
Run after `rsconnect write-manifest` to:
  1. Strip large binary directories from the bundle (rra_pdfs/, etc.)
  2. Pin the Python version to 3.11.9 (what Posit Connect has installed)
"""
import json

EXCLUDE_PREFIXES = [
    "rras/rra_pdfs/",
    "public_documents_filtered.csv",
]

TARGET_PYTHON = "3.11.9"

with open("manifest.json") as f:
    m = json.load(f)

before = len(m["files"])
m["files"] = {
    k: v for k, v in m["files"].items()
    if not any(k.startswith(p) for p in EXCLUDE_PREFIXES)
}
removed = before - len(m["files"])

m["python"]["version"] = TARGET_PYTHON

with open("manifest.json", "w") as f:
    json.dump(m, f, indent=2)

print(f"manifest.json patched: removed {removed} file(s), Python → {TARGET_PYTHON}")
