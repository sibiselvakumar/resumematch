# ResumeMatch — Architecture & File Breakdown

## What It Is

An internal HR tool: upload a job description + multiple resumes → get AI-scored, ranked candidates with breakdown by dimension. Two-pass LLM pipeline using Groq (Llama 3.3 70B).

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        BROWSER (port 5173)                      │
│                                                                 │
│  ┌──────────┐    ┌────────────────┐    ┌───────────────────┐   │
│  │JDUploader│    │ResumeUploader  │    │   Leaderboard     │   │
│  │          │    │                │    │   ┌─────────────┐ │   │
│  │ Paste tab│    │ Multi-file     │    │   │  ScoreCard  │ │   │
│  │ Upload   │    │ drag/drop      │    │   │ ┌─────────┐ │ │   │
│  │  tab     │    │ deduplication  │    │   │ │Dimension│ │ │   │
│  └────┬─────┘    └──────┬─────────┘    │   │ │  Bar    │ │ │   │
│       │                 │              │   │ └─────────┘ │ │   │
│       └────────┬────────┘              │   └─────────────┘ │   │
│                │                       └────────┬──────────┘   │
│            App.jsx                              │               │
│         (3 stages:                   export CSV │               │
│          upload→loading→results)                │               │
│                │                                │               │
│            api.js ─── POST /api/analyze ────────┘               │
│                  ─── GET  /api/sessions/{id}/export             │
└────────────────────────┬────────────────────────────────────────┘
                         │ Vite proxy /api → localhost:8000
                         │
┌────────────────────────▼────────────────────────────────────────┐
│                    FASTAPI BACKEND (port 8000)                   │
│                                                                 │
│  main.py                                                        │
│  ├── CORS (allows :5173, :3000)                                 │
│  ├── lifespan → init_db() on startup                            │
│  └── mounts router at /api                                      │
│                                                                 │
│  routers/analyze.py                                             │
│  ├── POST /api/analyze ──────────────────┐                      │
│  │   1. Resolve JD (text or file)        │                      │
│  │   2. Pass 1: analyze_jd()             │                      │
│  │   3. Pass 2: score_resume() × N       │  asyncio.gather()    │
│  │      (all resumes in parallel) ───────┘  concurrent          │
│  │   4. sort by score desc                                      │
│  │   5. save_session() → SQLite                                 │
│  │   6. return results                                          │
│  ├── GET /api/sessions                                          │
│  ├── GET /api/sessions/{id}                                     │
│  └── GET /api/sessions/{id}/export  → CSV (StreamingResponse)   │
│                                                                 │
│  services/                                                      │
│  ├── parser.py          ← pdfplumber / python-docx              │
│  ├── jd_analyzer.py     ← Groq LLM call (Pass 1)               │
│  └── resume_scorer.py   ← Groq LLM call (Pass 2) + weighting   │
│                                                                 │
│  database.py            ← aiosqlite, two tables                 │
│  models.py              ← Pydantic schemas                      │
└──────────────────────────┬──────────────────────────────────────┘
                           │
              ┌────────────▼─────────────┐
              │    Groq API (external)    │
              │  llama-3.3-70b-versatile  │
              │  json_object mode         │
              │  temperature=0.1          │
              └──────────────────────────┘
                           │
              ┌────────────▼─────────────┐
              │   SQLite (resumematch.db) │
              │   sessions table          │
              │   results table           │
              └──────────────────────────┘
```

---

## Data Flow — Single Request

```
User uploads JD + 3 resumes
         │
         ▼
POST /api/analyze (multipart/form-data)
         │
         ▼
  parser.py: extract_text() → raw text for JD
         │
         ▼
  jd_analyzer.py: LLM call → structured JSON
  {required_skills, preferred_skills,
   min_experience_years, education_req,
   key_responsibilities, seniority_level, role_title}
         │
         ▼ (once, shared across all resumes)
  asyncio.gather() — 3 concurrent LLM calls
  ┌──────────────┬──────────────┬──────────────┐
  │ resume_1.pdf │ resume_2.pdf │ resume_3.pdf │
  │ extract_text │ extract_text │ extract_text │
  │ score_resume │ score_resume │ score_resume │
  └──────┬───────┴──────┬───────┴──────┬───────┘
         │              │              │
         └──────────────┴──────────────┘
                        │
                        ▼
         LLM returns dimensions per candidate:
         {skills_match, experience, role_alignment,
          education, responsibilities}
                        │
                        ▼
         compute_overall_score() — deterministic weighted sum
         skills×0.35 + exp×0.30 + role×0.15 + edu×0.10 + resp×0.10
                        │
                        ▼
         sort desc by overall_score
                        │
                        ▼
         save_session() → SQLite
                        │
                        ▼
         return JSON → React renders Leaderboard
