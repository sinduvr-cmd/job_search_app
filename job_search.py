"""Main Streamlit application entry point for the Job Search & Recommendation App."""

from __future__ import annotations

import os
import streamlit as st

from database.connection import test_db_connection, init_db_schema, get_db_config
from database.repository import get_or_create_user, list_all_users
from ui.components import inject_custom_css, render_hero_banner
from ui.search_view import render_search_view
from ui.history_view import render_history_view
from ui.saved_jobs_view import render_saved_jobs_view
from ui.analytics_view import render_analytics_view
from ui.profile_view import render_profile_view
from ui.about_view import render_about_view

st.set_page_config(
    page_title="Job Search & Recommendation",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Inject custom modern styling
inject_custom_css()

# Test and initialize database connection
is_db_connected, db_status_msg = test_db_connection()
if is_db_connected:
    init_db_schema()

# Initialize default demo profile in session state if not present
if "current_user" not in st.session_state:
    if is_db_connected:
        try:
            existing = list_all_users()
            if existing:
                st.session_state["current_user"] = existing[0]
            else:
                demo_user = get_or_create_user(name="Sindhu Suraj", email="sindhu@example.com")
                st.session_state["current_user"] = demo_user
        except Exception:
            st.session_state["current_user"] = {"user_id": 1, "name": "Sindhu Suraj", "email": "sindhu@example.com"}
    else:
        st.session_state["current_user"] = {"user_id": 1, "name": "Guest Candidate", "email": "candidate@example.com"}

current_user = st.session_state["current_user"]

# Sidebar Navigation & Profile Context
with st.sidebar:
    st.markdown("### ✦ Career Compass")
    
    # Active Profile Pill
    st.markdown(
        f"""
        <div class="profile-pill">
            <div style="font-size: 0.75rem; text-transform: uppercase; color: #64748b; font-weight: 700;">Active Profile</div>
            <div style="font-weight: 700; color: #1e1b4b; font-size: 1.05rem; margin-top: 2px;">{current_user['name']}</div>
            <div style="color: #64748b; font-size: 0.8rem;">{current_user['email']}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    nav_choice = st.radio(
        "Navigation",
        options=[
            "Search Jobs",
            "My Searches",
            "Saved Jobs",
            "Analytics",
            "Profile",
            "About",
        ],
        index=0,
        label_visibility="collapsed",
    )

    st.divider()

    # Database Connection Status
    st.markdown("#### Database Status")
    db_cfg = get_db_config()
    if is_db_connected:
        st.success(f"● Connected to MySQL\n\n`{db_cfg['host']}:{db_cfg['port']}`\n\nDB: `{db_cfg['database']}`")
    else:
        st.error(f"● Disconnected\n\n{db_status_msg}")
        with st.expander("Troubleshoot Connection"):
            st.markdown(
                """
                1. Ensure MySQL Server is running locally.
                2. Check your `.env` file credentials.
                3. Open **MySQL Workbench** and execute `sql/schema.sql`.
                """
            )

    st.divider()
    st.caption("Powered by Arbeitnow REST API & Local MySQL Server.")

# Top Hero Banner
render_hero_banner(
    title="Find Your Next Opportunity",
    subtitle="Discover genuine developer and technology roles, ranked with deterministic 80/20 skill and location matching.",
)

# Route to selected navigation view
if nav_choice == "Search Jobs":
    render_search_view(current_user=current_user)
elif nav_choice == "My Searches":
    render_history_view(current_user=current_user)
elif nav_choice == "Saved Jobs":
    render_saved_jobs_view(current_user=current_user)
elif nav_choice == "Analytics":
    render_analytics_view()
elif nav_choice == "Profile":
    render_profile_view()
elif nav_choice == "About":
    render_about_view()
