#!/usr/bin/env python3
"""
SmartApply — Sync profile data from Google Sheets.

Reads the profileData sheet and stores all Key/Value pairs
into the SmartApply SQLite profile.

Usage:
    python3 sync_profile.py

Requires:
    - service_account.json in the project root
    - Google Sheets API access for the service account
"""

import json
import sys
import os
import urllib.request

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from google.oauth2.service_account import Credentials
from google.auth.transport.requests import Request
from app.config import get_settings
from app.db.database import init_db, set_profile, get_all_profile


SHEET_ID = "11olBJbiekeJqaM0wo8ezrWg3QYpVTQNwffqg2-ZIMpk"
SERVICE_ACCOUNT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "service_account.json")


def fetch_profile_from_sheets() -> dict:
    """Fetch profile Key/Value pairs from Google Sheets."""
    print("Authenticating with Google Sheets API...")
    creds = Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
    )
    creds.refresh(Request())

    range_name = "profileData!A:B"
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}/values/{range_name}"

    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {creds.token}")

    print(f"Fetching data from sheet...")
    resp = urllib.request.urlopen(req, timeout=30)
    data = json.loads(resp.read())

    values = data.get("values", [])
    profile = {}
    for row in values[1:]:  # skip header
        if len(row) >= 2 and row[0].strip() and row[1].strip():
            profile[row[0].strip()] = row[1].strip()

    return profile


def ingest_profile(profile: dict) -> None:
    """Store profile data into SmartApply SQLite database."""
    settings = get_settings()
    init_db(settings.sqlite_db_path)

    for key, value in profile.items():
        set_profile(key, value)
        print(f"  ✅ {key}: {value[:80]}{'...' if len(value) > 80 else ''}")


if __name__ == "__main__":
    print("=" * 60)
    print("SmartApply — Profile Sync from Google Sheets")
    print("=" * 60)

    try:
        profile = fetch_profile_from_sheets()
        print(f"\nFound {len(profile)} profile fields:\n")
        ingest_profile(profile)
        print(f"\n✅ Profile synced successfully! ({len(profile)} fields)")
        print("\nCurrent profile:")
        print(json.dumps(get_all_profile(), indent=2))
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
