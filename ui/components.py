"""UI Design System, custom CSS injection, and reusable HTML components."""

from __future__ import annotations

import html
from typing import Any
import streamlit as st


def inject_custom_css() -> None:
    """Inject polished, modern custom styles inspired by modern indigo/navy design aesthetics."""
    st.markdown(
        """
        <style>
        /* Base typography & page backgrounds */
        .stApp {
            background-color: #f8fafc;
            color: #0f172a;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
        }

        /* Hero Banner */
        .hero-banner {
            background: linear-gradient(135deg, #1e1b4b 0%, #312e81 40%, #4338ca 75%, #4f46e5 100%);
            color: #ffffff;
            padding: 2.25rem 2.5rem;
            border-radius: 16px;
            margin-bottom: 2rem;
            box-shadow: 0 10px 25px -5px rgba(67, 56, 202, 0.25), 0 8px 10px -6px rgba(67, 56, 202, 0.1);
        }
        .hero-banner h1 {
            color: #ffffff !important;
            font-size: 2.3rem !important;
            font-weight: 800 !important;
            margin: 0 !important;
            letter-spacing: -0.025em;
        }
        .hero-banner p {
            color: #e0e7ff !important;
            font-size: 1.05rem !important;
            margin: 0.6rem 0 0 0 !important;
            max-width: 680px;
            line-height: 1.5;
        }

        /* Metric cards */
        .metric-card {
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 14px;
            padding: 1.25rem;
            box-shadow: 0 1px 3px rgba(15, 23, 42, 0.05);
            text-align: center;
        }
        .metric-label {
            font-size: 0.82rem;
            color: #64748b;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        .metric-value {
            font-size: 1.85rem;
            font-weight: 800;
            color: #1e1b4b;
            margin-top: 0.35rem;
        }

        /* Job Cards */
        .job-card {
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 14px;
            padding: 1.5rem;
            margin-bottom: 1.25rem;
            box-shadow: 0 2px 4px rgba(15, 23, 42, 0.04);
            transition: transform 0.15s ease, box-shadow 0.15s ease;
        }
        .job-card:hover {
            box-shadow: 0 10px 15px -3px rgba(15, 23, 42, 0.08);
            border-color: #cbd5e1;
        }

        /* Badges */
        .badge-match {
            background: #ecfdf5;
            color: #047857;
            font-weight: 700;
            font-size: 0.85rem;
            padding: 0.25rem 0.65rem;
            border-radius: 9999px;
            display: inline-flex;
            align-items: center;
            border: 1px solid #a7f3d0;
        }
        .badge-rank {
            background: #f1f5f9;
            color: #475569;
            font-weight: 700;
            font-size: 0.8rem;
            padding: 0.2rem 0.55rem;
            border-radius: 6px;
        }
        .badge-remote {
            background: #ede9fe;
            color: #5b21b6;
            font-weight: 600;
            font-size: 0.78rem;
            padding: 0.2rem 0.55rem;
            border-radius: 6px;
        }
        .badge-skill {
            background: #f8fafc;
            color: #334155;
            border: 1px solid #e2e8f0;
            font-size: 0.75rem;
            padding: 0.2rem 0.5rem;
            border-radius: 6px;
            margin-right: 0.35rem;
            margin-bottom: 0.35rem;
            display: inline-block;
        }
        .badge-skill-match {
            background: #eef2ff;
            color: #4338ca;
            border: 1px solid #c7d2fe;
            font-weight: 600;
            font-size: 0.75rem;
            padding: 0.2rem 0.5rem;
            border-radius: 6px;
            margin-right: 0.35rem;
            margin-bottom: 0.35rem;
            display: inline-block;
        }

        /* Chip buttons */
        .chip-container {
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
            margin-bottom: 1rem;
        }

        /* Explanation box */
        .explanation-box {
            background: #f8fafc;
            border-left: 3px solid #6366f1;
            padding: 0.75rem 1rem;
            font-size: 0.85rem;
            color: #334155;
            border-radius: 0 8px 8px 0;
            margin: 0.75rem 0;
        }

        /* Sidebar profile indicator */
        .profile-pill {
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 10px;
            padding: 0.75rem 1rem;
            margin-bottom: 1.25rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_hero_banner(title: str = "Find Your Next Opportunity", subtitle: str = "") -> None:
    """Render the hero banner with indigo/navy gradient."""
    if not subtitle:
        subtitle = (
            "Explore genuine job postings from Arbeitnow, scored with deterministic "
            "skill and location matching and persisted in local MySQL."
        )
    banner_html = (
        f'<div class="hero-banner">'
        f'<h1>✦ {html.escape(title)}</h1>'
        f'<p>{html.escape(subtitle)}</p>'
        f'</div>'
    )
    st.markdown(banner_html, unsafe_allow_html=True)


def render_metric_card(col: Any, label: str, value: Any, subtext: str = "") -> None:
    """Render a clean metric box inside a Streamlit column."""
    with col:
        subtext_html = f'<div style="font-size: 0.75rem; color: #94a3b8; margin-top: 0.25rem;">{html.escape(subtext)}</div>' if subtext else ''
        card_html = (
            f'<div class="metric-card">'
            f'<div class="metric-label">{html.escape(label)}</div>'
            f'<div class="metric-value">{html.escape(str(value))}</div>'
            f'{subtext_html}'
            f'</div>'
        )
        st.markdown(card_html, unsafe_allow_html=True)
