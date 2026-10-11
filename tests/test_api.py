"""Tests for Arbeitnow REST API integration, HTML cleaning, and error handling."""

from unittest.mock import patch, MagicMock
import requests
import pytest
from services.jobs_api import (
    clean_html_description,
    parse_job_payload,
    fetch_arbeitnow_jobs,
)


def test_clean_html_description():
    """Verify conversion of HTML entities, paragraphs, lists, and stripping tags."""
    raw = (
        "&lt;div class=&quot;intro&quot;&gt;"
        "&lt;p&gt;We are hiring a &amp;amp; talented engineer!&lt;/p&gt;"
        "&lt;ul&gt;&lt;li&gt;Python&lt;/li&gt;&lt;li&gt;MySQL&lt;/li&gt;&lt;/ul&gt;"
        "&lt;/div&gt;"
    )
    cleaned = clean_html_description(raw)
    assert "<div" not in cleaned
    assert "&lt;" not in cleaned
    assert "• Python" in cleaned
    assert "• MySQL" in cleaned
    assert "& talented engineer!" in cleaned


def test_parse_job_payload_with_missing_fields():
    """Verify graceful handling of incomplete or missing API response fields."""
    partial_raw = {
        "slug": "sample-role-123",
        "title": None,
        "company_name": None,
        "tags": None,
        "location": None,
        "remote": True,
        "url": "https://example.com/job",
        "description": None,
        "created_at": 1791676517,
    }
    parsed = parse_job_payload(partial_raw)
    assert parsed["external_job_id"] == "arbeitnow_sample-role-123"
    assert parsed["title"] == "Untitled Job"
    assert parsed["company"] == "Confidential"
    assert parsed["salary"] == "Not provided"
    assert parsed["remote"] is True
    assert parsed["tags"] == []
    assert parsed["description"] == "No description provided."


@patch("requests.get")
def test_fetch_jobs_timeout_handling(mock_get):
    """Verify graceful error reporting when API times out."""
    mock_get.side_effect = requests.Timeout("Connection timed out")
    jobs, error, total = fetch_arbeitnow_jobs(max_pages=1)
    assert jobs == []
    assert error is not None
    assert "timed out" in error.lower()
    assert total == 0


@patch("requests.get")
def test_fetch_jobs_http_error(mock_get):
    """Verify graceful handling of non-200 HTTP responses."""
    mock_response = MagicMock()
    mock_response.status_code = 503
    mock_get.side_effect = requests.HTTPError(response=mock_response)
    jobs, error, total = fetch_arbeitnow_jobs(max_pages=1)
    assert jobs == []
    assert error is not None
    assert "503" in error


@patch("requests.get")
def test_fetch_jobs_invalid_json(mock_get):
    """Verify graceful handling of invalid JSON response."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.side_effect = ValueError("Invalid JSON")
    mock_get.return_value = mock_response
    jobs, error, total = fetch_arbeitnow_jobs(max_pages=1)
    assert jobs == []
    assert error is not None
    assert "non-json" in error.lower()
