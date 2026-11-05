"""Shared runtime settings, loaded from .env without overriding the environment."""
import os
from pathlib import Path
from dotenv import load_dotenv


def load_environment(env_path=None):
    """Prefer the source project's .env; installed commands use the working directory."""
    project_env = Path(__file__).resolve().parent / ".env"
    selected = Path(env_path) if env_path is not None else (
        project_env if project_env.is_file() else Path.cwd() / ".env"
    )
    return load_dotenv(selected, override=False, interpolate=False, encoding="utf-8-sig")


load_environment()

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
