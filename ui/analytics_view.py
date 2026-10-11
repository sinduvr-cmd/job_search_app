"""Analytics view displaying database metrics and Plotly charts computed from live MySQL data."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from database.repository import get_analytics_metrics
from ui.components import render_metric_card


def render_analytics_view() -> None:
    """Render database analytics and Plotly visualizations computed from genuine MySQL records."""
    st.subheader("Database Insights & Analytics")
    st.caption("Live aggregate metrics computed directly from your local MySQL database tables.")

    try:
        metrics = get_analytics_metrics()
    except Exception:
        st.warning("⚠️ Database is currently disconnected. Connect MySQL to view live database analytics.")
        return

    # Top-level Metric KPI Cards
    col1, col2, col3, col4 = st.columns(4)
    render_metric_card(col1, "Total Searches", metrics["total_searches"], "Recorded search transactions")
    render_metric_card(col2, "Unique Jobs", metrics["total_jobs"], "Normalized jobs in repository")
    render_metric_card(col3, "Saved Bookmarks", metrics["total_saved"], "Across all candidate profiles")
    render_metric_card(
        col4,
        "Remote Job Share",
        f"{metrics['remote_pct']}%",
        f"{metrics['remote_jobs']} of {metrics['total_jobs']} stored jobs"
    )

    st.markdown("<div style='height: 25px;'></div>", unsafe_allow_html=True)

    if metrics["total_jobs"] == 0:
        st.info("The local database currently has 0 imported jobs. Perform searches in the 'Search Jobs' tab to populate analytics.")
        return

    # Plotly Charts Section
    c_left, c_right = st.columns(2)

    with c_left:
        st.markdown("#### Most In-Demand Skills")
        st.caption(f"Top tags and detected skills across {metrics['total_jobs']} stored jobs in `skills` & `job_skills` tables.")
        top_skills = metrics.get("top_skills", [])
        if top_skills:
            df_skills = pd.DataFrame(top_skills)
            fig_skills = px.bar(
                df_skills,
                x="frequency",
                y="skill_name",
                orientation="h",
                labels={"frequency": "Job Postings Count", "skill_name": "Skill"},
                color="frequency",
                color_continuous_scale=["#a5b4fc", "#4f46e5"],
            )
            fig_skills.update_layout(
                yaxis={"categoryorder": "total ascending"},
                margin=dict(l=20, r=20, t=20, b=20),
                height=420,
                coloraxis_showscale=False,
                plot_bgcolor="#ffffff",
                paper_bgcolor="#ffffff",
            )
            st.plotly_chart(fig_skills, use_container_width=True)
        else:
            st.caption("No skill associations extracted yet.")

    with c_right:
        st.markdown("#### Top Hiring Companies")
        st.caption(f"Organizations with the highest volume of postings in local `jobs` table.")
        top_companies = metrics.get("top_companies", [])
        if top_companies:
            df_companies = pd.DataFrame(top_companies)
            fig_companies = px.bar(
                df_companies,
                x="job_count",
                y="company",
                orientation="h",
                labels={"job_count": "Active Listings", "company": "Company"},
                color="job_count",
                color_continuous_scale=["#c7d2fe", "#312e81"],
            )
            fig_companies.update_layout(
                yaxis={"categoryorder": "total ascending"},
                margin=dict(l=20, r=20, t=20, b=20),
                height=420,
                coloraxis_showscale=False,
                plot_bgcolor="#ffffff",
                paper_bgcolor="#ffffff",
            )
            st.plotly_chart(fig_companies, use_container_width=True)
        else:
            st.caption("No company data available yet.")

    st.divider()
    st.markdown(
        """
        <div style="font-size: 0.85rem; color: #64748b; line-height: 1.5;">
            <strong>Denominator & Methodology Transparency:</strong><br>
            • <em>Total Unique Jobs</em> represents distinct listings saved via <code>external_job_id</code> in the <code>jobs</code> table.<br>
            • <em>Remote Share</em> is computed as <code>COUNT(remote = 1) / COUNT(*) * 100</code> across all rows in <code>jobs</code>.<br>
            • <em>Skill Frequency</em> aggregates relational records from <code>job_skills</code> joined with <code>skills</code>.
        </div>
        """,
        unsafe_allow_html=True,
    )
