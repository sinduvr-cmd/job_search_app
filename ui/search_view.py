"""Search Jobs view with interactive search form, skill chips, filters, and job cards."""

from __future__ import annotations

import html
import math
from typing import Any
import streamlit as st

from services.jobs_api import get_cached_api_jobs, GEOGRAPHIC_COVERAGE, PROVIDER_NAME
from services.ranking import rank_jobs
from database.repository import (
    save_search_transaction,
    toggle_save_job,
    get_saved_job_ids,
    get_cached_jobs_for_fallback,
)
from ui.components import render_metric_card

SUGGESTED_SKILLS = ["Python", "SQL", "Data Analysis", "Machine Learning", "Power BI", "Docker", "AWS"]
PAGE_SIZE = 8


def render_search_view(current_user: dict[str, Any]) -> None:
    """Render the primary job discovery and ranking workspace."""
    st.subheader("Job Search & Recommendation")

    # Informative provider coverage disclaimer
    with st.expander("ℹ️ Data Source & Geographic Coverage Notice", expanded=False):
        st.info(f"**Provider**: {PROVIDER_NAME} API\n\n{GEOGRAPHIC_COVERAGE}")

    # Initialize skill query in session state if missing
    if "skill_input_val" not in st.session_state:
        st.session_state["skill_input_val"] = "Python, SQL"
    if "location_input_val" not in st.session_state:
        st.session_state["location_input_val"] = ""
    if "remote_only_val" not in st.session_state:
        st.session_state["remote_only_val"] = False

    # Suggested Skill Chips
    st.markdown("**Quick Add Skills:**")
    chip_cols = st.columns(len(SUGGESTED_SKILLS))
    for idx, skill_chip in enumerate(SUGGESTED_SKILLS):
        if chip_cols[idx].button(f"+ {skill_chip}", key=f"chip_{skill_chip}", use_container_width=True):
            current_skills = [s.strip() for s in st.session_state["skill_input_val"].split(",") if s.strip()]
            if skill_chip.lower() not in [s.lower() for s in current_skills]:
                current_skills.append(skill_chip)
                st.session_state["skill_input_val"] = ", ".join(current_skills)
                st.rerun()

    # Search Form
    with st.form("search_form", clear_on_submit=False):
        col_skills, col_loc, col_remote = st.columns([3, 2, 1.2])

        with col_skills:
            skill_query = st.text_input(
                "Skills (comma-separated)",
                value=st.session_state["skill_input_val"],
                placeholder="e.g. Python, SQL, Machine Learning",
                help="Enter one or more skills separated by commas. Aliases like JS, ML, and C++ are supported.",
            )
        with col_loc:
            location_query = st.text_input(
                "Preferred Location",
                value=st.session_state["location_input_val"],
                placeholder="e.g. Berlin, London, Remote",
                help="Desired city or country. Leave blank to score purely on skill coverage.",
            )
        with col_remote:
            st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
            remote_only = st.checkbox(
                "Remote only",
                value=st.session_state["remote_only_val"],
                help="Hard filter: exclude all non-remote positions.",
            )

        submit_search = st.form_submit_button("🔍 Search & Rank Jobs", type="primary", use_container_width=True)

    # Search submission handling
    if submit_search:
        st.session_state["skill_input_val"] = skill_query
        st.session_state["location_input_val"] = location_query
        st.session_state["remote_only_val"] = remote_only

        if not skill_query.strip() and not location_query.strip():
            st.error("Validation Error: Please provide at least one skill or a preferred location.")
        else:
            with st.spinner(f"Fetching genuine vacancies from {PROVIDER_NAME} API..."):
                jobs_data, api_error, total_retrieved = get_cached_api_jobs(max_pages=1)

            if api_error and not jobs_data:
                st.error(f"API Error: {api_error}")
                st.warning("Would you like to search previously cached listings from your local database?")
                if st.button("Search Local Cached Database", key="btn_fallback_cache"):
                    cached_jobs, cache_time = get_cached_jobs_for_fallback(
                        query=skill_query,
                        location=location_query,
                        remote_only=remote_only,
                    )
                    if cached_jobs:
                        st.info(f"Loaded {len(cached_jobs)} cached jobs (last updated: {cache_time or 'Unknown'}).")
                        ranked = rank_jobs(
                            jobs=cached_jobs,
                            skill_query=skill_query,
                            preferred_location=location_query,
                            remote_only=remote_only,
                        )
                        st.session_state["active_results"] = ranked
                        st.session_state["active_query"] = {
                            "skills": skill_query,
                            "location": location_query,
                            "remote_only": remote_only,
                            "is_cached_fallback": True,
                        }
                        st.session_state["page_num"] = 1
                    else:
                        st.warning("No cached jobs available in local database.")
            else:
                if api_error:
                    st.warning(f"Note: {api_error}. Proceeding with {len(jobs_data)} retrieved jobs.")

                # Deterministic ranking
                ranked = rank_jobs(
                    jobs=jobs_data,
                    skill_query=skill_query,
                    preferred_location=location_query,
                    remote_only=remote_only,
                )

                # Persist search and results into MySQL in a single transaction
                try:
                    search_id = save_search_transaction(
                        user_id=current_user["user_id"],
                        skill_query=skill_query,
                        location=location_query,
                        remote_only=remote_only,
                        ranked_jobs=ranked,
                    )
                    st.success(f"Retrieved {total_retrieved} API jobs · Ranked {len(ranked)} matches · Saved as Search #{search_id} in MySQL.")
                except Exception as exc:
                    st.warning(f"Could not persist search to database: {exc}")

                st.session_state["active_results"] = ranked
                st.session_state["active_query"] = {
                    "skills": skill_query,
                    "location": location_query,
                    "remote_only": remote_only,
                    "is_cached_fallback": False,
                }
                st.session_state["page_num"] = 1

    # Display active search results
    active_results = st.session_state.get("active_results")
    if active_results is not None:
        st.divider()

        # Summary Metrics
        m1, m2, m3, m4 = st.columns(4)
        total_matches = len(active_results)
        top_score = f"{active_results[0]['relevance_score']:.0f}%" if active_results else "N/A"
        remote_matches = sum(1 for item in active_results if item["job"].get("remote"))

        render_metric_card(m1, "Ranked Matches", total_matches, "Matching criteria")
        render_metric_card(m2, "Top Relevance", top_score, "Best algorithmic fit")
        render_metric_card(m3, "Remote Roles", remote_matches, "Work from anywhere")
        render_metric_card(m4, "Current Profile", current_user["name"], current_user["email"])

        st.markdown("<div style='height: 15px;'></div>", unsafe_allow_html=True)

        # Filtering & Sorting controls (In-memory, does not call API or re-insert search)
        st.markdown("#### Filter & Refine Current Results")
        f1, f2, f3, f4 = st.columns([1.5, 2, 2, 1.5])

        with f1:
            remote_filter = st.selectbox(
                "Remote Filter",
                options=["All Roles", "Remote Only", "On-site / Specified Only"],
                key="filter_remote_mode",
            )
        with f2:
            all_companies = sorted(list({str(item["job"].get("company") or item["job"].get("company_name") or "") for item in active_results if item["job"].get("company")}))
            company_filter = st.selectbox(
                "Filter by Company",
                options=["All Companies"] + all_companies,
                key="filter_company",
            )
        with f3:
            min_score = st.slider(
                "Minimum Relevance Score",
                min_value=0,
                max_value=100,
                value=0,
                step=5,
                key="filter_min_score",
            )
        with f4:
            sort_by = st.selectbox(
                "Sort Results",
                options=["Relevance Score", "Newest Date"],
                key="filter_sort",
            )

        # Apply in-memory filters
        filtered_list = active_results.copy()
        if remote_filter == "Remote Only":
            filtered_list = [item for item in filtered_list if item["job"].get("remote")]
        elif remote_filter == "On-site / Specified Only":
            filtered_list = [item for item in filtered_list if not item["job"].get("remote")]

        if company_filter != "All Companies":
            filtered_list = [item for item in filtered_list if (item["job"].get("company") or item["job"].get("company_name")) == company_filter]

        if min_score > 0:
            filtered_list = [item for item in filtered_list if item["relevance_score"] >= min_score]

        if sort_by == "Newest Date":
            def date_key(item: dict[str, Any]) -> int:
                dt = item.get("posted_date")
                return dt.toordinal() if dt else 0
            filtered_list.sort(key=date_key, reverse=True)
        else:
            filtered_list.sort(key=lambda item: item["relevance_score"], reverse=True)

        st.markdown(f"**Showing {len(filtered_list)} filtered results:**")

        if not filtered_list:
            st.info("No job listings match your active filters. Try lowering the minimum score or clearing company filters.")
            return

        # Pagination logic
        total_pages = max(1, math.ceil(len(filtered_list) / PAGE_SIZE))
        page_num = st.session_state.get("page_num", 1)
        if page_num > total_pages:
            page_num = 1
            st.session_state["page_num"] = 1

        start_idx = (page_num - 1) * PAGE_SIZE
        end_idx = min(start_idx + PAGE_SIZE, len(filtered_list))
        current_page_items = filtered_list[start_idx:end_idx]

        # Retrieve user's current saved job IDs for live bookmark status
        saved_job_ids = set()
        try:
            saved_job_ids = get_saved_job_ids(current_user["user_id"])
        except Exception:
            pass

        # Render Job Cards
        for idx, item in enumerate(current_page_items, start=start_idx + 1):
            render_job_card(
                item=item,
                rank_pos=idx,
                current_user=current_user,
                is_saved=(item["job"].get("job_id") in saved_job_ids) if item["job"].get("job_id") else False,
            )

        # Pagination controls
        p_col1, p_col2, p_col3 = st.columns([1, 2, 1])
        with p_col1:
            if page_num > 1 and st.button("⬅ Previous Page", key="btn_prev_page", use_container_width=True):
                st.session_state["page_num"] = page_num - 1
                st.rerun()
        with p_col2:
            st.markdown(f"<div style='text-align: center; line-height: 38px; color: #64748b; font-weight: 600;'>Page {page_num} of {total_pages}</div>", unsafe_allow_html=True)
        with p_col3:
            if page_num < total_pages and st.button("Next Page ➡", key="btn_next_page", use_container_width=True):
                st.session_state["page_num"] = page_num + 1
                st.rerun()
    else:
        st.info("Enter your skills and target location above, then click **Search & Rank Jobs** to view recommended positions.")


