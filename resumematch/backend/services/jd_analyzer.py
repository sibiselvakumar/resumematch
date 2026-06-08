import json
import os
from groq import AsyncGroq
from dotenv import load_dotenv

load_dotenv()

_client = None

def get_client() -> AsyncGroq:
    global _client
    if _client is None:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY environment variable is not set. Copy .env.example to .env and add your key.")
        _client = AsyncGroq(api_key=api_key)
    return _client


MODEL = "llama-3.3-70b-versatile"

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
    response = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "user",
                "content": JD_ANALYSIS_PROMPT.format(jd_text=jd_text[:8000])
            }
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
        max_tokens=1200,
    )

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
