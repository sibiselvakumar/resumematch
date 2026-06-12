import json
import os
from groq import AsyncGroq
from dotenv import load_dotenv
from .jd_analyzer import get_client, MODEL

load_dotenv()

# Scoring weights — must sum to 1.0
WEIGHTS = {
    "skills_match": 0.35,
    "experience": 0.30,
    "role_alignment": 0.15,
    "education": 0.10,
    "responsibilities": 0.10,
}

SCORING_PROMPT = """You are an expert HR recruiter scoring a candidate's resume against a job's requirements.

JOB REQUIREMENTS:
{jd_requirements}

CANDIDATE RESUME:
{resume_text}

Score the candidate across 5 dimensions (each 0-100) and return ONLY valid JSON — no markdown, no explanation:
{{
  "dimensions": {{
    "skills_match": {{
      "score": 80,
      "matched_skills": ["Python", "FastAPI", "SQL"],
      "missing_skills": ["Kubernetes", "Kafka"],
      "note": "Strong Python and API skills; missing container orchestration tools"
    }},
    "experience": {{
      "score": 70,
      "note": "5 years total, 3 directly relevant to backend engineering at this scale"
    }},
    "role_alignment": {{
      "score": 75,
      "note": "Previous Backend Engineer title aligns well; no Principal-level experience"
    }},
    "education": {{
      "score": 100,
      "note": "BS in Computer Science from reputed university — meets requirements"
    }},
    "responsibilities": {{
      "score": 65,
      "note": "API design and testing present; limited evidence of technical leadership"
    }}
  }},
  "summary": "Solid backend engineer with strong Python/API depth. Gaps in cloud-native tooling and seniority. Worth interviewing for a mid-level opening.",
  "recommendation": "Potential Match"
}}

Scoring rules:
- Be objective and evidence-based. Only score what is present in the resume.
- skills_match.matched_skills: skills from required_skills found in resume (list strings)
- skills_match.missing_skills: skills from required_skills NOT found in resume (list strings)
- recommendation must be EXACTLY one of: "Strong Match", "Potential Match", "Weak Match"
- Strong Match = candidate is clearly qualified and meets most requirements
- Potential Match = candidate is partially qualified, worth a closer look
- Weak Match = candidate clearly lacks key requirements"""


def compute_overall_score(dimensions: dict) -> int:
    """Compute weighted overall score from dimension scores."""
    total = 0.0
    for key, weight in WEIGHTS.items():
        dim = dimensions.get(key, {})
        score = dim.get("score", 0)
        total += score * weight
    return round(total)


def get_recommendation(overall_score: int) -> str:
    if overall_score >= 80:
        return "Strong Match"
    elif overall_score >= 60:
        return "Potential Match"
    else:
        return "Weak Match"


async def score_resume(jd_requirements: dict, resume_text: str, candidate_name: str) -> dict:
    """
    Pass 2: Score a resume against structured JD requirements.
    Returns a dict with overall_score, dimensions, summary, recommendation.
    """
    client = get_client()
    jd_str = json.dumps(jd_requirements, indent=2)

    response = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "user",
                "content": SCORING_PROMPT.format(
                    jd_requirements=jd_str,
                    resume_text=resume_text[:6000],
                )
            }
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
        max_tokens=1500,
    )

    raw = response.choices[0].message.content
    try:
        result = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM returned invalid JSON for resume scoring: {e}\nRaw: {raw[:500]}")

    dimensions = result.get("dimensions", {})

    # Validate all expected dimensions exist
    for key in WEIGHTS:
        if key not in dimensions:
            dimensions[key] = {"score": 0, "note": "Could not evaluate this dimension."}

    # Ensure skills_match has list fields
    sm = dimensions.get("skills_match", {})
    sm.setdefault("matched_skills", [])
    sm.setdefault("missing_skills", [])
    sm.setdefault("note", "")

    # Compute overall score using our weights (not LLM's)
    overall = compute_overall_score(dimensions)
    recommendation = get_recommendation(overall)

    return {
        "candidate_name": candidate_name,
        "overall_score": overall,
        "dimensions": dimensions,
        "summary": result.get("summary", "No summary generated."),
        "recommendation": recommendation,
    }
