"""Job Search & Recommendation app backed by the Arbeitnow Job Board API."""

from __future__ import annotations

import html
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

import pandas as pd
import requests
import streamlit as st
from sqlalchemy import create_engine, text

APP_DIR = Path(__file__).parent
DB_PATH = APP_DIR / "job_search.db"
API_URL = "https://www.arbeitnow.com/api/job-board-api"
DB_MODE = os.getenv("JOB_SEARCH_DB_MODE", "mysql").lower()

MYSQL_USER = os.getenv("JOB_SEARCH_DB_USER", "root")
MYSQL_PASSWORD = os.getenv("JOB_SEARCH_DB_PASSWORD", "")
MYSQL_HOST = os.getenv("JOB_SEARCH_DB_HOST", "localhost")
MYSQL_PORT = os.getenv("JOB_SEARCH_DB_PORT", "3306")
MYSQL_NAME = os.getenv("JOB_SEARCH_DB_NAME", "job_search_app")


def build_mysql_url(database: str | None = None) -> str:
    password = quote_plus(MYSQL_PASSWORD)
    db_name = database if database is not None else MYSQL_NAME
    return f"mysql+pymysql://{MYSQL_USER}:{password}@{MYSQL_HOST}:{MYSQL_PORT}/{db_name}"


DB_URL = os.getenv("JOB_SEARCH_DB_URL")
if not DB_URL:
    if DB_MODE == "mysql":
        DB_URL = build_mysql_url()
    else:
        DB_URL = f"sqlite:///{DB_PATH}"

ENGINE = create_engine(DB_URL, pool_pre_ping=True)


def ensure_mysql_database() -> bool:
    if not DB_URL.startswith("mysql"):
        return True
    try:
        admin_engine = create_engine(build_mysql_url(""), pool_pre_ping=True)
        with admin_engine.begin() as conn:
            conn.execute(text(f"CREATE DATABASE IF NOT EXISTS `{MYSQL_NAME}`"))
        return True
    except Exception:
        return False


def mysql_available() -> bool:
    if not DB_URL.startswith("mysql"):
        return False
    try:
        with ENGINE.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def use_mysql() -> bool:
    return DB_URL.startswith("mysql") and ensure_mysql_database() and mysql_available()


