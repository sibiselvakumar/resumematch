import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import init_db
from routers.analyze import router as analyze_router

# Diagnostic logging for the "why is this slow" investigation.
# openai/httpx at DEBUG/INFO reveal retries and the raw HTTP status of every
# call to the NVIDIA API (429s, 5xxs, timeouts) that would otherwise be
# retried silently by the SDK and never surfaced as an error.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logging.getLogger("openai").setLevel(logging.DEBUG)
logging.getLogger("httpx").setLevel(logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize DB on startup."""
    await init_db()
    yield


app = FastAPI(
    title="ResumeMatch API",
    description="AI-powered resume screening against job descriptions",
    version="1.0.0",
    lifespan=lifespan,
)

_default_origins = "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173,http://127.0.0.1:3000"
_allowed = os.getenv("ALLOWED_ORIGINS", _default_origins)
allowed_origins = [o.strip() for o in _allowed.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analyze_router, prefix="/api")


@app.get("/health")
async def health():
    return {"status": "ok"}
