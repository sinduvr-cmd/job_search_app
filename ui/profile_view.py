"""Candidate Profile selector and creation view for student project demonstration."""

from __future__ import annotations

import re
from typing import Any
import streamlit as st

from database.repository import list_all_users, get_or_create_user


def render_profile_view() -> None:
    """Render profile management allowing candidate switching and new profile registration."""
    st.subheader("Candidate Profile Management")
    st.caption("Student-demo profile selector: associates search history and bookmarks with your profile.")

    current_user = st.session_state.get("current_user")

    # Current profile card
    if current_user:
        profile_card_html = (
            f'<div class="metric-card" style="text-align: left; margin-bottom: 1.5rem;">'
            f'<div class="metric-label">Active Candidate Profile</div>'
            f'<div style="font-size: 1.35rem; font-weight: 700; color: #1e1b4b; margin: 0.25rem 0;">'
            f'{current_user["name"]}'
            f'</div>'
            f'<div style="color: #64748b; font-size: 0.95rem;">'
            f'📧 {current_user["email"]} &nbsp;·&nbsp; ID: #{current_user["user_id"]}'
            f'</div>'
            f'</div>'
        )
        st.markdown(profile_card_html, unsafe_allow_html=True)

    col_switch, col_create = st.columns(2)

    with col_switch:
        st.markdown("#### Switch to Existing Profile")
        existing_users = list_all_users()
        if existing_users:
            user_map = {f"{u['name']} ({u['email']})": u for u in existing_users}
            selected_label = st.selectbox("Select Profile:", options=list(user_map.keys()), key="profile_select_box")
            if st.button("Set Active Profile", type="primary", use_container_width=True):
                chosen = user_map[selected_label]
                st.session_state["current_user"] = chosen
                st.success(f"Switched active candidate to {chosen['name']}!")
                st.rerun()
        else:
            st.info("No profiles registered in database yet. Create your first profile on the right.")

    with col_create:
        st.markdown("#### Create New Candidate Profile")
        with st.form("new_profile_form"):
            new_name = st.text_input("Full Name", placeholder="e.g. Sindhu Suraj")
            new_email = st.text_input("Email Address", placeholder="e.g. sindhu@example.com")
            submitted = st.form_submit_button("Register Candidate", use_container_width=True)

        if submitted:
            if not new_name.strip():
                st.error("Please enter a candidate name.")
            elif not new_email.strip() or "@" not in new_email or "." not in new_email:
                st.error("Please enter a valid email address.")
            else:
                try:
                    user_record = get_or_create_user(name=new_name, email=new_email)
                    st.session_state["current_user"] = user_record
                    st.success(f"Profile created successfully for {user_record['name']}!")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Could not save profile to MySQL: {exc}")
