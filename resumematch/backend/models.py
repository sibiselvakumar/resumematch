from pydantic import BaseModel
from typing import List, Optional


class SkillDimension(BaseModel):
    score: int
    matched_skills: List[str] = []
    missing_skills: List[str] = []
    note: str = ""


class BasicDimension(BaseModel):
    score: int
    note: str = ""


class Dimensions(BaseModel):
    skills_match: SkillDimension
    experience: BasicDimension
    role_alignment: BasicDimension
    education: BasicDimension
    responsibilities: BasicDimension


class ResumeResult(BaseModel):
    candidate_name: str
    overall_score: int
    dimensions: Dimensions
    summary: str
    recommendation: str  # "Strong Match" | "Potential Match" | "Weak Match"


class JDRequirements(BaseModel):
    required_skills: List[str] = []
    preferred_skills: List[str] = []
    min_experience_years: Optional[int] = None
    education_requirement: str = ""
    key_responsibilities: List[str] = []
    seniority_level: str = ""
    role_title: str = ""


class AnalyzeResponse(BaseModel):
    session_id: str
    jd_requirements: JDRequirements
    results: List[ResumeResult]
