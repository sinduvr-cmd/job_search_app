"""Saved Jobs view displaying persistent bookmarks from MySQL."""

from __future__ import annotations

import html
from typing import Any
import streamlit as st

from database.repository import get_saved_jobs, toggle_save_job
from ui.search_view import render_job_card


def render_saved_jobs_view(current_user: dict[str, Any]) -> None:
    """Render all bookmarked job listings for the active candidate profile."""
    st.subheader(f"Saved Jobs for {current_user['name']}")

    st.info(
        "💡 **Notice**: These jobs are saved locally in your MySQL `saved_jobs` table. "
        "Because external employer postings expire over time, verify current vacancy status via the 'View & Apply' link."
    )

    try:
        saved_jobs = get_saved_jobs(current_user["user_id"])
    except Exception as exc:
        st.error(f"Could not load saved jobs: {exc}")
        return

    if not saved_jobs:
        st.warning("You have not saved any jobs yet. Browse vacancies under 'Search Jobs' and click '☆ Save Job' to bookmark them.")
        return

    st.markdown(f"**Total Bookmarks: {len(saved_jobs)}**")

    for idx, job in enumerate(saved_jobs, start=1):
        job_id = job["job_id"]
        title = str(job.get("title") or "Untitled Role")
        company = str(job.get("company_name") or job.get("company") or "Confidential")
        location = str(job.get("location") or "Location Not Specified")
        is_remote = bool(job.get("remote"))
        posted_date = str(job.get("posted_date") or "Recently")
        saved_at = job.get("saved_at").strftime("%Y-%m-%d %H:%M") if job.get("saved_at") else "Recently"
        url = str(job.get("url") or "#")
        tags = job.get("tags") or []
        description = str(job.get("description") or "No description provided.")

        with st.container():
            st.markdown(
                f"""
                <div class="job-card">
                    <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                        <div>
                            <span class="badge-rank">Saved #{idx}</span>
                            {f'<span class="badge-remote" style="margin-left: 0.4rem;">🌐 Remote</span>' if is_remote else ''}
                        </div>
                        <div style="font-size: 0.8rem; color: #94a3b8;">
                            Bookmarked on: {html.escape(saved_at)}
                        </div>
                    </div>
                    <h3 style="margin: 0.3rem 0; color: #1e1b4b; font-size: 1.25rem; font-weight: 700;">
                        {html.escape(title)}
                    </h3>
                    <div style="color: #475569; font-weight: 600; font-size: 0.95rem; margin-bottom: 0.5rem;">
                        🏢 {html.escape(company)} &nbsp;·&nbsp; 📍 {html.escape(location)} &nbsp;·&nbsp; ◷ {html.escape(posted_date)}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # Skill tags
            if tags:
                badge_html = [f'<span class="badge-skill">{html.escape(str(t))}</span>' for t in tags[:6]]
                st.markdown(f"<div style='margin-top: -0.8rem; margin-bottom: 0.5rem;'>{''.join(badge_html)}</div>", unsafe_allow_html=True)

            with st.expander("📄 View Description"):
                st.write(description)

            b_c1, b_c2, _ = st.columns([1.5, 1.5, 3])
            with b_c1:
                st.link_button("View & Apply ↗", url, use_container_width=True)
            with b_c2:
                if st.button("🗑 Remove Bookmark", key=f"unsave_{job_id}_{idx}", use_container_width=True):
                    toggle_save_job(current_user["user_id"], job_id)
                    st.success("Removed from bookmarks.")
                    st.rerun()

            st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
