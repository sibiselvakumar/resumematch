# ResumeMatch — Project Overview

An internal HR tool that screens resumes against a job description and ranks
candidates by fit. A recruiter pastes a JD and drops in a batch of resumes;
the backend extracts structured requirements from the JD once, scores every
resume against those requirements using an LLM, and returns a ranked
leaderboard with per-dimension breakdowns.

---

## 1. Tech Stack

**Backend**
- **FastAPI** (Python 3.10+) — API server, `resumematch/backend/main.py`
- **SQLite via `aiosqlite`** — stores past screening sessions and a JD-requirements cache (no separate DB server to run)
- **NVIDIA API** (`https://integrate.api.nvidia.com/v1`) via the `openai` SDK's `AsyncOpenAI` client — the LLM backend
- **Model**: `meta/llama-3.1-70b-instruct` (see [§6 Known discrepancy](#6-known-discrepancy-model-name))
- **`pdfplumber`** / **`python-docx`** — text extraction from PDF/DOCX
- **`python-dotenv`** — loads `NVIDIA_API_KEY` from `.env`

**Frontend**
- **React 18** + **Vite 5** — SPA, `resumematch/frontend/src/`
- No component library or state management framework — plain `useState` in `App.jsx`, plain `fetch` wrappers in `api.js`
- Vite dev server proxies `/api` → `http://localhost:8000`

**No auth, no user accounts.** This is built as a single-tenant internal tool.

---

## 2. How the Project Is Organized

```
resumematch/
├── backend/
│   ├── main.py                  FastAPI app, CORS, DB init on startup, /health
│   ├── models.py                Pydantic response schemas
│   ├── database.py              SQLite: sessions, results, JD-requirements cache
│   ├── routers/analyze.py       All HTTP endpoints
│   └── services/
│       ├── parser.py            PDF/DOCX/text → plain text, filename → candidate name
│       ├── jd_analyzer.py       Pass 1: JD text → structured requirements (LLM call)
│       └── resume_scorer.py     Pass 2: requirements + resume → score (LLM call + math)
│
└── frontend/
    └── src/
        ├── App.jsx              3-stage flow: upload → loading → results
        ├── api.js                fetch() wrapper for /api/*
        └── components/
            ├── JDUploader.jsx        paste or upload the JD
            ├── ResumeUploader.jsx    multi-file drop zone
            ├── WeightConfig.jsx      lets the recruiter re-weight the 5 scoring dimensions
            ├── Leaderboard.jsx       ranked candidate list
            ├── ScoreCard.jsx         per-candidate expandable detail
            └── DimensionBar.jsx      single dimension's score bar + notes/chips
```

---

## 3. How a Screening Request Flows

1. **Frontend** — user pastes/uploads a JD, drops resume files, optionally adjusts
   scoring weights (must sum to 100%), clicks **Screen Resumes**.
   `App.jsx` → `analyzeResumes()` in `api.js` → `POST /api/analyze` (multipart form:
   `resumes[]`, `jd_text` or `jd_file`, `weights_json`).

2. **`routers/analyze.py: analyze_resumes()`** — the orchestrator:
   - Resolves JD text (from pasted text or uploaded file via `parser.extract_text`)
   - Validates JD length (≥50 chars) and that at least one resume was sent
   - Parses/validates custom weights if provided (must sum to 1.0 ± 0.02)
   - **Pass 1**: hashes the JD text (`sha256`) and checks the `jd_analysis_cache`
     table in SQLite. On a cache miss, calls `jd_analyzer.analyze_jd()` and caches
     the result. Repeat screenings of an identical JD reuse the same extracted
     requirements instead of re-deriving them (and risking drift) every time.
   - **Pass 2**: for each resume, extracts text, and — if it parsed to ≥50 chars
     of text — calls `resume_scorer.score_resume()`. All resumes are scored
     **concurrently** via `asyncio.gather`, gated by a
     `asyncio.Semaphore(15)` so a large batch doesn't burst past the NVIDIA
     account's rate limit (40 RPM) all in the same second.
   - Results are sorted by `overall_score` descending, the whole session
     (JD text, role title, all results) is persisted to SQLite, and the
     response is returned.

3. **Frontend** renders `Leaderboard` → `ScoreCard` → `DimensionBar` from the
   response.

Other endpoints (`GET /api/sessions`, `GET /api/sessions/{id}`,
`GET /api/sessions/{id}/export`) just read back what was persisted — session
list, single session detail, and a CSV export.

---

## 4. The Scoring Algorithm (the core of the project)

This is a **two-pass LLM pipeline with deterministic post-processing** — the
LLM does the qualitative judgment; hand-written code redoes anything that
needs to be numerically reliable or consistent across resumes.

### Pass 1 — JD → structured requirements (`jd_analyzer.py`)

One LLM call per unique JD (cached by hash). The prompt asks Llama to return
strict JSON:

```json
{
  "role_title": "...",
  "seniority_level": "Junior|Mid-level|Senior|Lead|Principal|Manager",
  "required_skills": [...],
  "preferred_skills": [...],
  "min_experience_years": 3,
  "education_requirement": "...",
  "key_responsibilities": [...]
}
```
Called with `temperature=0` and a fixed `seed=42` for reproducibility, and
`response_format={"type": "json_object"}` to force valid JSON.

### Pass 2 — resume → score (`resume_scorer.py`)

One LLM call per resume, scoring 5 dimensions (0–100 each) with a fixed
weighting:

| Dimension | Weight | What it evaluates |
|---|---|---|
| Skills Match | 35% | Required JD skills found in the resume |
| Experience | 30% | Years and relevance of past roles |
| Role Alignment | 15% | How closely past titles match the target role |
| Education | 10% | Whether the degree requirement is met |
| Responsibilities | 10% | Overlap between past duties and JD responsibilities |

Weights are overridable per-request via `weights_json` (the frontend's
`WeightConfig` component), as long as they sum to 1.0.

**Critically, the LLM's own numbers are not trusted at face value.** After
the raw JSON comes back, the code re-derives several fields deterministically:

- **Skills sanitation** — the model sometimes invents a plausible but
  absent skill (e.g. reporting "Azure" when the JD only said "Azure OpenAI").
  `_sanitize_skills()` drops anything not literally in `required_skills`.
  If a skill is claimed as both matched *and* missing, "matched" wins (it
  reflects found evidence). Any required skill the model never classified
  either way is added to `missing_skills` so nothing silently disappears
  from what's shown vs. what's counted.
- **Skills score recomputed** — `skills_match.score` is overwritten as
  `100 × len(matched_skills) / len(required_skills)`, not the LLM's
  self-reported number, since the two can disagree (e.g. every required
  skill tagged matched, but a self-rated score of 80).
- **Experience years computed from dates, not the LLM's arithmetic** — the
  prompt asks the model to list *every* job with start/end dates and a
  `relevant_to_role` flag, but never to total the years itself (small
  models are unreliable at that arithmetic and give inconsistent totals
  across runs of the same resume). `compute_experience_years()` parses each
  date (handles `"2021-03"`, `"2021"`, `"Sep 2010"`, `"09/2010"`,
  `"Present"`/`"current"`/etc.), converts to absolute month indices, and
  merges overlapping/adjacent ranges (`_merge_month_ranges`) so concurrent
  jobs aren't double-counted. Produces both **total years** and **relevant
  years** (only ranges flagged `relevant_to_role: true`).
- **Overall score** = weighted sum of the 5 (possibly-corrected) dimension
  scores using `WEIGHTS` (or the caller's custom weights), rounded to an int.
- **Recommendation band** is derived purely from the overall score:
  - **80–100 → Strong Match**
  - **60–79 → Potential Match**
  - **0–59 → Weak Match**
  (the LLM also proposes a recommendation, but the final one returned is
  always this deterministic banding).

### Why this design

The split exists because small/mid-size LLMs are good at *qualitative*
judgment (is this skill present, is this role relevant) but unreliable at
*consistent arithmetic* (totaling years, self-rating a score 0–100
consistently across many independent calls). So the prompt is structured to
extract raw facts (skill lists, dated employment history) and the scoring
math is done in plain Python from those facts — making the numeric results
reproducible and auditable instead of just "whatever the model said."

---

## 5. Other Notable Behavior

- **JD caching** (`jd_analysis_cache` table) — same JD text → same hash →
  reuses Pass 1 output. Saves an API call and keeps requirements identical
  across repeat screenings of the same role.
- **Concurrency cap** — `asyncio.Semaphore(15)` in `routers/analyze.py`
  limits simultaneous NVIDIA API calls during Pass 2, to stay under the
  account's 40 RPM ceiling.
- **Bad/empty resumes never crash the batch** — if text extraction fails
  (e.g. scanned/image-only PDF) or extracts to <50 chars, that candidate
  gets a synthetic all-zero result with an explanatory `summary` instead of
  the whole request failing.
- **Diagnostic logging** — `main.py` sets `openai` logger to DEBUG and
  `httpx` to INFO specifically to surface retries/429s/5xxs from the NVIDIA
  API that the SDK would otherwise retry silently.
- **CORS** — origins configurable via `ALLOWED_ORIGINS` env var, defaults
  to the local Vite/CRA dev ports.
- **CSV export** — `GET /api/sessions/{id}/export` flattens a session's
  results into a CSV (UTF-8 BOM for Excel compatibility).

---

## 6. Model Name

The app runs **Llama 3.1 70B** end to end (`MODEL = "meta/llama-3.1-70b-instruct"`
in `services/jd_analyzer.py`, imported into `resume_scorer.py`). The README
and frontend footer (`App.jsx`) now match this. (The commit that migrated to
the NVIDIA API originally mislabeled it "8B" in the commit message and copy —
that copy has since been corrected to 70B to match the code.)

---

## 7. Running It Locally

```bash
# Backend
cd resumematch/backend
pip install -r requirements.txt
cp .env.example .env        # add NVIDIA_API_KEY=nvapi-...
uvicorn main:app --reload --port 8000

# Frontend (separate terminal)
cd resumematch/frontend
npm install
npm run dev                 # http://localhost:5173
```

Full endpoint list, troubleshooting, and deploy instructions (Vercel +
Render) are in `resumematch/README.md`.
