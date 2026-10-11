"""Tests for skill normalization, aliases, and boundary-aware regex matching."""

import pytest
from services.skill_extraction import (
    normalize_skill,
    parse_skills_input,
    skill_matches_text,
    compile_skill_regex,
    match_skills_against_job,
    SKILL_ALIASES,
)


def test_normalize_skill_and_aliases():
    """Verify normalization of casing, whitespace, and tech aliases."""
    assert normalize_skill("  PYTHON  ") == "python"
    assert normalize_skill("js") == "javascript"
    assert normalize_skill("JS") == "javascript"
    assert normalize_skill("TS") == "typescript"
    assert normalize_skill("ML") == "machine learning"
    assert normalize_skill("postgres") == "postgresql"
    assert normalize_skill("k8s") == "kubernetes"
    assert normalize_skill("dotnet") == ".net"
    assert normalize_skill("csharp") == "c#"
    assert normalize_skill("cpp") == "c++"


def test_parse_skills_input():
    """Verify parsing comma-separated query into distinct normalized skills."""
    raw = " Python,  SQL, JS,  Machine Learning, python "
    parsed = parse_skills_input(raw)
    assert parsed == ["python", "sql", "javascript", "machine learning"]


def test_java_versus_javascript():
    """Verify boundary matching: Java MUST NOT match JavaScript, and vice versa."""
    # Java alone
    assert skill_matches_text("java", "We are looking for a Senior Java Developer.")
    assert skill_matches_text("java", "Core Java and Spring Boot experience.")
    assert not skill_matches_text("java", "Looking for a JavaScript developer.")
    assert not skill_matches_text("java", "Frontend React with JavaScript and HTML.")

    # JavaScript alone
    assert skill_matches_text("javascript", "Frontend React with JavaScript and HTML.")
    assert not skill_matches_text("javascript", "Backend Core Java and Hibernate role.")


def test_punctuation_sensitive_skills():
    """Verify boundary matching for C++, C#, and .NET without false positives."""
    # C++
    assert skill_matches_text("c++", "Seeking a High-Performance C++ Software Engineer.")
    assert skill_matches_text("c++", "Requires Modern C++ (C++17/C++20).")
    assert not skill_matches_text("c++", "Experience in C programming language.")
    assert not skill_matches_text("c++", "Frontend CSS and styling.")

    # C#
    assert skill_matches_text("c#", "Senior C# Backend Developer.")
    assert skill_matches_text("c#", "Stack: C#, ASP.NET, SQL Server.")
    assert not skill_matches_text("c#", "Only C programming.")

    # .NET
    assert skill_matches_text(".net", "Fullstack .NET Core Engineer.")
    assert skill_matches_text(".net", "Enterprise application built on dotnet.")
    assert not skill_matches_text(".net", "Network engineer.")

    # Single-letter C
    assert skill_matches_text("c", "Embedded programming in C and Assembly.")
    assert not skill_matches_text("c", "C++ and C# developer.")
    assert not skill_matches_text("c", "CSS and HTML.")


def test_match_skills_against_job():
    """Verify matching across title, tags, and description with title promotion."""
    requested = ["python", "sql", "docker", "aws"]
    title = "Senior Python Developer"
    tags = ["AWS", "Microservices"]
    description = "You will write SQL queries and deploy scalable services."

    matched, missing, title_matches = match_skills_against_job(
        requested_skills=requested,
        title=title,
        tags=tags,
        description=description,
    )

    assert set(matched) == {"python", "sql", "aws"}
    assert missing == ["docker"]
    assert title_matches == {"python"}
