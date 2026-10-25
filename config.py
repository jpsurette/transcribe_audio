"""
Shared settings for transcribe.py and format_dictation.py.

Directory defaults live in the repo (inputs/, outputs/raw/, outputs/cleaned/) and can be
overridden per machine in the gitignored .env file. See .env.example for the available keys.
Paths in .env may use ~ and may be relative (resolved against this repo's directory).

Precedence: command-line flag > .env / environment variable > repo default.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

SCRIPT_DIR = Path(__file__).resolve().parent

load_dotenv(SCRIPT_DIR / ".env")


def resolve_path(path: str | Path) -> Path:
    """Expand ~ and resolve relative paths against the repo directory."""
    path = Path(path).expanduser()
    return path if path.is_absolute() else SCRIPT_DIR / path


def _env_path(name: str, default: Path) -> Path:
    value = os.getenv(name)
    return resolve_path(value) if value else default


INPUTS_DIR = _env_path("TRANSCRIBE_INPUTS_DIR", SCRIPT_DIR / "inputs")
RAW_DIR = _env_path("TRANSCRIBE_RAW_DIR", SCRIPT_DIR / "outputs" / "raw")
CLEANED_DIR = _env_path("TRANSCRIBE_CLEANED_DIR", SCRIPT_DIR / "outputs" / "cleaned")
GLOSSARY_PATH = _env_path("TRANSCRIBE_GLOSSARY", SCRIPT_DIR / "glossary.txt")
