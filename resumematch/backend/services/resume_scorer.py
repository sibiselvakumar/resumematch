import json
import logging
import os
import re
import time
from datetime import date
from typing import List, Optional, Tuple
from dotenv import load_dotenv
from .jd_analyzer import get_client, MODEL, SEED

load_dotenv()

logger = logging.getLogger("resumematch.resume_scorer")

# Resumes commonly put Education/Certifications last, after every job entry —
# a low cap here truncates those sections away before the model ever sees them
# (Llama 3.1's 128K-token context has ample room for a full resume, so this is
# generous on purpose rather than tight).
MAX_RESUME_CHARS = 20000

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
      "employment_history": [
        {{"title": "Backend Engineer", "company": "Acme Corp", "start_date": "2021-03", "end_date": "Present", "relevant_to_role": true}},
        {{"title": "QA Intern", "company": "Beta Inc", "start_date": "2019-06", "end_date": "2019-12", "relevant_to_role": false}}
      ],
      "note": "Backend Engineer role involved building production APIs directly aligned with this JD; internship was unrelated QA work"
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
- experience.employment_history: list EVERY job/role found in the resume, one entry per role
  - start_date / end_date: format "YYYY-MM" (use "YYYY" if the resume gives no month; use "Present" for an ongoing role)
  - relevant_to_role: true if that role's work is directly applicable to this job's required skills/domain, false otherwise
  - Do NOT state total years of experience anywhere — the system computes that from these dates. Use experience.note only for qualitative reasoning (e.g. what made a role relevant or not)
