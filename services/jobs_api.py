"""Arbeitnow REST API integration with bounded pagination, error handling, and text normalization."""

from __future__ import annotations

import html
import re
from typing import Any
import requests
import streamlit as st

ARBEITNOW_API_URL = "https://www.arbeitnow.com/api/job-board-api"
API_TIMEOUT_SECONDS = 15
PROVIDER_NAME = "Arbeitnow"
GEOGRAPHIC_COVERAGE = (
    "Arbeitnow primarily indexes technology vacancies across European hubs "
    "(London, Berlin, Munich, Paris, Zurich) alongside global Remote positions. "
    "Coverage for domestic non-European regions (such as India or US domestic cities) "
    "is limited. Candidates searching these locations should consider selecting 'Remote only'."
)


def clean_html_description(raw_html: Any) -> str:
    """Normalize HTML or entity-encoded job descriptions into safe, cleanly formatted plain text."""
    if not raw_html:
        return "No description provided."

    text = str(raw_html)
    # 1. Unescape HTML entities twice to cleanly handle double-escaped entities (e.g. &amp;amp; -> &)
    text = html.unescape(html.unescape(text))

    # 2. Convert line break and paragraph/list tags to line breaks
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</?(?:p|div|h[1-6])>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<li>", "\n• ", text, flags=re.IGNORECASE)
    text = re.sub(r"</li>", "", text, flags=re.IGNORECASE)

    # 3. Strip all remaining HTML tags
    text = re.sub(r"<[^>]+>", " ", text)

    # 4. Clean up excessive whitespace while preserving distinct paragraphs
    paragraphs = [re.sub(r"[ \t]+", " ", p).strip() for p in text.split("\n")]
    cleaned = "\n".join(p for p in paragraphs if p)
    return cleaned.strip() or "No description provided."


def parse_job_payload(raw_item: dict[str, Any]) -> dict[str, Any]:
    """Extract, validate, and normalize raw fields from an Arbeitnow job dictionary."""
    slug = str(raw_item.get("slug") or "")
    url = str(raw_item.get("url") or "")
    title = str(raw_item.get("title") or "Untitled Job").strip()
    company = str(raw_item.get("company_name") or "Confidential").strip()
    location = str(raw_item.get("location") or "Remote / Unspecified").strip()
    is_remote = bool(raw_item.get("remote"))

    tags = raw_item.get("tags") or []
    if not isinstance(tags, list):
        tags = [str(tags)]
    clean_tags = [str(t).strip() for t in tags if str(t).strip()]

    description_raw = raw_item.get("description")
    description_clean = clean_html_description(description_raw)

    external_id = f"arbeitnow_{slug}" if slug else f"arbeitnow_{hash(url or title)}"

    return {
        "external_job_id": external_id,
        "slug": slug,
        "title": title,
        "company_name": company,
        "company": company,
        "location": location,
        "remote": is_remote,
        "category": ", ".join(clean_tags[:3]) if clean_tags else "Technology",
        "salary": "Not provided",  # Arbeitnow API does not supply structured salary data
        "url": url,
        "description": description_clean,
        "tags": clean_tags,
        "created_at": raw_item.get("created_at"),
    }


def fetch_arbeitnow_jobs(
    max_pages: int = 1,
) -> tuple[list[dict[str, Any]], str | None, int]:
    """Fetch jobs from the official Arbeitnow Job Board API with bounded pagination.
    
    Returns:
        (jobs_list, error_message, total_retrieved)
    """
    all_jobs: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    headers = {
        "Accept": "application/json",
        "User-Agent": "JobSearchApp-StudentProject/1.0",
    }

    current_url = ARBEITNOW_API_URL

    for page_idx in range(1, max_pages + 1):
        try:
            params = {"page": page_idx} if page_idx > 1 else {}
            response = requests.get(
                ARBEITNOW_API_URL,
                params=params,
                headers=headers,
                timeout=API_TIMEOUT_SECONDS,
            )
            response.raise_for_status()

            payload = response.json()
            if not isinstance(payload, dict):
                return [], "Unexpected response format from Arbeitnow API.", 0

            data_list = payload.get("data", [])
            if not isinstance(data_list, list):
                break

            for item in data_list:
                if isinstance(item, dict):
                    parsed = parse_job_payload(item)
                    if parsed["external_job_id"] not in seen_ids:
                        all_jobs.append(parsed)
                        seen_ids.add(parsed["external_job_id"])

            links = payload.get("links") or {}
            next_url = links.get("next")
            if not next_url:
                break

        except requests.Timeout:
            err = f"Connection timed out while contacting Arbeitnow API (attempted page {page_idx})."
            return all_jobs, err, len(all_jobs)
        except requests.ConnectionError:
            err = "Unable to connect to Arbeitnow API. Please check your internet connection."
            return all_jobs, err, len(all_jobs)
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else "Unknown"
            err = f"Arbeitnow API returned HTTP error status {status}."
            return all_jobs, err, len(all_jobs)
        except ValueError:
            err = "Arbeitnow API returned non-JSON response data."
            return all_jobs, err, len(all_jobs)
        except Exception as exc:
            err = f"Unexpected error while fetching jobs: {str(exc)}"
            return all_jobs, err, len(all_jobs)

    return all_jobs, None, len(all_jobs)


@st.cache_data(ttl=900, show_spinner=False)
def get_cached_api_jobs(max_pages: int = 1) -> tuple[list[dict[str, Any]], str | None, int]:
    """Streamlit cached wrapper for Arbeitnow API queries with 15-minute TTL.
    Database writes are NEVER cached.
    """
    return fetch_arbeitnow_jobs(max_pages=max_pages)