def clean_text(value: Any) -> str:
    """Turn the API's HTML fields into short readable plain text."""
    value = re.sub(r"<[^>]+>", " ", str(value or ""))
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def init_db() -> None:
    """Create the tables from the supplied MySQL ERD, or use SQLite for local fallback."""
    if use_mysql():
        with ENGINE.begin() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    email VARCHAR(150) UNIQUE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS searches (
                    search_id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    skill_query VARCHAR(500),
                    location VARCHAR(150),
                    remote_only BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id INT AUTO_INCREMENT PRIMARY KEY,
                    external_job_id VARCHAR(150) UNIQUE,
                    title VARCHAR(255) NOT NULL,
                    company VARCHAR(255),
                    location VARCHAR(255),
                    remote BOOLEAN DEFAULT FALSE,
                    category VARCHAR(100),
                    salary VARCHAR(255),
                    url TEXT,
                    description TEXT,
                    posted_date DATE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS skills (
                    skill_id INT AUTO_INCREMENT PRIMARY KEY,
                    skill_name VARCHAR(100) UNIQUE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS job_skills (
                    job_skill_id INT AUTO_INCREMENT PRIMARY KEY,
                    job_id INT NOT NULL,
                    skill_id INT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (job_id, skill_id),
                    FOREIGN KEY (job_id) REFERENCES jobs(job_id) ON DELETE CASCADE,
                    FOREIGN KEY (skill_id) REFERENCES skills(skill_id) ON DELETE CASCADE
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS search_results (
                    search_result_id INT AUTO_INCREMENT PRIMARY KEY,
                    search_id INT NOT NULL,
                    job_id INT NOT NULL,
                    relevance_score DECIMAL(6,2),
                    rank_position INT,
                    FOREIGN KEY (search_id) REFERENCES searches(search_id) ON DELETE CASCADE,
                    FOREIGN KEY (job_id) REFERENCES jobs(job_id) ON DELETE CASCADE
                )
            """))
        return

    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(
            """
            PRAGMA foreign_keys = ON;
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS searches (
                search_id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                skill_query TEXT,
                location TEXT,
                remote_only BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );
            CREATE TABLE IF NOT EXISTS jobs (
                job_id INTEGER PRIMARY KEY,
                external_job_id TEXT UNIQUE,
                title TEXT,
                company TEXT,
                location TEXT,
                remote BOOLEAN DEFAULT FALSE,
                category TEXT,
                salary TEXT,
                url TEXT,
                description TEXT,
                posted_date DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS skills (
                skill_id INTEGER PRIMARY KEY,
                skill_name TEXT NOT NULL UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS job_skills (
                job_skill_id INTEGER PRIMARY KEY,
                job_id INTEGER NOT NULL,
                skill_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(job_id, skill_id),
                FOREIGN KEY (job_id) REFERENCES jobs(job_id),
                FOREIGN KEY (skill_id) REFERENCES skills(skill_id)
            );
            CREATE TABLE IF NOT EXISTS search_results (
                search_result_id INTEGER PRIMARY KEY,
                search_id INTEGER NOT NULL,
                job_id INTEGER NOT NULL,
                relevance_score DECIMAL(6,2),
                rank_position INTEGER,
                FOREIGN KEY (search_id) REFERENCES searches(search_id),
                FOREIGN KEY (job_id) REFERENCES jobs(job_id)
            );
            """
        )


def user_id_for(name: str, email: str) -> int:
    if use_mysql():
        with ENGINE.begin() as conn:
            existing = conn.execute(text("SELECT user_id FROM users WHERE email = :email"), {"email": email}).fetchone()
            if existing is None:
                conn.execute(text("INSERT INTO users (name, email) VALUES (:name, :email)"), {"name": name, "email": email})
                user_id = conn.execute(text("SELECT LAST_INSERT_ID() AS user_id")).scalar_one()
            else:
                user_id = existing[0]
                conn.execute(text("UPDATE users SET name = :name WHERE email = :email"), {"name": name, "email": email})
            return int(user_id)

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO users (name, email) VALUES (?, ?)", (name, email))
        conn.execute("UPDATE users SET name = ? WHERE email = ?", (name, email))
        return int(conn.execute("SELECT user_id FROM users WHERE email = ?", (email,)).fetchone()[0])


@st.cache_data(ttl=900, show_spinner=False)
def fetch_jobs() -> tuple[list[dict[str, Any]], str | None]:
    """Fetch one page from Arbeitnow. Cache the response for 15 minutes."""
    try:
        response = requests.get(API_URL, timeout=20, headers={"Accept": "application/json"})
        response.raise_for_status()
        payload = response.json()
        return payload.get("data", []), None
    except requests.RequestException as exc:
        return [], f"Could not reach Arbeitnow: {exc}"
    except ValueError:
        return [], "Arbeitnow returned an unexpected response."


def terms(value: str) -> list[str]:
    return [word.lower() for word in re.split(r"[,\s]+", value.strip()) if word]


def matches_and_score(job: dict[str, Any], keywords: list[str], location: str, remote_only: bool) -> tuple[bool, float]:
    title = clean_text(job.get("title"))
    company = clean_text(job.get("company_name"))
    description = clean_text(job.get("description"))
    job_location = clean_text(job.get("location"))
    tags = " ".join(map(str, job.get("tags", [])))
    haystack = f"{title} {company} {description} {tags}".lower()
    is_remote = bool(job.get("remote"))
    if remote_only and not is_remote:
        return False, 0
    if location and location.lower() not in job_location.lower() and not is_remote:
        return False, 0
    hits = sum(term in haystack for term in keywords)
    if keywords and not hits:
        return False, 0
    title_hits = sum(term in title.lower() for term in keywords)
    tag_hits = sum(term in tags.lower() for term in keywords)
    score = 35 + (hits / max(len(keywords), 1)) * 45 + title_hits * 8 + tag_hits * 4
    if is_remote:
        score += 3
    return True, min(round(score, 1), 100)


def save_search(user_id: int, query: str, location: str, remote_only: bool, results: list[tuple[dict[str, Any], float]]) -> None:
    """Save a search, its jobs, skills, and ranking to the configured database."""
    if use_mysql():
        with ENGINE.begin() as conn:
            result = conn.execute(
                text("INSERT INTO searches (user_id, skill_query, location, remote_only) VALUES (:user_id, :query, :location, :remote_only)"),
                {"user_id": user_id, "query": query, "location": location, "remote_only": remote_only},
            )
            search_id = result.lastrowid
            for rank, (job, score) in enumerate(results, start=1):
                external_id = str(job.get("slug") or job.get("url") or f"{job.get('title')}-{job.get('company_name')}")
                conn.execute(
                    text("""
                        INSERT INTO jobs (external_job_id, title, company, location, remote, category, salary, url, description, posted_date)
                        VALUES (:external_job_id, :title, :company, :location, :remote, :category, :salary, :url, :description, :posted_date)
                        ON DUPLICATE KEY UPDATE
                            title = VALUES(title),
                            company = VALUES(company),
                            location = VALUES(location),
                            remote = VALUES(remote),
                            category = VALUES(category),
                            salary = VALUES(salary),
                            url = VALUES(url),
                            description = VALUES(description),
                            posted_date = VALUES(posted_date)
                    """),
                    {
                        "external_job_id": external_id,
                        "title": clean_text(job.get("title")),
                        "company": clean_text(job.get("company_name")),
                        "location": clean_text(job.get("location")),
                        "remote": bool(job.get("remote")),
                        "category": ", ".join(job.get("tags", [])[:3]),
                        "salary": "",
                        "url": job.get("url"),
                        "description": clean_text(job.get("description")),
                        "posted_date": job.get("created_at"),
                    },
                )
                job_record = conn.execute(text("SELECT job_id FROM jobs WHERE external_job_id = :external_job_id"), {"external_job_id": external_id}).fetchone()
                if not job_record:
                    raise RuntimeError(f"Job save failed for {external_id}")
                job_id = job_record[0]
                for skill in job.get("tags", []):
                    skill_name = clean_text(skill).lower()
                    if not skill_name:
                        continue
                    conn.execute(text("INSERT IGNORE INTO skills (skill_name) VALUES (:skill_name)"), {"skill_name": skill_name})
                    skill_record = conn.execute(text("SELECT skill_id FROM skills WHERE skill_name = :skill_name"), {"skill_name": skill_name}).fetchone()
                    if not skill_record:
                        continue
                    skill_id = skill_record[0]
                    conn.execute(text("INSERT IGNORE INTO job_skills (job_id, skill_id) VALUES (:job_id, :skill_id)"), {"job_id": job_id, "skill_id": skill_id})
                conn.execute(
                    text("INSERT INTO search_results (search_id, job_id, relevance_score, rank_position) VALUES (:search_id, :job_id, :relevance_score, :rank_position)"),
                    {"search_id": search_id, "job_id": job_id, "relevance_score": score, "rank_position": rank},
                )
        return

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.execute(
            "INSERT INTO searches (user_id, skill_query, location, remote_only) VALUES (?, ?, ?, ?)",
            (user_id, query, location, remote_only),
        )
        search_id = cursor.lastrowid
        for rank, (job, score) in enumerate(results, start=1):
            external_id = str(job.get("slug") or job.get("url") or f"{job.get('title')}-{job.get('company_name')}")
            conn.execute(
                """INSERT INTO jobs (external_job_id, title, company, location, remote, category, salary, url, description, posted_date)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(external_job_id) DO UPDATE SET title=excluded.title, company=excluded.company,
                   location=excluded.location, remote=excluded.remote, category=excluded.category, salary=excluded.salary,
                   url=excluded.url, description=excluded.description, posted_date=excluded.posted_date""",
                (external_id, clean_text(job.get("title")), clean_text(job.get("company_name")), clean_text(job.get("location")),
                 bool(job.get("remote")), ", ".join(job.get("tags", [])[:3]), "", job.get("url"), clean_text(job.get("description")), job.get("created_at")),
            )
            job_id_row = conn.execute("SELECT job_id FROM jobs WHERE external_job_id = ?", (external_id,)).fetchone()
            if job_id_row is None:
                raise RuntimeError(f"SQLite job save failed for {external_id}")
            job_id = job_id_row[0]
            for skill in job.get("tags", []):
                skill = clean_text(skill).lower()
                if not skill:
                    continue
                conn.execute("INSERT OR IGNORE INTO skills (skill_name) VALUES (?)", (skill,))
                skill_row = conn.execute("SELECT skill_id FROM skills WHERE skill_name = ?", (skill,)).fetchone()
                if skill_row is None:
                    continue
                skill_id = skill_row[0]
                conn.execute("INSERT OR IGNORE INTO job_skills (job_id, skill_id) VALUES (?, ?)", (job_id, skill_id))
            conn.execute(
                "INSERT INTO search_results (search_id, job_id, relevance_score, rank_position) VALUES (?, ?, ?, ?)",
                (search_id, job_id, score, rank),
            )
            conn.commit()
        conn.commit()


def recent_searches(email: str) -> pd.DataFrame:
    if use_mysql():
        with ENGINE.begin() as conn:
            rows = conn.execute(
                text("""
                    SELECT s.skill_query AS Search,
                           s.location AS Location,
                           s.remote_only AS Remote,
                           s.created_at AS `Searched at`
                    FROM searches s
                    JOIN users u ON u.user_id = s.user_id
                    WHERE u.email = :email
                    ORDER BY s.search_id DESC
                    LIMIT 8
                """),
                {"email": email},
            ).fetchall()
            return pd.DataFrame(rows, columns=["Search", "Location", "Remote", "Searched at"])

    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql_query(
            """SELECT s.skill_query AS Search,
                      s.location AS Location,
                      s.remote_only AS Remote,
                      s.created_at AS 'Searched at'
               FROM searches s
               JOIN users u ON u.user_id = s.user_id
               WHERE u.email = ?
               ORDER BY s.search_id DESC
               LIMIT 8""",
            conn,
            params=(email,),
        )


def render_card(job: dict[str, Any], score: float, rank: int) -> None:
    title, company = clean_text(job.get("title")), clean_text(job.get("company_name"))
    location = clean_text(job.get("location")) or "Location not specified"
    tags = [clean_text(tag) for tag in job.get("tags", [])[:5]]
    badges = "".join(f'<span class="tag">{html.escape(tag)}</span>' for tag in tags)
    remote = "Remote" if job.get("remote") else location
    posted = clean_text(job.get("created_at"))[:10] or "Recent"
    safe_url = job.get("url") or "#"
    st.markdown(
        f'''<div class="job-card">
          <div class="score">{score:.0f}% match</div><div class="rank">#{rank}</div>
          <h3>{html.escape(title)}</h3><p class="company">{html.escape(company)}</p>
          <p class="meta">⌖ {html.escape(remote)} &nbsp; · &nbsp; ◷ {html.escape(posted)}</p>
          <div class="tags">{badges}</div>
          <p class="summary">{html.escape(clean_text(job.get("description"))[:260])}…</p>
          <a class="apply" href="{html.escape(safe_url, quote=True)}" target="_blank">View & apply ↗</a>
        </div>''',
        unsafe_allow_html=True,
    )


st.set_page_config(page_title="Job Compass", page_icon="✦", layout="wide")
init_db()

st.markdown("""<style>
    .stApp { background: #f7f8fc; color: #172033; }
    .hero { background: linear-gradient(120deg,#102a43,#246b8e 58%,#3da9a0); color:#fff; padding:2.5rem 3rem; border-radius:24px; margin:0 0 1.5rem; }
    .hero h1 { margin:0; font-size:2.7rem; } .hero p { margin:.45rem 0 0; color:#dcebf3; font-size:1.1rem; }
    .job-card { background:#fff; border:1px solid #e4e8ef; border-radius:18px; padding:1.35rem; margin:.9rem 0; box-shadow:0 4px 14px rgba(24,39,75,.06); position:relative; }
    .job-card h3 { margin:.15rem 0; color:#102a43; font-size:1.2rem; padding-right:85px; } .company { margin:.25rem 0 .55rem; font-weight:650; }
    .meta,.summary { color:#5c6878; font-size:.9rem; } .summary { line-height:1.45; }
    .score { color:#087f5b; font-weight:800; font-size:.83rem; } .rank { position:absolute; top:1.25rem; right:1.25rem; color:#8a97a8; font-weight:700; }
    .tag { display:inline-block; background:#e7f5f3; color:#087f5b; border-radius:99px; padding:.22rem .58rem; margin:0 .32rem .55rem 0; font-size:.77rem; }
    .apply { display:inline-block; background:#102a43; color:#fff !important; text-decoration:none; border-radius:9px; padding:.55rem .85rem; font-weight:650; margin-top:.25rem; }
    div[data-testid="stMetric"] { background:#fff; padding:1rem; border-radius:14px; border:1px solid #e4e8ef; }
</style>""", unsafe_allow_html=True)

st.markdown("""<div class="hero"><h1>Job Compass ✦</h1><p>Discover relevant roles from Arbeitnow, ranked around what you do best.</p></div>""", unsafe_allow_html=True)

with st.sidebar:
    st.header("Your profile")
    profile_name = st.text_input("Name", value="Guest")
    profile_email = st.text_input("Email", value="guest@example.com")
    st.caption("Your saved searches stay only in this local project database.")
    st.divider()
    st.caption("Source: Arbeitnow Job Board API · refreshed every 15 minutes")

filters, history = st.tabs(["Search jobs", "Search history"])
with filters:
    st.subheader("Find your next role")
    a, b, c = st.columns([2.5, 1.6, 1])
    with a:
        query = st.text_input("Skills, role, or keywords", placeholder="e.g. Python, data analyst")
    with b:
        location_filter = st.text_input("Location", placeholder="e.g. Berlin")
    with c:
        remote_only = st.toggle("Remote only", value=False)
    search = st.button("Search roles", type="primary", use_container_width=True)

    if search:
        if not profile_name.strip() or not profile_email.strip() or "@" not in profile_email:
            st.error("Enter a name and a valid email in the sidebar to save your recommendations.")
        else:
            with st.spinner("Checking the latest roles on Arbeitnow…"):
                jobs, error = fetch_jobs()
            if error:
                st.error(error)
            else:
                key_terms = terms(query)
                matches = [(job, score) for job in jobs if (result := matches_and_score(job, key_terms, location_filter, remote_only))[0] for score in [result[1]]]
                matches.sort(key=lambda item: item[1], reverse=True)
                matches = matches[:30]
                save_search(user_id_for(profile_name.strip(), profile_email.strip().lower()), query, location_filter, remote_only, matches)
                st.session_state["results"] = matches
                st.session_state["query_label"] = query or "all roles"

    results = st.session_state.get("results")
    if results is not None:
        total, top, remote_count = st.columns(3)
        total.metric("Matches", len(results))
        top.metric("Best fit", f"{results[0][1]:.0f}%" if results else "—")
        remote_count.metric("Remote roles", sum(bool(job.get("remote")) for job, _ in results))
        st.markdown(f"#### Ranked results for “{st.session_state.get('query_label', '')}”")
        if results:
            for rank, (job, score) in enumerate(results, start=1):
                render_card(job, score, rank)
        else:
            st.info("No roles matched these filters. Try fewer keywords, another location, or turn off Remote only.")
    else:
        st.info("Start with a skill, role, or keyword. We’ll score and save the most relevant current listings.")

with history:
    st.subheader("Your recent searches")
    if profile_email and "@" in profile_email:
        dataframe = recent_searches(profile_email.strip().lower())
        if dataframe.empty:
            st.info("Your saved searches will appear here after your first search.")
        else:
            dataframe["Remote"] = dataframe["Remote"].map({1: "Yes", 0: "No", True: "Yes", False: "No"})
            st.dataframe(dataframe, use_container_width=True, hide_index=True)
    else:
        st.info("Add a valid email in the sidebar to view saved history.")
