import asyncio
import io
import csv
import json
import uuid
from typing import List, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from database import get_session, get_sessions, save_session
from services.jd_analyzer import analyze_jd
from services.parser import extract_text, get_candidate_name
from services.resume_scorer import score_resume

router = APIRouter()


@router.post("/analyze")
async def analyze_resumes(
    resumes: List[UploadFile] = File(..., description="One or more resume files (PDF or DOCX)"),
    jd_text: Optional[str] = Form(None, description="Job description as plain text"),
    jd_file: Optional[UploadFile] = File(None, description="Job description as PDF or DOCX"),
    weights_json: Optional[str] = Form(None, description="JSON object of scoring weights (values 0–1, must sum to 1.0)"),
):
    """
    Main endpoint: upload a JD + resumes, get back scored & ranked candidates.
    """
    # ── 1. Resolve JD text ──────────────────────────────────────────────────
    if jd_file and jd_file.filename:
        jd_bytes = await jd_file.read()
        try:
            jd_content = extract_text(jd_bytes, jd_file.filename)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
    elif jd_text and jd_text.strip():
        jd_content = jd_text.strip()
    else:
        raise HTTPException(status_code=400, detail="Provide either jd_text or jd_file.")

    if len(jd_content.strip()) < 50:
        raise HTTPException(status_code=400, detail="Job description is too short to analyze.")

    if not resumes:
        raise HTTPException(status_code=400, detail="At least one resume file is required.")

    # ── 1b. Parse custom weights (optional) ─────────────────────────────────
    custom_weights = None
    if weights_json:
        try:
            custom_weights = json.loads(weights_json)
            total = sum(custom_weights.values())
            if abs(total - 1.0) > 0.02:
                raise HTTPException(status_code=400, detail=f"Weights must sum to 1.0 (got {round(total, 3)})")
        except (json.JSONDecodeError, AttributeError):
            raise HTTPException(status_code=400, detail="Invalid weights_json — expected a JSON object")

    # ── 2. Pass 1: Analyze JD once ──────────────────────────────────────────
    try:
        jd_requirements = await analyze_jd(jd_content)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"JD analysis failed: {e}")

    # ── 3. Pass 2: Score resumes concurrently ────────────────────────────────
    async def process_resume(resume: UploadFile) -> dict:
        resume_bytes = await resume.read()
        candidate_name = get_candidate_name(resume.filename or "Unknown")
        try:
            resume_text = extract_text(resume_bytes, resume.filename or "")
        except ValueError as e:
            return {
                "candidate_name": candidate_name,
                "overall_score": 0,
                "dimensions": {
                    "skills_match": {"score": 0, "matched_skills": [], "missing_skills": [], "note": ""},
                    "experience": {"score": 0, "note": ""},
                    "role_alignment": {"score": 0, "note": ""},
                    "education": {"score": 0, "note": ""},
                    "responsibilities": {"score": 0, "note": ""},
                },
                "summary": f"Could not read this file: {e}",
                "recommendation": "Weak Match",
                "error": str(e),
            }
        if len(resume_text.strip()) < 50:
            return {
                "candidate_name": candidate_name,
                "overall_score": 0,
                "dimensions": {
                    "skills_match": {"score": 0, "matched_skills": [], "missing_skills": [], "note": ""},
                    "experience": {"score": 0, "note": ""},
                    "role_alignment": {"score": 0, "note": ""},
                    "education": {"score": 0, "note": ""},
                    "responsibilities": {"score": 0, "note": ""},
                },
                "summary": "Resume appears to be empty or image-only (no text extracted).",
                "recommendation": "Weak Match",
                "error": "Empty resume",
            }
        return await score_resume(jd_requirements, resume_text, candidate_name, weights=custom_weights)

    try:
        results = list(await asyncio.gather(*[process_resume(r) for r in resumes]))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Resume scoring failed: {e}")

    # Sort by score descending
    results.sort(key=lambda x: x["overall_score"], reverse=True)

    # ── 4. Persist session ──────────────────────────────────────────────────
    session_id = str(uuid.uuid4())
    role_title = jd_requirements.get("role_title", "")
    await save_session(session_id, jd_content, role_title, results)

    return {
        "session_id": session_id,
        "jd_requirements": jd_requirements,
        "results": results,
    }


@router.get("/sessions")
async def list_sessions():
    """Return a list of past screening sessions."""
    return await get_sessions()


@router.get("/sessions/{session_id}")
async def get_session_results(session_id: str):
    """Return all results for a specific session."""
    data = await get_session(session_id)
    if not data:
        raise HTTPException(status_code=404, detail="Session not found")
    return data


@router.get("/sessions/{session_id}/export")
async def export_csv(session_id: str):
    """Download session results as CSV."""
    data = await get_session(session_id)
    if not data:
        raise HTTPException(status_code=404, detail="Session not found")

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Rank", "Candidate", "Overall Score", "Recommendation",
        "Skills Score", "Matched Skills", "Missing Skills",
        "Experience Score", "Experience Notes",
        "Role Alignment Score", "Role Alignment Notes",
        "Education Score", "Education Notes",
        "Responsibilities Score", "Responsibilities Notes",
        "Summary",
    ])

    for rank, r in enumerate(data["results"], 1):
        dims = r.get("dimensions", {})
        sm = dims.get("skills_match", {})
        exp = dims.get("experience", {})
        ra = dims.get("role_alignment", {})
        edu = dims.get("education", {})
        resp = dims.get("responsibilities", {})
        writer.writerow([
            rank,
            r["candidate_name"],
            r["overall_score"],
            r["recommendation"],
            sm.get("score", ""),
            ", ".join(sm.get("matched_skills", [])),
            ", ".join(sm.get("missing_skills", [])),
            exp.get("score", ""),
            exp.get("note", ""),
            ra.get("score", ""),
            ra.get("note", ""),
            edu.get("score", ""),
            edu.get("note", ""),
            resp.get("score", ""),
            resp.get("note", ""),
            r.get("summary", ""),
        ])

    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8-sig")),  # utf-8-sig for Excel compat
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="session_{session_id[:8]}.csv"'
        },
    )
