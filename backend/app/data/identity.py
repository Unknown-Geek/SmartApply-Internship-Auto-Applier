"""backend/app/data/identity.py — Loads applicant identity from CSV into memory.
Also accepts structured JSON profiles pushed directly from n8n."""
import csv
import logging
import os
from typing import Any, Optional

import pandas as pd

logger = logging.getLogger(__name__)

# Global identity store
_identity: Optional[dict] = None


def load_identity(csv_path: Optional[str] = None) -> dict:
    """Load applicant identity from CSV. Returns dict of field → value."""
    global _identity

    path = csv_path or os.getenv("IDENTITY_CSV_PATH", "/app/data/identity/identity.csv")

    if not os.path.exists(path):
        raise FileNotFoundError(f"Identity CSV not found at: {path}")

    df = pd.read_csv(path)

    # Expect columns: field, value  (e.g. "first_name", "Shravan")
    if "field" in df.columns and "value" in df.columns:
        identity = dict(zip(df["field"], df["value"]))
    else:
        # Fallback: single-row CSV where column names are field names
        identity = df.iloc[0].to_dict()

    _identity = identity
    logger.info(f"Loaded identity: {list(identity.keys())}")
    return identity


def get_identity() -> dict:
    """Return cached identity or load from disk."""
    global _identity
    if _identity is None:
        _identity = load_identity()
    return _identity


def get_identity_text() -> str:
    """Return identity as a formatted string for injection into LLM prompt."""
    identity = get_identity()
    lines = [f"  {k}: {v}" for k, v in identity.items()]
    return "Applicant Identity Data:\n" + "\n".join(lines)


def _flatten(obj: Any, prefix: str = "") -> dict:
    """
    Recursively flatten a nested dict/list into dot-notation key→value pairs.
    Lists of dicts are indexed (projects.0.name, projects.1.name).
    Lists of scalars are joined with ', '.
    """
    out = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            full_key = f"{prefix}.{k}" if prefix else str(k)
            out.update(_flatten(v, full_key))
    elif isinstance(obj, list):
        if all(isinstance(i, dict) for i in obj):
            for idx, item in enumerate(obj):
                out.update(_flatten(item, f"{prefix}.{idx}"))
        else:
            # scalar list → comma-joined string
            out[prefix] = ", ".join(str(i) for i in obj)
    else:
        if prefix:
            out[prefix] = str(obj) if obj is not None else ""
    return out


def ingest_profile_json(profile: dict, csv_path: Optional[str] = None) -> dict:
    """
    Accept a rich JSON profile from n8n (nested personal/skills/projects/…),
    flatten it to a key→value dict, persist as CSV, and hot-reload _identity.

    Returns the flattened identity dict.
    """
    global _identity

    flat = _flatten(profile)
    _identity = flat
    logger.info(f"Profile ingested from n8n — {len(flat)} fields")

    # Persist to CSV so the identity survives container restarts
    dest = csv_path or os.getenv("IDENTITY_CSV_PATH", "/app/data/identity/identity.csv")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    try:
        with open(dest, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["field", "value"])
            for field, value in flat.items():
                writer.writerow([field, value])
        logger.info(f"Identity CSV updated at {dest} ({len(flat)} rows)")
    except Exception as exc:
        logger.warning(f"Could not persist identity CSV: {exc}")

    return flat
