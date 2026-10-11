"""Services package for API fetching, skill extraction, and ranking."""

from .jobs_api import (
    fetch_arbeitnow_jobs,
    get_cached_api_jobs,
    clean_html_description,
    GEOGRAPHIC_COVERAGE,
    PROVIDER_NAME,
)
from .skill_extraction import (
    normalize_skill,
    parse_skills_input,
    match_skills_against_job,
    skill_matches_text,
    compile_skill_regex,
    SKILL_ALIASES,
)
from .ranking import rank_jobs, evaluate_job

__all__ = [
    "fetch_arbeitnow_jobs",
    "get_cached_api_jobs",
    "clean_html_description",
    "GEOGRAPHIC_COVERAGE",
    "PROVIDER_NAME",
    "normalize_skill",
    "parse_skills_input",
    "match_skills_against_job",
    "skill_matches_text",
    "compile_skill_regex",
    "SKILL_ALIASES",
    "rank_jobs",
    "evaluate_job",
]
