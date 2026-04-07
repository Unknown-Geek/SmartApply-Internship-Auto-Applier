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

from app.data.identity import _identity, get_identity, load_identity

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
