"""Tests for deterministic 80/20 ranking, blank inputs, and remote filtering."""

# pyrefly: ignore [missing-import]
import pytest
from datetime import date
from services.ranking import evaluate_job, rank_jobs


def test_ranking_weights_both_present():
    """Verify 80% skill and 20% location weighted score calculation."""
    job = {
        "title": "Backend Python Developer",
        "tags": ["Python", "Docker"],
        "description": "Looking for Python specialist in Berlin.",
        "location": "Berlin, Germany",
        "remote": False,
        "external_job_id": "job_1",
    }
    # Candidate asks for Python and SQL (1 of 2 matched -> 50% skill coverage)
    # Candidate asks for location "Berlin" -> Direct match (100% location score)
    # Expected overall = 0.8 * 50.0 + 0.2 * 100.0 = 40.0 + 20.0 = 60.0
    eval_res = evaluate_job(
        job=job,
        requested_skills=["python", "sql"],
        preferred_location="Berlin",
        remote_only=False,
    )
    assert eval_res is not None
    assert eval_res["location_score"] == 100.0
    assert eval_res["skill_score"] == 50.0
    assert eval_res["relevance_score"] == 60.0
    assert "80% Skills" in eval_res["score_explanation"]
    assert "20% Location" in eval_res["score_explanation"]


def test_blank_location_input():
    """Verify that when location is blank, score is derived 100% from skills."""
    job = {
        "title": "Data Analyst",
        "tags": ["SQL", "Power BI"],
        "description": "SQL and dashboards.",
        "location": "Munich",
        "remote": False,
        "external_job_id": "job_2",
    }
    # Requested skills: SQL and Power BI (2 of 2 matched -> 100% skill coverage)
    eval_res = evaluate_job(
        job=job,
        requested_skills=["sql", "power bi"],
        preferred_location="",
        remote_only=False,
    )
    assert eval_res is not None
    assert eval_res["skill_score"] == 100.0
    assert eval_res["relevance_score"] == 100.0
    assert "100% Skills" in eval_res["score_explanation"]


def test_blank_skills_input():
    """Verify that when skills are blank, score is derived 100% from location."""
    job = {
        "title": "Product Manager",
        "tags": [],
        "description": "Managing tech products.",
        "location": "London, UK",
        "remote": False,
        "external_job_id": "job_3",
    }
    eval_res = evaluate_job(
        job=job,
        requested_skills=[],
        preferred_location="London",
        remote_only=False,
    )
    assert eval_res is not None
    assert eval_res["location_score"] == 100.0
    assert eval_res["relevance_score"] == 100.0
    assert "100% Location" in eval_res["score_explanation"]


def test_both_inputs_blank_raises_validation_error():
    """Verify that if both skills and location are blank, a validation error is raised."""
    with pytest.raises(ValueError, match="Please provide at least one skill or a preferred location"):
        rank_jobs(jobs=[], skill_query="", preferred_location="", remote_only=False)


def test_remote_only_hard_filtering():
    """Verify that non-remote jobs are strictly excluded when remote_only is enabled."""
    jobs = [
        {"title": "Role 1", "location": "Berlin", "remote": False, "external_job_id": "r1"},
        {"title": "Role 2", "location": "Remote", "remote": True, "external_job_id": "r2"},
    ]
    ranked = rank_jobs(
        jobs=jobs,
        skill_query="role",
        preferred_location="",
        remote_only=True,
    )
    assert len(ranked) == 1
    assert ranked[0]["job"]["external_job_id"] == "r2"


def test_deterministic_sorting_order():
    """Verify ranking order: Score DESC, then Posted Date DESC, then External ID ASC."""
    jobs = [
        # Job A: lower score
        {"title": "Junior Python Dev", "tags": [], "description": "", "location": "", "remote": False, "posted_date": date(2026, 10, 5), "external_job_id": "a"},
        # Job B: higher score, older date
        {"title": "Senior Python and SQL Dev", "tags": ["Python", "SQL"], "description": "", "location": "", "remote": False, "posted_date": date(2026, 10, 1), "external_job_id": "b"},
        # Job C: same high score as B, but newer date
        {"title": "Senior Python and SQL Dev", "tags": ["Python", "SQL"], "description": "", "location": "", "remote": False, "posted_date": date(2026, 10, 8), "external_job_id": "c"},
    ]
    ranked = rank_jobs(
        jobs=jobs,
        skill_query="Python, SQL",
        preferred_location="",
        remote_only=False,
    )
    ranked_ids = [r["job"]["external_job_id"] for r in ranked]
    # C should rank before B because same score but C is newer
    # Both B and C rank before A
    assert ranked_ids[0] == "c"
    assert ranked_ids[1] == "b"
    assert ranked_ids[2] == "a"
