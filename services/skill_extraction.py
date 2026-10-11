"""Skill normalization, alias expansion, and boundary-aware regex matching."""

from __future__ import annotations

import re
from typing import Iterable

# Canonical alias mapping for common tech acronyms and variants
SKILL_ALIASES: dict[str, str] = {
    "js": "javascript",
    "ts": "typescript",
    "py": "python",
    "react.js": "react",
    "reactjs": "react",
    "node.js": "nodejs",
    "nodejs": "nodejs",
    "vue.js": "vue",
    "vuejs": "vue",
    "ml": "machine learning",
    "dl": "deep learning",
    "nlp": "natural language processing",
    "cv": "computer vision",
    "ai": "artificial intelligence",
    "postgres": "postgresql",
    "k8s": "kubernetes",
    "aws": "amazon web services",
    "gcp": "google cloud platform",
    "powerbi": "power bi",
    "cplusplus": "c++",
    "cpp": "c++",
    "csharp": "c#",
    "c sharp": "c#",
    "dotnet": ".net",
}


def normalize_skill(skill: str) -> str:
    """Normalize skill name: trim, lowercase, collapse whitespace, and resolve known aliases."""
    cleaned = re.sub(r"\s+", " ", skill.strip().lower())
    return SKILL_ALIASES.get(cleaned, cleaned)


def parse_skills_input(query: str) -> list[str]:
    """Parse a comma-separated or whitespace-separated skill query into normalized distinct skills."""
    if not query or not query.strip():
        return []

    # Prefer comma separation; if no commas, split by semicolon or clean tokens
    if "," in query:
        raw_tokens = query.split(",")
    elif ";" in query:
        raw_tokens = query.split(";")
    else:
        # Check if single term or multi-word term
        raw_tokens = [query]

    skills: list[str] = []
    seen: set[str] = set()

    for token in raw_tokens:
        normalized = normalize_skill(token)
        if normalized and normalized not in seen:
            skills.append(normalized)
            seen.add(normalized)

    return skills


def compile_skill_regex(skill: str) -> re.Pattern:
    """Generate a boundary-aware regular expression for a specific skill.
    Correctly isolates standard words, single-character languages (C),
    and punctuation-sensitive terms (C++, C#, .NET).
    """
    clean = normalize_skill(skill)

    if clean == "c++":
        # Matches C++ without matching C or C#
        pattern = r"(?<![a-zA-Z0-9_])c\+\+(?![a-zA-Z0-9_+])"
    elif clean == "c#":
        # Matches C# without matching C or C++
        pattern = r"(?<![a-zA-Z0-9_])c#(?![a-zA-Z0-9_#])"
    elif clean in (".net", "dotnet"):
        # Matches .NET or dotnet
        pattern = r"(?:(?<![a-zA-Z0-9_])\.net(?![a-zA-Z0-9_])|(?<![a-zA-Z0-9_])dotnet(?![a-zA-Z0-9_]))"
    elif clean == "c":
        # Matches isolated 'C' language without matching C++, C#, CSS, or words containing C
        pattern = r"(?<![a-zA-Z0-9_+#.])c(?![a-zA-Z0-9_+#.])"
    elif clean in ("power bi", "machine learning", "deep learning", "data analysis", "natural language processing", "computer vision", "artificial intelligence"):
        # Multi-word phrase with internal whitespace flexibility
        words = clean.split()
        escaped_words = [re.escape(w) for w in words]
        pattern = r"(?<![a-zA-Z0-9_])" + r"\s+".join(escaped_words) + r"(?![a-zA-Z0-9_])"
    else:
        # Standard boundary-safe matching
        pattern = r"(?<![a-zA-Z0-9_])" + re.escape(clean) + r"(?![a-zA-Z0-9_])"

    return re.compile(pattern, re.IGNORECASE)


def skill_matches_text(skill: str, text: str) -> bool:
    """Check if the given skill appears in text using boundary-aware matching."""
    if not text or not skill:
        return False
    regex = compile_skill_regex(skill)
    return bool(regex.search(text))


def match_skills_against_job(
    requested_skills: Iterable[str],
    title: str,
    tags: Iterable[str],
    description: str,
) -> tuple[list[str], list[str], set[str]]:
    """Determine which requested skills are matched in the job title, tags, or description.
    Returns:
        (matched_skills, missing_skills, title_matched_skills)
    """
    matched: list[str] = []
    missing: list[str] = []
    title_matches: set[str] = set()

    normalized_tags = [str(t).strip().lower() for t in tags if t]
    combined_tags_text = " ".join(normalized_tags)

    for skill in requested_skills:
        clean_skill = str(skill).strip().lower()
        alias = SKILL_ALIASES.get(clean_skill)
        candidate_terms = [clean_skill]
        if alias and alias != clean_skill:
            candidate_terms.append(alias)

        in_title = any(skill_matches_text(term, title) for term in candidate_terms)
        in_tags = any(
            any(term == t for t in normalized_tags) or skill_matches_text(term, combined_tags_text)
            for term in candidate_terms
        )
        in_desc = any(skill_matches_text(term, description) for term in candidate_terms)

        if in_title:
            title_matches.add(clean_skill)

        if in_title or in_tags or in_desc:
            matched.append(clean_skill)
        else:
            missing.append(clean_skill)

    return matched, missing, title_matches
