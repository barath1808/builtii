"""Shared runtime settings. Credentials stay in the process environment."""
import os
from pathlib import Path

DEFAULT_MODEL = "gemini-2.5-pro"
MAX_PDF_BYTES = 100 * 1024 * 1024
MAX_PDF_PAGES = 200


def api_key():
    return os.environ.get("GEMINI_API_KEY", "").strip()


def models():
    extractor = os.environ.get("GEMINI_MODEL", DEFAULT_MODEL)
    return {"ai1": extractor, "ai2": os.environ.get("GEMINI_AUDIT_MODEL", extractor)}


def output_dir():
    return Path(os.environ.get("BUILTII_DATA_DIR", "output"))
