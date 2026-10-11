"""About & Architecture view providing technical documentation and methodology explanations."""

from __future__ import annotations

import streamlit as st
from services.jobs_api import GEOGRAPHIC_COVERAGE, PROVIDER_NAME


def render_about_view() -> None:
    """Render technical documentation, ERD breakdown, and ranking algorithm explanation."""
    st.subheader("About Job Search & Recommendation App")

    st.markdown(
        """
        This application is an end-to-end full-stack data system built for academic demonstration.
        It integrates a public REST API with a local relational MySQL database and an interactive Streamlit UI,
        performing deterministic skill extraction and multi-attribute ranking.
        """
    )

    t1, t2, t3, t4 = st.tabs(["🏗 System Architecture", "📊 Ranking Methodology", "🗄 Database Schema", "🌐 API Coverage & Limits"])

    with t1:
        st.markdown(
            """
            ### Technology Stack & Architecture
            - **Frontend & Interaction**: Streamlit with custom CSS design tokens (Navy/Indigo palette).
            - **Backend Services**: Pure Python 3 modular services (`services/jobs_api.py`, `services/ranking.py`, `services/skill_extraction.py`).
            - **REST API Client**: `requests` communicating with the official Arbeitnow Job Board API.
            - **Database Engine**: Local **MySQL Server 8.0+** using the **InnoDB** storage engine.
            - **Database Client / Driver**: `mysql-connector-python` using parameterized SQL queries (`%s`).
            - **Configuration**: `python-dotenv` reading local environment parameters from `.env`.
            - **Visualizations**: Interactive Plotly charts computed directly from relational aggregates.

            #### Modular Structure
            ```
            job_search_app/
            ├── app.py                     # Main Streamlit coordinator and state router
            ├── services/
            │   ├── jobs_api.py            # REST client with HTML cleaning and pagination
            │   ├── ranking.py             # Deterministic 80/20 scoring engine
            │   └── skill_extraction.py    # Boundary-aware regexes and alias resolver
            ├── database/
            │   ├── connection.py          # MySQL connector, health checks, error sanitization
            │   └── repository.py          # Parameterized CRUD and atomic search transactions
            ├── ui/
            │   ├── components.py          # Design system, banners, and metric cards
            │   ├── search_view.py         # Search form, filters, and paginated job cards
            │   ├── history_view.py        # MySQL search history viewer and rerun trigger
            │   ├── saved_jobs_view.py     # Persistent user bookmarks
            │   ├── analytics_view.py      # Plotly database analytics
            │   ├── profile_view.py        # Candidate profile switcher
            │   └── about_view.py          # System documentation
            ├── sql/
            │   ├── schema.sql             # Complete DDL script for MySQL Workbench
            │   └── create_app_user.sql    # Optional least-privilege user script
            └── tests/                     # Unit tests for scoring, boundaries, and mocks
            ```
            """
        )

    with t2:
        st.markdown(
            """
            ### Deterministic Scoring Formula
            The application strictly rejects fabricated AI claims and relies on an **explainable, deterministic algorithm**:

            $$\\text{Overall Score} = 0.80 \\times \\text{Skill Score} + 0.20 \\times \\text{Location Score}$$

            #### 1. Skill Score (80% Weight)
            - **Coverage**: $\\frac{|\\text{Matched Skills}|}{|\\text{Requested Skills}|} \\times 100\\%$ across job title, tags, and description.
            - **Boundary-Aware Matching**:
              - Distinguishes `Java` from `JavaScript`.
              - Isolates single-character `C` from `C++`, `C#`, and `CSS`.
              - Handles punctuation-sensitive symbols (`C++`, `C#`, `.NET`).
            - **Alias Expansion**: Automatically equates `JS` $\\rightarrow$ `JavaScript`, `ML` $\\rightarrow$ `Machine Learning`, `Postgres` $\\rightarrow$ `PostgreSQL`, etc.

            #### 2. Location Score (20% Weight)
            - **Exact / Substring Match**: $100\\%$ if the job location contains the candidate's target location.
            - **Remote Accessibility**: $75\\%$ if the job is flagged as `remote = True`.
            - **Mismatch**: $0\\%$.

            #### 3. Special Cases & Validation
            - **Location Blank**: Score is calculated as $100\\%$ Skill Coverage.
            - **Skills Blank**: Score is calculated as $100\\%$ Location Relevance.
            - **Both Blank**: System displays a validation error requiring at least one input.
            - **Remote Only**: Enforces a strict hard filter excluding non-remote roles.
            """
        )

    with t3:
        st.markdown(
            """
            ### Database Relational Schema
            The schema follows strict relational modeling with Foreign Keys (`ON DELETE CASCADE`), Indexes, and Uniqueness constraints:

            1. **`users`**: Profiles for demo candidate tracking (`user_id`, `name`, `email` UNIQUE).
            2. **`searches`**: Records every distinct search execution (`search_id`, `user_id`, `skill_query`, `location`, `remote_only`).
            3. **`jobs`**: Normalized job listings repository with `external_job_id` UNIQUE and upsert support.
            4. **`skills`**: Master table of distinct skill strings (`skill_id`, `skill_name` UNIQUE).
            5. **`job_skills`**: Many-to-many bridge linking jobs with identified skills (`UNIQUE(job_id, skill_id)`).
            6. **`search_results`**: Preserves ranked scores and positions (`UNIQUE(search_id, job_id)`).
            7. **`saved_jobs`**: Persistent user bookmarks (`UNIQUE(user_id, job_id)`).

            *All database operations execute inside atomic MySQL transactions with automatic rollback on error.*
            """
        )

    with t4:
        st.markdown(
            f"""
            ### External API Integration & Coverage
            - **API Provider**: [{PROVIDER_NAME} Job Board API](https://www.arbeitnow.com/api/job-board-api)
            - **Geographic Coverage**:
              > {GEOGRAPHIC_COVERAGE}
            - **Field Transparency**:
              - Salary is marked as *'Not provided'* because the API payload does not supply structured compensation fields.
              - No synthetic logos, experience levels, or hybrid classifications are fabricated.
            - **Caching Policy**: API reads are cached using Streamlit's `@st.cache_data(ttl=900)` (15 minutes). Database writes are **never** cached.
            """
        )
