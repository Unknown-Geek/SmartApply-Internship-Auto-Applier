"""backend/app/data/identity.py — Loads applicant identity from CSV into memory."""
import os
import logging
from typing import Optional
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
