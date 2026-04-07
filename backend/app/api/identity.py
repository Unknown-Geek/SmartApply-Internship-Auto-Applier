"""
backend/app/api/identity.py
Endpoints for uploading and viewing the applicant identity CSV and resume PDF.
"""
import os
import shutil
from typing import Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.data.identity import _identity, get_identity, ingest_profile_json, load_identity

router = APIRouter()

IDENTITY_DIR = os.getenv("IDENTITY_DIR", "/app/data/identity")
os.makedirs(IDENTITY_DIR, exist_ok=True)


class IdentityResponse(BaseModel):
    loaded: bool
    fields: dict
    csv_path: Optional[str] = None
    resume_exists: bool = False


@router.get("/identity", response_model=IdentityResponse)
async def get_identity_info():
    """Return current loaded identity fields."""
    csv_path = os.getenv("IDENTITY_CSV_PATH", os.path.join(IDENTITY_DIR, "identity.csv"))
    resume_path = os.getenv("RESUME_PDF_PATH", os.path.join(IDENTITY_DIR, "resume.pdf"))
    try:
        identity = get_identity()
        return IdentityResponse(
            loaded=True,
            fields=identity,
            csv_path=csv_path,
            resume_exists=os.path.exists(resume_path),
        )
    except Exception:
        return IdentityResponse(loaded=False, fields={}, resume_exists=False)


@router.post("/identity/csv")
async def upload_identity_csv(file: UploadFile = File(...)):
    """Upload the applicant identity CSV file."""
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files accepted")
    dest = os.path.join(IDENTITY_DIR, "identity.csv")
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)
    # Reload identity
    try:
        identity = load_identity(dest)
        return {"uploaded": True, "fields_loaded": list(identity.keys()), "path": dest}
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"CSV loaded but parse failed: {e}")


@router.post("/identity/resume")
async def upload_resume(file: UploadFile = File(...)):
    """Upload the applicant resume PDF."""
    if not (file.filename.endswith(".pdf") or file.filename.endswith(".PDF")):
        raise HTTPException(status_code=400, detail="Only PDF files accepted")
    dest = os.path.join(IDENTITY_DIR, "resume.pdf")
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)
    size_kb = os.path.getsize(dest) // 1024
    return {"uploaded": True, "path": dest, "size_kb": size_kb}


class ProfileIngestRequest(BaseModel):
    """Body expected from n8n Identity Fetcher / Profile Sync workflows."""
    # The n8n Identity Fetcher returns a nested JSON with these top-level keys.
    # Any subset is acceptable — unknown keys are stored as-is after flattening.
    personal: Optional[dict] = None
    education_details: Optional[dict] = None
    skills: Optional[dict] = None
    links: Optional[dict] = None
    documents: Optional[dict] = None
    projects: Optional[list] = None
    experience: Optional[list] = None
    leadership: Optional[list] = None
    certifications: Optional[list] = None
    volunteering: Optional[list] = None
    # Allow arbitrary extra top-level keys from future workflow changes
    model_config = {"extra": "allow"}


@router.post("/profile/ingest/direct")
async def ingest_profile_direct(payload: ProfileIngestRequest):
    """
    Receive a structured profile JSON from n8n (Identity Fetcher / Profile Sync
    workflows) and hot-reload it as the active identity.

    The payload is flattened into dot-notation keys (e.g. `personal.Name`,
    `skills.technical`) and written to identity.csv for persistence.
    """
    try:
        # Convert to plain dict (includes extra fields via model_config)
        profile_dict = payload.model_dump(exclude_none=True)
        flat = ingest_profile_json(profile_dict)
        return {
            "ingested": True,
            "fields_loaded": len(flat),
            "preview": dict(list(flat.items())[:5]),  # first 5 for quick sanity check
        }
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Profile ingest failed: {e}")


@router.get("/profile/schema")
async def profile_schema():
    """Return the expected profile JSON shape for the n8n Identity Fetcher."""
    return {
        "description": "POST this structure to /profile/ingest/direct",
        "schema": {
            "personal": {"Name": "string", "Email": "string", "Phone": "string"},
            "education_details": {"University": "string", "Degree": "string", "CGPA": "string"},
            "skills": {
                "technical": ["list of strings"],
                "soft": ["list of strings"],
                "ai_llm": ["list of strings"],
            },
            "links": {"GitHub": "url", "LinkedIn": "url"},
            "documents": {"Resume": "drive url"},
            "projects": [{"name": "string", "details": "string"}],
            "experience": [{"company": "string", "role_details": "string"}],
            "certifications": [{"name": "string", "details": "string"}],
        },
    }
