# ResumeMatch — AI Resume Screening Tool

Internal HR tool that scores resumes against a job description using the NVIDIA API + GLM-5.2.

---

## Quick Start (Local)

### Prerequisites

- Python 3.10+
- Node.js 18+
- An [NVIDIA API key](https://build.nvidia.com) (takes 1 minute)

---

### 1. Set up the backend

```bash
cd backend

# Install Python dependencies
pip install -r requirements.txt

# Create your .env file
cp .env.example .env
```

Open `.env` and paste your NVIDIA API key:
```
NVIDIA_API_KEY=nvapi-xxxxxxxxxxxxxxxxxxxx
```

Start the backend server:
```bash
uvicorn main:app --reload --port 8000
```

You should see: `Uvicorn running on http://127.0.0.1:8000`

---

### 2. Set up the frontend

Open a new terminal:

```bash
cd frontend

# Install Node dependencies
npm install

# Start the dev server
npm run dev
```

You should see: `Local: http://localhost:5173`

---

### 3. Use the app

Open **http://localhost:5173** in your browser.

1. Paste or upload a Job Description
2. Upload one or more resumes (PDF or DOCX)
3. Click **Screen Resumes**
4. See ranked candidates with match scores, skill breakdowns, and AI summaries

---

## How Scoring Works

Each resume is scored across 5 dimensions using a two-pass AI approach:

| Dimension | Weight | What's Evaluated |
|-----------|--------|-----------------|
| Skills Match | 35% | Required skills from JD vs resume |
| Experience | 30% | Years and relevance of experience |
| Role Alignment | 15% | How closely past titles match the role |
| Education | 10% | Degree requirements met |
| Responsibilities | 10% | Overlap with JD duties |

**Pass 1** — JD is analyzed once to extract structured requirements (required skills, experience, education, etc.)

**Pass 2** — Each resume is scored against those requirements independently. Multiple resumes run in parallel.

Score bands:
- **80–100** → Strong Match 🟢
- **60–79** → Potential Match 🟡
- **0–59** → Weak Match 🔴

---

## File Format Support

| Format | JD | Resume |
|--------|-----|--------|
| PDF | ✅ | ✅ |
| DOCX | ✅ | ✅ |
| Plain text paste | ✅ | — |
| .doc (legacy) | ❌ | ❌ |

> **Note:** Scanned/image PDFs won't work — the text must be selectable. If a resume is image-only, the system will flag it.

---

## API Reference

The backend exposes these endpoints at `http://localhost:8000`:

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/analyze` | Upload JD + resumes, get scores |
| `GET` | `/api/sessions` | List past screening sessions |
| `GET` | `/api/sessions/{id}` | Get a specific session's results |
| `GET` | `/api/sessions/{id}/export` | Download results as CSV |
| `GET` | `/health` | Health check |

---

## Project Structure

```
resumematch/
├── backend/
│   ├── main.py                  # FastAPI app entry point
│   ├── models.py                # Pydantic schemas
│   ├── database.py              # SQLite session storage
│   ├── requirements.txt
│   ├── .env.example
│   ├── routers/
│   │   └── analyze.py           # API endpoints
│   └── services/
│       ├── parser.py            # PDF + DOCX text extraction
│       ├── jd_analyzer.py       # Pass 1: JD → requirements
│       └── resume_scorer.py     # Pass 2: Resume → score
│
└── frontend/
    ├── index.html
    ├── package.json
    ├── vite.config.js           # Proxies /api → localhost:8000
    └── src/
        ├── App.jsx              # Main app + stage routing
        ├── App.css
        ├── api.js               # Fetch wrappers
        └── components/
            ├── JDUploader.jsx   # JD paste/upload area
            ├── ResumeUploader.jsx # Multi-file drop zone
            ├── Leaderboard.jsx  # Candidate ranking
            ├── ScoreCard.jsx    # Per-candidate expandable card
            └── DimensionBar.jsx # Score bar with notes + skill chips
```

---

## Troubleshooting

**"NVIDIA_API_KEY environment variable is not set"**
→ Make sure you created `.env` in the `backend/` folder with your key.

**"Analysis failed" error in the UI**
→ Check that the backend is running on port 8000. Check the backend terminal for the full error.

**PDF text extraction returns empty**
→ The PDF is likely a scanned image. Export the original document as a searchable PDF or use DOCX instead.

**NVIDIA API rate limit errors**
→ Wait 60 seconds and retry, or check your usage tier on build.nvidia.com.

**Port 5173 already in use**
→ Change the Vite port in `vite.config.js` and update the CORS origins in `backend/main.py`.

---

## Deploying for Free (Phase 3)

**Frontend → Vercel:**
```bash
cd frontend
npm run build
# Push to GitHub → connect repo on vercel.com → auto-deploys
```

**Backend → Render.com:**
- Create a new Web Service on render.com
- Connect your GitHub repo
- Set Build Command: `pip install -r requirements.txt`
- Set Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
- Add `NVIDIA_API_KEY` as an environment variable
- Update CORS origins in `main.py` with your Vercel URL
