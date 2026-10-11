"""Deterministic, explainable job ranking and multi-attribute scoring service."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Iterable

from .skill_extraction import (
    parse_skills_input,
    match_skills_against_job,
    normalize_skill,
)


def evaluate_job(
    job: dict[str, Any],
    requested_skills: list[str],
    preferred_location: str,
    remote_only: bool,
) -> dict[str, Any] | None:
    """Evaluate a single job against candidate criteria.
    Returns scoring details dictionary or None if excluded by hard filters.
    """
    is_remote = bool(job.get("remote"))
    job_location = str(job.get("location") or "").strip()
    title = str(job.get("title") or "")
    tags = job.get("tags") or []
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    description = str(job.get("description") or "")

    # Hard filter: Remote-only
    if remote_only and not is_remote:
        return None

    has_skills = bool(requested_skills)
    has_location = bool(preferred_location.strip())

    if not has_skills and not has_location:
        raise ValueError("Please provide at least one skill or a preferred location.")

    # 1. Skill scoring
    matched_skills: list[str] = []
    missing_skills: list[str] = []
    title_matches: set[str] = set()
    skill_score = 0.0

    if has_skills:
        matched_skills, missing_skills, title_matches = match_skills_against_job(
            requested_skills=requested_skills,
            title=title,
            tags=tags,
            description=description,
        )
        base_coverage = (len(matched_skills) / len(requested_skills)) * 100.0
        skill_score = round(base_coverage, 2)

    # 2. Location scoring
    location_score = 0.0
    location_reason = "No location requested"

    if has_location:
        target_loc = preferred_location.strip().lower()
        curr_loc = job_location.lower()

        if target_loc in curr_loc:
            location_score = 100.0
            location_reason = f"Direct match with '{preferred_location}'"
        elif is_remote or "remote" in curr_loc or "homeoffice" in curr_loc:
            location_score = 75.0
            location_reason = "Remote position (accessible from anywhere)"
        else:
            location_score = 0.0
            location_reason = f"Location '{job_location or 'Not specified'}' does not match '{preferred_location}'"

    # 3. Overall Weighted Score (80% skills, 20% location)
    if has_skills and has_location:
        overall_score = round(0.80 * skill_score + 0.20 * location_score, 2)
        score_explanation = (
            f"80% Skills ({skill_score:.1f}%) + 20% Location ({location_score:.1f}%) = {overall_score:.1f}%. "
            f"Matched {len(matched_skills)} of {len(requested_skills)} skills. {location_reason}."
        )
    elif has_skills:
        overall_score = round(skill_score, 2)
        score_explanation = (
            f"100% Skills ({skill_score:.1f}%) [Location criteria left blank]. "
            f"Matched {len(matched_skills)} of {len(requested_skills)} skills."
        )
    else:
        overall_score = round(location_score, 2)
        score_explanation = (
            f"100% Location ({location_score:.1f}%) [Skill criteria left blank]. {location_reason}."
        )

    # Convert posted date for deterministic sorting
    posted_date_obj: date | None = None
    raw_posted = job.get("posted_date") or job.get("created_at")
    if isinstance(raw_posted, (int, float)):
        posted_date_obj = datetime.fromtimestamp(raw_posted).date()
    elif isinstance(raw_posted, date):
        posted_date_obj = raw_posted
    elif isinstance(raw_posted, str):
        try:
            posted_date_obj = datetime.fromisoformat(raw_posted[:10]).date()
        except ValueError:
            posted_date_obj = None

    return {
        "job": job,
        "relevance_score": overall_score,
        "skill_score": skill_score,
        "location_score": location_score,
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
        "title_matches": list(title_matches),
        "location_reason": location_reason,
        "score_explanation": score_explanation,
        "posted_date": posted_date_obj,
    }


def rank_jobs(
    jobs: list[dict[str, Any]],
    skill_query: str,
    preferred_location: str,
    remote_only: bool = False,
    min_score: float = 0.0,
) -> list[dict[str, Any]]:
    """Filter, evaluate, and rank a collection of jobs deterministically.
    
    Sorting hierarchy:
    1. Relevance Score (Descending)
    2. Posted Date (Descending, None last)
    3. External Job ID / Slug (Ascending, stable tie-breaker)
    """
    requested_skills = parse_skills_input(skill_query)
    clean_location = preferred_location.strip()

    if not requested_skills and not clean_location:
        raise ValueError("Please provide at least one skill or a preferred location.")

    evaluated: list[dict[str, Any]] = []

    for job in jobs:
        evaluation = evaluate_job(
            job=job,
            requested_skills=requested_skills,
            preferred_location=clean_location,
            remote_only=remote_only,
        )
        if evaluation is not None and evaluation["relevance_score"] >= min_score:
            evaluated.append(evaluation)

    # Deterministic sorting helper
    def sort_key(item: dict[str, Any]) -> tuple[float, int, str]:
        score = item["relevance_score"]
        dt = item.get("posted_date")
        dt_ordinal = dt.toordinal() if dt else 0
        ext_id = str(item["job"].get("external_job_id") or item["job"].get("slug") or "")
        return (-score, -dt_ordinal, ext_id)

    evaluated.sort(key=sort_key)

    # Assign 1-based rank position
    for idx, item in enumerate(evaluated, start=1):
        item["rank_position"] = idx

    return evaluated
