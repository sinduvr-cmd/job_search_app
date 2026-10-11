"""My Searches view to inspect past search history and reload saved ranked results."""

from __future__ import annotations

from typing import Any
import pandas as pd
import streamlit as st

from database.repository import (
    get_user_searches,
    get_search_results_by_id,
    get_saved_job_ids,
)
from services.jobs_api import get_cached_api_jobs
from services.ranking import rank_jobs
from database.repository import save_search_transaction
from ui.search_view import render_job_card


def render_history_view(current_user: dict[str, Any]) -> None:
    """Render historical searches and allow direct inspection or re-running."""
    st.subheader(f"Search History for {current_user['name']}")
    st.caption(f"Profile: {current_user['email']} · All searches are persisted in MySQL.")

    try:
        searches = get_user_searches(current_user["user_id"])
    except Exception:
        st.warning("⚠️ Database is currently disconnected. Connect MySQL to inspect and reload past search history.")
        return

    if not searches:
        st.info("No searches recorded yet for this profile. Perform a search in 'Search Jobs' to see history here.")
        return

    # Render history overview table
    summary_data = []
    for s in searches:
        summary_data.append({
            "Search ID": f"#{s['search_id']}",
            "Skill Query": s["skill_query"] or "(None)",
            "Location": s["location"] or "(Any)",
            "Remote Only": "Yes" if s["remote_only"] else "No",
            "Results Count": s["result_count"],
            "Timestamp": s["created_at"].strftime("%Y-%m-%d %H:%M") if s["created_at"] else "N/A",
        })

    st.dataframe(pd.DataFrame(summary_data), use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("#### Inspect or Rerun a Past Search")

    search_options = {
        f"Search #{s['search_id']}: '{s['skill_query'] or 'Any'}' in '{s['location'] or 'Any'}' ({s['created_at'].strftime('%b %d, %H:%M') if s['created_at'] else ''})": s
        for s in searches
    }

    selected_label = st.selectbox("Select a previous search to open:", options=list(search_options.keys()))
    selected_search = search_options[selected_label]

    col_view, col_rerun, _ = st.columns([2, 2, 3])

    with col_view:
        if st.button("📂 Load Stored Results (No API Call)", type="secondary", use_container_width=True):
            st.session_state["history_selected_search_id"] = selected_search["search_id"]

    with col_rerun:
        if st.button("🔄 Rerun Search (Fresh API Call)", type="primary", use_container_width=True):
            with st.spinner("Fetching fresh vacancies and recalculating ranking..."):
                jobs_data, err, total_retrieved = get_cached_api_jobs(max_pages=1)
                ranked = rank_jobs(
                    jobs=jobs_data,
                    skill_query=selected_search["skill_query"] or "",
                    preferred_location=selected_search["location"] or "",
                    remote_only=bool(selected_search["remote_only"]),
                )
                new_search_id = save_search_transaction(
                    user_id=current_user["user_id"],
                    skill_query=selected_search["skill_query"] or "",
                    location=selected_search["location"] or "",
                    remote_only=bool(selected_search["remote_only"]),
                    ranked_jobs=ranked,
                )
                st.session_state["active_results"] = ranked
                st.session_state["history_selected_search_id"] = new_search_id
                st.success(f"Rerun complete! Created new Search #{new_search_id} with {len(ranked)} ranked listings.")
                st.rerun()

    # If a search is selected to view
    active_search_id = st.session_state.get("history_selected_search_id", selected_search["search_id"])
    if active_search_id:
        st.markdown(f"### Saved Ranked Results for Search #{active_search_id}")
        stored_results = get_search_results_by_id(active_search_id, current_user["user_id"])

        if not stored_results:
            st.warning(f"No stored ranked jobs found for Search #{active_search_id}.")
            return

        saved_job_ids = set()
        try:
            saved_job_ids = get_saved_job_ids(current_user["user_id"])
        except Exception:
            pass

        st.caption(f"Loaded {len(stored_results)} jobs directly from MySQL database without calling external API.")

        for idx, job_item in enumerate(stored_results, start=1):
            render_job_card(
                item={
                    "job": job_item,
                    "relevance_score": job_item["relevance_score"],
                    "rank_position": job_item["rank_position"],
                    "matched_skills": [],
                    "missing_skills": [],
                    "score_explanation": f"Saved rank #{job_item['rank_position']} with score {job_item['relevance_score']}%.",
                    "posted_date": job_item["posted_date"],
                },
                rank_pos=job_item["rank_position"],
                current_user=current_user,
                is_saved=(job_item["job_id"] in saved_job_ids),
            )
