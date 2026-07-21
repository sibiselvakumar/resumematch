import hashlib
import json
import logging
import os
import time
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("resumematch.jd_analyzer")

_client = None

def get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        api_key = os.environ.get("NVIDIA_API_KEY")
        if not api_key:
            raise RuntimeError("NVIDIA_API_KEY environment variable is not set. Copy .env.example to .env and add your key.")
        _client = AsyncOpenAI(base_url="https://integrate.api.nvidia.com/v1", api_key=api_key)
    return _client


MODEL = "meta/llama-3.1-70b-instruct"
SEED = 42


def hash_jd_text(jd_text: str) -> str:
    """Stable cache key for a JD's text, so repeat screenings of the same JD reuse the same extracted requirements instead of re-deriving (and drifting) them each time."""
    return hashlib.sha256(jd_text.strip().encode("utf-8")).hexdigest()

JD_ANALYSIS_PROMPT = """You are an expert technical recruiter. Analyze this job description and extract structured requirements.

Job Description:
{jd_text}

Return ONLY valid JSON matching this exact schema — no markdown, no explanation:
{{
  "role_title": "Software Engineer",
  "seniority_level": "Mid-level",
  "required_skills": ["Python", "REST APIs", "SQL"],
  "preferred_skills": ["Kubernetes", "Kafka"],
  "min_experience_years": 3,
  "education_requirement": "Bachelor's degree in Computer Science or equivalent",
  "key_responsibilities": [
    "Design and build REST APIs",
    "Collaborate with product and design teams",
    "Write unit and integration tests"
  ]
}}

Rules:
- required_skills: skills explicitly listed as required/must-have (max 15)
- preferred_skills: nice-to-have skills (max 10)
- min_experience_years: integer, 0 if not specified
- seniority_level: one of Junior, Mid-level, Senior, Lead, Principal, Manager
- If a field is unclear, use a sensible default"""


async def analyze_jd(jd_text: str) -> dict:
    """
    Pass 1: Extract structured requirements from a job description.
    Returns a dict with role_title, required_skills, preferred_skills, etc.
    """
    client = get_client()
    start = time.monotonic()
    try:
        response = await client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "user",
                    "content": JD_ANALYSIS_PROMPT.format(jd_text=jd_text[:8000])
                }
            ],
            response_format={"type": "json_object"},
            temperature=0,
            max_tokens=1200,
            seed=SEED,
        )
    except Exception as e:
        elapsed = time.monotonic() - start
        status_code = getattr(e, "status_code", None)
        resp = getattr(e, "response", None)
        retry_after = resp.headers.get("retry-after") if resp is not None else None
        logger.error(
            "analyze_jd FAILED after %.1fs status=%s retry_after=%s error=%s",
            elapsed, status_code, retry_after, e,
        )
        raise
    elapsed = time.monotonic() - start
    logger.info("analyze_jd OK in %.1fs (model=%s)", elapsed, MODEL)

    raw = response.choices[0].message.content
    try:
        result = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM returned invalid JSON for JD analysis: {e}\nRaw: {raw[:500]}")

    # Ensure expected keys exist with defaults
    result.setdefault("role_title", "")
    result.setdefault("seniority_level", "")
    result.setdefault("required_skills", [])
    result.setdefault("preferred_skills", [])
    result.setdefault("min_experience_years", 0)
    result.setdefault("education_requirement", "")
    result.setdefault("key_responsibilities", [])

    return result
