"""
app/api/main.py
Production FastAPI app
  - /health        — liveness + readiness probe
  - /chat          — multi-turn agent chat
  - /jobs/search   — direct semantic search
  - /jobs/salary   — salary analysis
  - /jobs/skill-gap — skill gap check
"""
import json
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, File, HTTPException, Request, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.agent.core import JobAgent
from app.rag.retriever import JobRetriever
from app.tools.job_tools import salary_analysis, skill_gap_check
from app.config import get_settings
from app.logger import setup_logger

log = setup_logger("api")
settings = get_settings()

# ─── SESSION STORE (in-memory; swap for Redis in prod) ────────
_sessions: dict[str, JobAgent] = {}


def get_or_create_agent(session_id: str) -> JobAgent:
    if session_id not in _sessions:
        _sessions[session_id] = JobAgent()
        log.info(f"New session: {session_id}")
    return _sessions[session_id]


# ─── LIFESPAN ─────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Starting up — warming retriever...")
    try:
        r = JobRetriever()
        log.info(f"Retriever ready: {r.count()} documents")
    except Exception as e:
        log.error(f"Retriever warm-up failed: {e}")
    yield
    log.info("Shutting down")


# ─── APP ──────────────────────────────────────────────────────
app = FastAPI(
    title="Thai Job Market AI Agent",
    description="LLM-powered job market intelligence for Thailand IT/Data roles",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── MIDDLEWARE: request logging + timing ─────────────────────
@app.middleware("http")
async def log_requests(request: Request, call_next):
    req_id = str(uuid.uuid4())[:8]
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = round((time.perf_counter() - start) * 1000)
    log.info(f"[{req_id}] {request.method} {request.url.path} → {response.status_code} ({elapsed}ms)")
    response.headers["X-Request-ID"] = req_id
    response.headers["X-Response-Time"] = f"{elapsed}ms"
    return response


# ─── GLOBAL ERROR HANDLER ─────────────────────────────────────
@app.exception_handler(Exception)
async def global_error_handler(request: Request, exc: Exception):
    log.error(f"Unhandled error on {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error", "type": type(exc).__name__},
    )


# ─── SCHEMAS ──────────────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))

class ChatResponse(BaseModel):
    answer: str
    tools_used: list[dict]
    session_id: str
    turn: int

class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    n_results: int = Field(default=5, ge=1, le=20)
    salary_min: int | None = None

class SalaryRequest(BaseModel):
    role: str
    skill: str | None = None

class SkillGapRequest(BaseModel):
    target_role: str
    current_skills: list[str] = Field(..., min_length=1)


# ─── ENDPOINTS ────────────────────────────────────────────────
@app.get("/health")
def health():
    try:
        count = JobRetriever().count()
        return {"status": "ok", "jobs_indexed": count}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Retriever unavailable: {e}")


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    agent = get_or_create_agent(req.session_id)
    result = agent.chat(req.message)
    return ChatResponse(
        answer=result["answer"],
        tools_used=result["tools_used"],
        session_id=req.session_id,
        turn=result["turn"],
    )


@app.delete("/chat/{session_id}")
def reset_chat(session_id: str):
    if session_id in _sessions:
        _sessions[session_id].reset()
    return {"status": "cleared", "session_id": session_id}


@app.post("/jobs/search")
def search_jobs(req: SearchRequest):
    retriever = JobRetriever()
    jobs = retriever.search(
        query=req.query,
        n_results=req.n_results,
        salary_min=req.salary_min,
    )
    return {"query": req.query, "results": jobs, "count": len(jobs)}


@app.post("/jobs/salary")
def get_salary(req: SalaryRequest):
    result = salary_analysis(role=req.role, skill=req.skill)
    return result


@app.post("/jobs/skill-gap")
def get_skill_gap(req: SkillGapRequest):
    result = skill_gap_check(
        target_role=req.target_role,
        current_skills=req.current_skills,
    )
    return result