def render_job_card(
    item: dict[str, Any],
    rank_pos: int,
    current_user: dict[str, Any],
    is_saved: bool,
) -> None:
    """Render an individual job listing card with score pill, badges, and action buttons."""
    job = item.get("job", item)
    score = float(item.get("relevance_score", 0.0))
    title = str(job.get("title") or "Untitled Role")
    company = str(job.get("company_name") or job.get("company") or "Confidential")
    location = str(job.get("location") or "Location Not Specified")
    is_remote = bool(job.get("remote"))
    posted_date = str(item.get("posted_date") or job.get("posted_date") or "Recently")
    url = str(job.get("url") or "#")
    salary = "Not provided"  # Truthful: Arbeitnow does not provide structured salary
    description = str(job.get("description") or "No description available.")

    matched_skills = item.get("matched_skills") or []
    missing_skills = item.get("missing_skills") or []
    explanation = item.get("score_explanation") or f"Overall Match: {score:.1f}%"
    job_id = job.get("job_id") or item.get("job_id")

    with st.container():
        remote_badge = f'<span class="badge-remote" style="margin-left: 0.4rem;">🌐 Remote</span>' if is_remote else ''
        card_html = (
            f'<div class="job-card">'
            f'<div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.5rem;">'
            f'<div>'
            f'<span class="badge-rank">#{rank_pos}</span>'
            f'<span class="badge-match" style="margin-left: 0.4rem;">{score:.0f}% Match</span>'
            f'{remote_badge}'
            f'</div>'
            f'<div style="font-size: 0.8rem; color: #94a3b8; font-weight: 500;">'
            f'Posted: {html.escape(posted_date)}'
            f'</div>'
            f'</div>'
            f'<h3 style="margin: 0.2rem 0; color: #1e1b4b; font-size: 1.25rem; font-weight: 700;">'
            f'{html.escape(title)}'
            f'</h3>'
            f'<div style="color: #475569; font-weight: 600; font-size: 0.95rem; margin-bottom: 0.5rem;">'
            f'🏢 {html.escape(company)} &nbsp;·&nbsp; 📍 {html.escape(location)} &nbsp;·&nbsp; 💰 {html.escape(salary)}'
            f'</div>'
            f'</div>'
        )
        st.markdown(card_html, unsafe_allow_html=True)

        # Skill Badges
        tags = job.get("tags") or []
        badge_html = []
        for s in matched_skills:
            badge_html.append(f'<span class="badge-skill-match">✓ {html.escape(s)}</span>')
        for t in tags[:6]:
            if t.lower() not in [m.lower() for m in matched_skills]:
                badge_html.append(f'<span class="badge-skill">{html.escape(str(t))}</span>')

        if badge_html:
            st.markdown(f"<div style='margin-top: -0.8rem; margin-bottom: 0.5rem;'>{''.join(badge_html)}</div>", unsafe_allow_html=True)

        # Score Explanation Expander
        with st.expander("📊 Score Breakdown & Matching Details"):
            st.markdown(f"**Explanation**: {explanation}")
            if matched_skills:
                st.markdown(f"**Matched Requested Skills**: {', '.join(matched_skills)}")
            if missing_skills:
                st.markdown(f"**Missing Requested Skills**: {', '.join(missing_skills)}")
            st.markdown(f"**Location Evaluation**: {item.get('location_reason', 'N/A')}")

        # Description Expander
        with st.expander("📄 View Job Description"):
            st.write(description)

        # Action Buttons: Apply Link & Save/Bookmark Toggle
        btn_c1, btn_c2, _ = st.columns([1.5, 1.5, 3])
        with btn_c1:
            st.link_button("View & Apply ↗", url, use_container_width=True)

        with btn_c2:
            if job_id:
                label = "★ Saved" if is_saved else "☆ Save Job"
                if st.button(label, key=f"save_{job_id}_{rank_pos}", use_container_width=True):
                    new_status = toggle_save_job(current_user["user_id"], job_id)
                    st.rerun()
            else:
                st.caption("Save available for imported roles")

        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