```

---

## File-by-File Breakdown

### Backend

| File                        | Purpose                                                                                                                                                                                                                                                             |
| --------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `main.py`                   | FastAPI app entry point. Wires CORS, mounts `/api` router, runs `init_db()` on startup via `lifespan`.                                                                                                                                                              |
| `models.py`                 | Pydantic schemas: `SkillDimension`, `BasicDimension`, `Dimensions`, `ResumeResult`, `JDRequirements`, `AnalyzeResponse`. Shape contracts for everything in/out of the API.                                                                                          |
| `database.py`               | All SQLite logic via `aiosqlite`. Two tables: `sessions` (id, jd_text, role_title, created_at) and `results` (candidate_name, overall_score, recommendation, full result_json). CRUD: init, save, list, get.                                                        |
| `routers/analyze.py`        | The only router. Four endpoints: `POST /analyze` (main pipeline), `GET /sessions`, `GET /sessions/{id}`, `GET /sessions/{id}/export` (CSV download with Excel-compatible utf-8-sig encoding).                                                                       |
| `services/parser.py`        | File parsing. `extract_text_from_pdf()` via pdfplumber, `extract_text_from_docx()` via python-docx (includes table cells). `get_candidate_name()` strips "resume*" / "cv*" prefixes from filenames to derive display names.                                         |
| `services/jd_analyzer.py`   | **Pass 1 LLM call.** Sends JD text (capped at 8000 chars) to Groq, forces `json_object` response mode, returns structured requirements dict. Lazy singleton for the `AsyncGroq` client.                                                                             |
| `services/resume_scorer.py` | **Pass 2 LLM call.** Sends JD requirements + resume text (capped at 6000 chars) to Groq. LLM scores 5 dimensions. `compute_overall_score()` applies hardcoded weights (not trusting LLM's arithmetic). `get_recommendation()` converts numeric score to band label. |
| `requirements.txt`          | 9 pinned deps: fastapi, uvicorn, python-multipart, pdfplumber, python-docx, groq, httpx, aiosqlite, python-dotenv.                                                                                                                                                  |
| `.env` / `.env.example`     | `GROQ_API_KEY` — only secret the app needs.                                                                                                                                                                                                                         |
| `resumematch.db`            | SQLite file, auto-created on first run, persists past sessions.                                                                                                                                                                                                     |

### Frontend

| File                                | Purpose                                                                                                                                                                                                    |
| ----------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `vite.config.js`                    | Vite + React plugin. Proxies all `/api/*` requests to `http://localhost:8000` — means frontend never directly hits the backend origin, no CORS issues in dev.                                              |
| `src/main.jsx`                      | React entry point. Mounts `<App />` into `#root`.                                                                                                                                                          |
| `src/api.js`                        | Three fetch wrappers: `analyzeResumes()` (POST multipart), `getExportUrl()` (returns string URL for CSV), `fetchSessions()` (GET list). All errors surface as thrown `Error` with human-readable messages. |
| `src/App.jsx`                       | State machine with 3 stages: `upload → loading → results`. Owns all top-level state (jdText, jdFile, resumes, results). Cycles through 4 loading messages every 4s during analysis.                        |
| `src/components/JDUploader.jsx`     | Two-tab component: "Paste Text" (textarea) and "Upload File" (drag-drop zone). Mutually exclusive — switching input type clears the other.                                                                 |
| `src/components/ResumeUploader.jsx` | Multi-file drop zone. Deduplicates by filename before adding. Shows file list with per-item remove.                                                                                                        |
| `src/components/Leaderboard.jsx`    | Displays stats bar (Strong/Potential/Weak counts) and renders one `ScoreCard` per candidate. "Export CSV" button opens the backend CSV endpoint in a new tab.                                              |
| `src/components/ScoreCard.jsx`      | Per-candidate expandable card. Header shows rank, name, recommendation, overall score. Collapsed: summary text. Expanded: all 5 `DimensionBar` components. Color-coded green/yellow/red by score.          |
| `src/components/DimensionBar.jsx`   | Single dimension visualization. Progress bar + score + note + skill chips (matched ✓ green / missing ✗ red). Shows weight % label.                                                                         |

---

## Scoring Weights

Hardcoded identically in both `services/resume_scorer.py` and `src/components/DimensionBar.jsx`:

```
Skills Match      35%   ← most important, explicit skill matching
Experience        30%   ← years + relevance
Role Alignment    15%   ← past job titles vs. target role
Education         10%   ← degree requirement
Responsibilities  10%   ← overlap with JD duties
```

Score bands: **≥80 → Strong Match**, **60–79 → Potential Match**, **<60 → Weak Match**

---

## Key Design Decisions

1. **Two-pass LLM strategy** — JD is parsed once into structured JSON (Pass 1), then each resume is independently scored against that JSON (Pass 2). N resumes = 1 + N LLM calls, not 2N.
2. **Deterministic scoring** — The LLM scores each dimension 0–100, but the weighted rollup (`compute_overall_score`) is done in Python, not by the LLM. This prevents hallucinated overall scores.
3. **`json_object` response mode** — Groq's forced JSON mode + `temperature=0.1` minimizes parsing failures.
4. **Concurrent resume processing** — `asyncio.gather()` fires all `score_resume()` calls in parallel, so 10 resumes take roughly the same wall-clock time as 1.
5. **Session persistence** — Every analysis run is saved to SQLite with full JSON blobs, enabling history review and CSV export without re-running the LLM.