@app.post("/cv/analyze")
def analyze_cv(file: UploadFile = File(...)):
    """Extract text from uploaded CV (PDF) and analyze with Gemini"""
    import base64
    import fitz  # pymupdf
    from google import genai
    from google.genai import types

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are supported")

    pdf_bytes = file.file.read()

    # Try text extraction first
    cv_text = ""
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        cv_text = "\n".join(page.get_text() for page in doc)
        doc.close()
    except Exception:
        pass

    client = genai.Client(api_key=settings.gemini_api_key)

    # If text extraction failed or got very little text, use Gemini Vision
    use_vision = len(cv_text.strip()) < 100

    if use_vision:
        log.info("CV is image-based — using Gemini Vision to read PDF")
        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            page_images = []
            for page_num in range(min(len(doc), 5)):  # Max 5 pages
                pix = doc[page_num].get_pixmap(matrix=fitz.Matrix(2, 2))
                img_bytes = pix.tobytes("png")
                page_images.append(img_bytes)
            doc.close()
        except Exception as e:
            raise HTTPException(400, f"Failed to render PDF pages: {e}")

        # Use Gemini Vision to extract text from images
        vision_parts = []
        for img_bytes in page_images:
            vision_parts.append(types.Part(
                inline_data=types.Blob(mime_type="image/png", data=img_bytes)
            ))

        try:
            extract_response = client.models.generate_content(
                model=settings.gemini_model,
                contents=[
                    types.Part(text="Extract ALL text from this CV/Resume. Return the raw text content, preserving structure. Include all skills, experience, education, and contact details you can read."),
                    *vision_parts,
                ],
                config=types.GenerateContentConfig(temperature=0.1),
            )
            cv_text = extract_response.text
            log.info(f"Vision extracted {len(cv_text)} chars from CV")
        except Exception as e:
            log.error(f"Gemini Vision extraction failed: {e}")
            raise HTTPException(503, f"AI could not read the CV: {e}")

    if not cv_text.strip():
        raise HTTPException(400, "Could not extract any text from PDF")

    # Search for relevant jobs based on CV content
    retriever = JobRetriever()
    jobs = retriever.search(query=cv_text[:500], n_results=10)

    jobs_json = json.dumps([
        {
            "title": j["title"],
            "company": j["company"],
            "location": j.get("location", ""),
            "description": j.get("description", "")[:200],
        }
        for j in jobs
    ], ensure_ascii=False)

    # Analyze with Gemini — return structured JSON
    prompt = f"""You are a job matching AI. Analyze the CV and compare it against each job listing.

CV TEXT:
{cv_text[:4000]}

JOB LISTINGS:
{jobs_json}

Return a JSON object (no markdown, no code fences) with this exact structure:
{{
  "profile_summary": "สรุปโปรไฟล์ผู้สมัครเป็นภาษาไทย 2-3 ประโยค",
  "skills_found": ["skill1", "skill2", ...],
  "skills_missing": ["skill1", "skill2", ...],
  "recommendations": "คำแนะนำเพื่อเพิ่มโอกาสในตลาดงาน เป็นภาษาไทย",
  "job_matches": [
    {{
      "job_index": 0,
      "match_score": 85,
      "match_reasons": ["เหตุผลที่เหมาะ 1", "เหตุผลที่เหมาะ 2"],
      "gap_notes": ["สิ่งที่ยังขาด 1"]
    }},
    ...for each job
  ]
}}

Rules:
- match_score is 0-100 based on how well the CV fits the job
- Respond all Thai text in Thai language
- Return ONLY valid JSON, no other text
"""
    try:
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.2),
        )
        raw = response.text.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()

        import json as json_mod
        ai_result = json_mod.loads(raw)
    except json.JSONDecodeError:
        log.warning("Gemini returned non-JSON, falling back to text analysis")
        ai_result = {
            "profile_summary": raw[:500],
            "skills_found": [],
            "skills_missing": [],
            "recommendations": "",
            "job_matches": [],
        }
    except Exception as e:
        log.error(f"Gemini CV analysis failed: {e}")
        raise HTTPException(503, f"AI analysis failed: {e}")

    # Merge AI match data into job results
    match_map = {m["job_index"]: m for m in ai_result.get("job_matches", [])}
    matched_jobs = []
    for i, j in enumerate(jobs):
        m = match_map.get(i, {})
        matched_jobs.append({
            **j,
            "match_score": m.get("match_score", 0),
            "match_reasons": m.get("match_reasons", []),
            "gap_notes": m.get("gap_notes", []),
        })

    # Sort by match score descending
    matched_jobs.sort(key=lambda x: x["match_score"], reverse=True)

    return {
        "filename": file.filename,
        "profile_summary": ai_result.get("profile_summary", ""),
        "skills_found": ai_result.get("skills_found", []),
        "skills_missing": ai_result.get("skills_missing", []),
        "recommendations": ai_result.get("recommendations", ""),
        "matched_jobs": matched_jobs,
    }


@app.get("/")
def root():
    return {
        "name": "Thai Job Market AI Agent",
        "version": "1.0.0",
        "docs": "/docs",
    }
