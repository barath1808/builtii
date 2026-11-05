"""Load the human-readable prompt templates used by the actual API requests."""
import hashlib
import json
from pathlib import Path
from importlib.resources import files
from pipeline.validator import PAGE_SCHEMA

TEMPLATES = Path(str(files("prompts")))
SYSTEM = (TEMPLATES / "system.md").read_text(encoding="utf-8").strip()
RULES = (TEMPLATES / "shared_rules.md").read_text(encoding="utf-8")


def fingerprint():
    digest = hashlib.sha256()
    for path in sorted(TEMPLATES.glob("*.md")):
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def prompt(stage, page, total):
    names = {"ai1": "construction_takeoff_prompt.md", "ai2": "ai2_audit_prompt.md"}
    if stage not in names:
        raise ValueError("Unknown extraction stage")
    role = (TEMPLATES / names[stage]).read_text(encoding="utf-8").strip()
    return f"{role}\nPage {page} of {total}. Set page={page}.\n{RULES}\nStrict output schema:\n{json.dumps(PAGE_SCHEMA)}"