- recommendation must be EXACTLY one of: "Strong Match", "Potential Match", "Weak Match"
- Strong Match = candidate is clearly qualified and meets most requirements
- Potential Match = candidate is partially qualified, worth a closer look
- Weak Match = candidate clearly lacks key requirements"""


_YEAR_MONTH_RE = re.compile(r"^(\d{4})(?:-(\d{1,2}))?$")
_NUMERIC_SLASH_RE = re.compile(r"^(\d{1,2})[/-](\d{4})$")
_MONTH_NAME_RE = re.compile(r"^([A-Za-z]{3,9})[\s.'-]*(\d{2,4})$")
_ONGOING_TERMS = {"present", "current", "currently", "now", "ongoing", "to date", "till date"}
_MONTH_NAMES = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}


def _expand_two_digit_year(year: int) -> int:
    """"10" -> 2010, "99" -> 1999 — resumes rarely span before 1980."""
    return 2000 + year if year < 80 else 1900 + year


def _parse_month_index(value: Optional[str], *, end_of_period: bool) -> Optional[int]:
    """
    Parse a resume date string into an absolute month index (year*12+month).
    Handles ISO-ish forms the JD/scoring prompt asks for ("2021-03", "2021", "Present")
    as well as the raw formats resumes actually use ("Sep 2010", "Sep'10", "09/2010") —
    small models don't reliably normalize every resume's date style to the requested
    schema, so falling back to None here silently (and misleadingly) zeroes out a
    candidate's whole computed experience.
    """
    if not value or not isinstance(value, str):
        return None
    raw = value.strip()
    v = raw.lower()
    if v in _ONGOING_TERMS:
        today = date.today()
        return today.year * 12 + today.month

    m = _YEAR_MONTH_RE.match(raw)
    if m:
        year = int(m.group(1))
        if m.group(2):
            month = int(m.group(2))
            if not (1 <= month <= 12):
                return None
        else:
            # Year-only: approximate a full year (Jan for a start, Dec for an end).
            month = 12 if end_of_period else 1
        return year * 12 + month

    m = _NUMERIC_SLASH_RE.match(raw)
    if m:
        month, year = int(m.group(1)), int(m.group(2))
        if not (1 <= month <= 12):
            return None
        return year * 12 + month

    m = _MONTH_NAME_RE.match(raw)
    if m:
        month = _MONTH_NAMES.get(m.group(1).lower())
        if month is None:
            return None
        year = int(m.group(2))
        if len(m.group(2)) == 2:
            year = _expand_two_digit_year(year)
        return year * 12 + month

    return None


def _merge_month_ranges(ranges: List[Tuple[int, int]]) -> int:
    """Merge overlapping/adjacent (start, end) month-index ranges and sum the covered months, so concurrent roles aren't double-counted."""
    if not ranges:
        return 0
    ranges = sorted(ranges)
    merged = [ranges[0]]
    for start, end in ranges[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end + 1:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return sum(end - start + 1 for start, end in merged)


def compute_experience_years(employment_history: list) -> Tuple[float, float]:
    """
    Compute (total_years, relevant_years) from structured employment history via
    plain date arithmetic, instead of trusting the LLM's own year count — small
    models are unreliable at that arithmetic and give inconsistent totals for
    the same resume across runs.
    """
    total_ranges: List[Tuple[int, int]] = []
    relevant_ranges: List[Tuple[int, int]] = []
    for job in employment_history or []:
        if not isinstance(job, dict):
            continue
        start = _parse_month_index(job.get("start_date"), end_of_period=False)
        end = _parse_month_index(job.get("end_date"), end_of_period=True)
        if start is None or end is None or end < start:
            continue
        total_ranges.append((start, end))
        if job.get("relevant_to_role"):
            relevant_ranges.append((start, end))

    total_years = round(_merge_month_ranges(total_ranges) / 12, 1)
    relevant_years = round(_merge_month_ranges(relevant_ranges) / 12, 1)
    return total_years, relevant_years


def _format_years(n: float) -> str:
    return f"{n:g}"


def compute_overall_score(dimensions: dict, weights: dict = None) -> int:
    """Compute weighted overall score from dimension scores."""
    w = weights if weights is not None else WEIGHTS
    total = 0.0
    for key, weight in w.items():
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


async def score_resume(jd_requirements: dict, resume_text: str, candidate_name: str, weights: dict = None) -> dict:
    """
    Pass 2: Score a resume against structured JD requirements.
    Returns a dict with overall_score, dimensions, summary, recommendation.
    """
    client = get_client()
    jd_str = json.dumps(jd_requirements, indent=2)

    start = time.monotonic()
    try:
        response = await client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "user",
                    "content": SCORING_PROMPT.format(
                        jd_requirements=jd_str,
                        resume_text=resume_text[:MAX_RESUME_CHARS],
                    )
                }
            ],
            response_format={"type": "json_object"},
            temperature=0,
            max_tokens=1500,
            seed=SEED,
        )
    except Exception as e:
        elapsed = time.monotonic() - start
        status_code = getattr(e, "status_code", None)
        resp = getattr(e, "response", None)
        retry_after = resp.headers.get("retry-after") if resp is not None else None
        logger.error(
            "score_resume FAILED after %.1fs candidate=%r status=%s retry_after=%s error=%s",
            elapsed, candidate_name, status_code, retry_after, e,
        )
        raise
    elapsed = time.monotonic() - start
    logger.info("score_resume OK in %.1fs candidate=%r (model=%s)", elapsed, candidate_name, MODEL)

    raw = response.choices[0].message.content
    try:
        result = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM returned invalid JSON for resume scoring: {e}\nRaw: {raw[:500]}")

    dimensions = result.get("dimensions", {})

    # Validate all expected dimensions exist
    for key in (weights or WEIGHTS):
        if key not in dimensions:
            dimensions[key] = {"score": 0, "note": "Could not evaluate this dimension."}

    # Ensure skills_match has list fields
    sm = dimensions.get("skills_match", {})
    sm.setdefault("matched_skills", [])
    sm.setdefault("missing_skills", [])
    sm.setdefault("note", "")

    # Keep only skills that were actually in the JD's required_skills — small
    # models sometimes invent a plausible-looking but absent skill (e.g. a bare
    # "Azure" when the JD only lists "Azure OpenAI"), which would otherwise
    # render as a real requirement the candidate is missing.
    required_skills = jd_requirements.get("required_skills", []) or []
    canonical_skills = {s.strip().lower(): s for s in required_skills if isinstance(s, str)}

    def _sanitize_skills(skill_list: list) -> list:
        cleaned = []
        for skill in skill_list or []:
            if not isinstance(skill, str):
                continue
            canonical = canonical_skills.get(skill.strip().lower())
            if canonical is None:
                logger.info(
                    "score_resume: dropping hallucinated skill %r (not in required_skills) candidate=%r",
                    skill, candidate_name,
                )
            elif canonical not in cleaned:
                cleaned.append(canonical)
        return cleaned

    sm["matched_skills"] = _sanitize_skills(sm["matched_skills"])
    sm["missing_skills"] = _sanitize_skills(sm["missing_skills"])

    # A skill can't be both present and absent — if the model claims both,
    # trust "matched" since that reflects actual evidence found in the resume.
    contradicted = set(sm["matched_skills"]) & set(sm["missing_skills"])
    if contradicted:
        logger.info(
            "score_resume: skill(s) %r claimed as both matched and missing, keeping as matched candidate=%r",
            sorted(contradicted), candidate_name,
        )
        sm["missing_skills"] = [s for s in sm["missing_skills"] if s not in contradicted]

    # A required skill the model never mentioned in either list would otherwise
    # just vanish from the UI — counted against the score's denominator but
    # invisible on screen. Surface it as missing so what's counted is also shown.
    unaccounted = [
        canonical for canonical in canonical_skills.values()
        if canonical not in sm["matched_skills"] and canonical not in sm["missing_skills"]
    ]
    if unaccounted:
        logger.info(
            "score_resume: skill(s) %r never classified by model, treating as missing candidate=%r",
            unaccounted, candidate_name,
        )
        sm["missing_skills"].extend(unaccounted)

    # Replace the LLM's own skills_match score with one computed from its own
    # matched_skills list — the model's numeric self-rating and its structured
    # skill lists are two independent judgments and can disagree (e.g. every
    # required skill tagged as matched, yet a self-reported score of 80).
    if required_skills:
        sm["score"] = round(100 * len(sm["matched_skills"]) / len(required_skills))

    # Replace the LLM's own year count with one computed from its structured
    # employment_history — deterministic date math instead of model arithmetic.
    exp = dimensions.get("experience", {})
    employment_history = exp.pop("employment_history", [])
    llm_note = (exp.get("note") or "").strip()
    total_years, relevant_years = compute_experience_years(employment_history) if employment_history else (0, 0)
    if total_years > 0:
        years_summary = f"{_format_years(total_years)} years total, {_format_years(relevant_years)} directly relevant"
        exp["note"] = f"{years_summary}. {llm_note}" if llm_note else years_summary
    else:
        # Every date in employment_history failed to parse (or there was no history at
        # all) — showing "0 years total" here would misrepresent a parsing gap as a
        # measured fact, so fall back to the LLM's own qualitative note instead.
        exp["note"] = llm_note or "Could not determine employment dates from resume."
    dimensions["experience"] = exp

    # Compute overall score using our weights (not LLM's)
    overall = compute_overall_score(dimensions, weights)
    recommendation = get_recommendation(overall)

    return {
        "candidate_name": candidate_name,
        "overall_score": overall,
        "dimensions": dimensions,
        "summary": result.get("summary", "No summary generated."),
        "recommendation": recommendation,
    }
