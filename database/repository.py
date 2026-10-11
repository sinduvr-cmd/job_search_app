"""Repository layer for parameterized MySQL operations and transactional persistence."""

from __future__ import annotations

from datetime import datetime, date
from typing import Any
import mysql.connector

from .connection import get_db_connection, get_db_cursor, sanitize_db_error


def get_or_create_user(name: str, email: str) -> dict[str, Any]:
    """Retrieve an existing user profile by email or insert a new one."""
    clean_email = email.strip().lower()
    clean_name = name.strip() or "Candidate"

    with get_db_cursor(commit=True) as (conn, cursor):
        cursor.execute("SELECT user_id, name, email, created_at FROM users WHERE email = %s", (clean_email,))
        row = cursor.fetchone()
        if row:
            if row["name"] != clean_name and clean_name:
                cursor.execute("UPDATE users SET name = %s WHERE user_id = %s", (clean_name, row["user_id"]))
                row["name"] = clean_name
            return dict(row)

        cursor.execute(
            "INSERT INTO users (name, email) VALUES (%s, %s)",
            (clean_name, clean_email)
        )
        user_id = cursor.lastrowid
        return {
            "user_id": user_id,
            "name": clean_name,
            "email": clean_email,
            "created_at": datetime.now(),
        }


def list_all_users() -> list[dict[str, Any]]:
    """List all demo user profiles available in the local database."""
    try:
        with get_db_cursor(commit=False) as (conn, cursor):
            cursor.execute("SELECT user_id, name, email, created_at FROM users ORDER BY created_at DESC")
            return [dict(r) for r in cursor.fetchall()]
    except Exception:
        return []


def save_search_transaction(
    user_id: int,
    skill_query: str,
    location: str,
    remote_only: bool,
    ranked_jobs: list[dict[str, Any]],
) -> int:
    """Store every submitted search and its ranked results in a single atomic transaction.
    Upserts jobs, prevents duplicate skills/mappings, and rolls back cleanly on any failure.
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        # Defensively ensure user exists in users table to prevent Foreign Key Error (1452)
        cursor.execute("SELECT user_id FROM users WHERE user_id = %s", (user_id,))
        if not cursor.fetchone():
            cursor.execute(
                "INSERT INTO users (user_id, name, email) VALUES (%s, %s, %s) "
                "ON DUPLICATE KEY UPDATE name = VALUES(name)",
                (user_id, "Candidate Profile", f"candidate_{user_id}@example.com"),
            )

        # 1. Record search query
        cursor.execute(
            """
            INSERT INTO searches (user_id, skill_query, location, remote_only)
            VALUES (%s, %s, %s, %s)
            """,
            (user_id, skill_query.strip(), location.strip(), bool(remote_only)),
        )
        search_id = cursor.lastrowid

        # 2. Process each ranked job
        for rank_pos, item in enumerate(ranked_jobs, start=1):
            job_data = item.get("job", item)
            score = float(item.get("relevance_score", item.get("score", 0.0)))
            external_id = str(job_data.get("external_job_id") or "")
            if not external_id:
                slug = job_data.get("slug") or job_data.get("url") or f"{job_data.get('title')}-{job_data.get('company_name')}"
                external_id = f"arbeitnow_{slug}"

            title = str(job_data.get("title") or "Untitled Role")[:255]
            company = str(job_data.get("company_name") or job_data.get("company") or "Unknown Company")[:255]
            job_loc = str(job_data.get("location") or "")[:255]
            is_remote = bool(job_data.get("remote"))
            category = str(job_data.get("category") or ", ".join(job_data.get("tags", [])[:3]))[:100]
            salary = str(job_data.get("salary") or "")[:255]
            url = str(job_data.get("url") or "")
            description = str(job_data.get("description") or "")
            
            posted_date_val = job_data.get("posted_date")
            if not posted_date_val and job_data.get("created_at"):
                ts = job_data.get("created_at")
                if isinstance(ts, (int, float)):
                    posted_date_val = datetime.fromtimestamp(ts).date()
                elif isinstance(ts, str):
                    try:
                        posted_date_val = datetime.fromisoformat(ts[:10]).date()
                    except ValueError:
                        posted_date_val = None

            # Upsert job
            cursor.execute(
                """
                INSERT INTO jobs (external_job_id, title, company, location, remote, category, salary, url, description, posted_date)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                """,
                (external_id, title, company, job_loc, is_remote, category, salary, url, description, posted_date_val),
            )

            # Retrieve database job_id
            cursor.execute("SELECT job_id FROM jobs WHERE external_job_id = %s", (external_id,))
            job_row = cursor.fetchone()
            if not job_row:
                raise RuntimeError(f"Could not retrieve job_id for external ID: {external_id}")
            job_id = job_row["job_id"]

            # Process skill tags
            tags = job_data.get("tags") or []
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split(",") if t.strip()]

            for tag in tags:
                tag_clean = str(tag).strip()[:100]
                if not tag_clean:
                    continue
                # Insert skill if not exists
                cursor.execute(
                    "INSERT IGNORE INTO skills (skill_name) VALUES (%s)",
                    (tag_clean,),
                )
                cursor.execute("SELECT skill_id FROM skills WHERE skill_name = %s", (tag_clean,))
                skill_row = cursor.fetchone()
                if skill_row:
                    skill_id = skill_row["skill_id"]
                    cursor.execute(
                        "INSERT IGNORE INTO job_skills (job_id, skill_id) VALUES (%s, %s)",
                        (job_id, skill_id),
                    )

            # Insert search_results entry
            cursor.execute(
                """
                INSERT INTO search_results (search_id, job_id, relevance_score, rank_position)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    relevance_score = VALUES(relevance_score),
                    rank_position = VALUES(rank_position)
                """,
                (search_id, job_id, score, rank_pos),
            )

        conn.commit()
        return search_id
    except Exception as exc:
        conn.rollback()
        raise RuntimeError(f"Transaction failed and was rolled back: {sanitize_db_error(exc)}") from exc
    finally:
        cursor.close()
        conn.close()


def get_user_searches(user_id: int, limit: int = 30) -> list[dict[str, Any]]:
    """Retrieve history of searches conducted by a specific candidate profile."""
    with get_db_cursor(commit=False) as (conn, cursor):
        cursor.execute(
            """
            SELECT s.search_id, s.skill_query, s.location, s.remote_only, s.created_at,
                   COUNT(sr.search_result_id) AS result_count
            FROM searches s
            LEFT JOIN search_results sr ON s.search_id = sr.search_id
            WHERE s.user_id = %s
            GROUP BY s.search_id, s.skill_query, s.location, s.remote_only, s.created_at
            ORDER BY s.created_at DESC
            LIMIT %s
            """,
            (user_id, limit),
        )
        return [dict(row) for row in cursor.fetchall()]


def get_search_results_by_id(search_id: int, user_id: int) -> list[dict[str, Any]]:
    """Open saved ranked results from MySQL without repeating the external API call."""
    with get_db_cursor(commit=False) as (conn, cursor):
        cursor.execute(
            """
            SELECT j.job_id, j.external_job_id, j.title, j.company, j.location,
                   j.remote, j.category, j.salary, j.url, j.description, j.posted_date,
                   sr.relevance_score, sr.rank_position,
                   GROUP_CONCAT(DISTINCT sk.skill_name SEPARATOR '||') AS skills_list
            FROM search_results sr
            JOIN searches s ON s.search_id = sr.search_id
            JOIN jobs j ON j.job_id = sr.job_id
            LEFT JOIN job_skills js ON js.job_id = j.job_id
            LEFT JOIN skills sk ON sk.skill_id = js.skill_id
            WHERE sr.search_id = %s AND s.user_id = %s
            GROUP BY j.job_id, j.external_job_id, j.title, j.company, j.location,
                     j.remote, j.category, j.salary, j.url, j.description, j.posted_date,
                     sr.relevance_score, sr.rank_position
            ORDER BY sr.rank_position ASC
            """,
            (search_id, user_id),
        )
        rows = cursor.fetchall()
        results = []
        for r in rows:
            row_dict = dict(r)
            skills_str = row_dict.pop("skills_list", None)
            row_dict["tags"] = [s for s in skills_str.split("||") if s] if skills_str else []
            row_dict["company_name"] = row_dict["company"]
            results.append(row_dict)
        return results


def toggle_save_job(user_id: int, job_id: int) -> bool:
    """Toggle a bookmark for the selected user profile. Returns True if now saved, False if removed."""
    with get_db_cursor(commit=True) as (conn, cursor):
        cursor.execute("SELECT user_id FROM users WHERE user_id = %s", (user_id,))
        if not cursor.fetchone():
            cursor.execute(
                "INSERT INTO users (user_id, name, email) VALUES (%s, %s, %s) "
                "ON DUPLICATE KEY UPDATE name = VALUES(name)",
                (user_id, "Candidate Profile", f"candidate_{user_id}@example.com"),
            )
        cursor.execute(
            "SELECT saved_job_id FROM saved_jobs WHERE user_id = %s AND job_id = %s",
            (user_id, job_id),
        )
        row = cursor.fetchone()
        if row:
            cursor.execute(
                "DELETE FROM saved_jobs WHERE user_id = %s AND job_id = %s",
                (user_id, job_id),
            )
            return False
        else:
            cursor.execute(
                "INSERT IGNORE INTO saved_jobs (user_id, job_id) VALUES (%s, %s)",
                (user_id, job_id),
            )
            return True


def is_job_saved(user_id: int, job_id: int) -> bool:
    """Check if a specific job is bookmarked by the user."""
    with get_db_cursor(commit=False) as (conn, cursor):
        cursor.execute(
            "SELECT 1 FROM saved_jobs WHERE user_id = %s AND job_id = %s LIMIT 1",
            (user_id, job_id),
        )
        return cursor.fetchone() is not None


def get_saved_job_ids(user_id: int) -> set[int]:
    """Retrieve all job_ids currently saved by this user for quick O(1) checks."""
    with get_db_cursor(commit=False) as (conn, cursor):
        cursor.execute("SELECT job_id FROM saved_jobs WHERE user_id = %s", (user_id,))
        return {r["job_id"] for r in cursor.fetchall()}


def get_saved_jobs(user_id: int) -> list[dict[str, Any]]:
    """Retrieve all persistent bookmarks for the selected candidate profile."""
    with get_db_cursor(commit=False) as (conn, cursor):
        cursor.execute(
            """
            SELECT j.job_id, j.external_job_id, j.title, j.company, j.location,
                   j.remote, j.category, j.salary, j.url, j.description, j.posted_date,
                   sj.saved_at,
                   GROUP_CONCAT(DISTINCT sk.skill_name SEPARATOR '||') AS skills_list
            FROM saved_jobs sj
            JOIN jobs j ON j.job_id = sj.job_id
            LEFT JOIN job_skills js ON js.job_id = j.job_id
            LEFT JOIN skills sk ON sk.skill_id = js.skill_id
            WHERE sj.user_id = %s
            GROUP BY j.job_id, j.external_job_id, j.title, j.company, j.location,
                     j.remote, j.category, j.salary, j.url, j.description, j.posted_date, sj.saved_at
            ORDER BY sj.saved_at DESC
            """,
            (user_id,),
        )
        rows = cursor.fetchall()
        results = []
        for r in rows:
            row_dict = dict(r)
            skills_str = row_dict.pop("skills_list", None)
            row_dict["tags"] = [s for s in skills_str.split("||") if s] if skills_str else []
            row_dict["company_name"] = row_dict["company"]
            results.append(row_dict)
        return results


def get_analytics_metrics() -> dict[str, Any]:
    """Calculate actual metrics and frequency tables directly from local MySQL tables."""
    with get_db_cursor(commit=False) as (conn, cursor):
        # 1. Total searches
        cursor.execute("SELECT COUNT(*) AS cnt FROM searches")
        total_searches = cursor.fetchone()["cnt"]

        # 2. Total unique jobs
        cursor.execute("SELECT COUNT(*) AS cnt FROM jobs")
        total_jobs = cursor.fetchone()["cnt"]

        # 3. Total saved bookmarks across all users
        cursor.execute("SELECT COUNT(*) AS cnt FROM saved_jobs")
        total_saved = cursor.fetchone()["cnt"]

        # 4. Remote jobs count and share
        cursor.execute("SELECT COUNT(*) AS cnt FROM jobs WHERE remote = 1")
        remote_jobs = cursor.fetchone()["cnt"]
        remote_pct = (remote_jobs / total_jobs * 100.0) if total_jobs > 0 else 0.0

        # 5. Top skills by frequency in job listings
        cursor.execute(
            """
            SELECT sk.skill_name, COUNT(js.job_id) AS frequency
            FROM skills sk
            JOIN job_skills js ON js.skill_id = sk.skill_id
            GROUP BY sk.skill_id, sk.skill_name
            ORDER BY frequency DESC
            LIMIT 15
            """
        )
        top_skills = [dict(r) for r in cursor.fetchall()]

        # 6. Top hiring companies
        cursor.execute(
            """
            SELECT company, COUNT(*) AS job_count
            FROM jobs
            WHERE company IS NOT NULL AND company != ''
            GROUP BY company
            ORDER BY job_count DESC
            LIMIT 10
            """
        )
        top_companies = [dict(r) for r in cursor.fetchall()]

        return {
            "total_searches": total_searches,
            "total_jobs": total_jobs,
            "total_saved": total_saved,
            "remote_jobs": remote_jobs,
            "remote_pct": round(remote_pct, 1),
            "top_skills": top_skills,
            "top_companies": top_companies,
        }


def get_cached_jobs_for_fallback(
    query: str = "",
    location: str = "",
    remote_only: bool = False,
    limit: int = 50,
) -> tuple[list[dict[str, Any]], datetime | None]:
    """Retrieve previously imported jobs directly from MySQL when the external API is unreachable."""
    with get_db_cursor(commit=False) as (conn, cursor):
        # Find latest imported job date
        cursor.execute("SELECT MAX(created_at) AS latest_created FROM jobs")
        latest_row = cursor.fetchone()
        latest_cache = latest_row["latest_created"] if latest_row else None

        sql = """
            SELECT j.job_id, j.external_job_id, j.title, j.company, j.location,
                   j.remote, j.category, j.salary, j.url, j.description, j.posted_date,
                   GROUP_CONCAT(DISTINCT sk.skill_name SEPARATOR '||') AS skills_list
            FROM jobs j
            LEFT JOIN job_skills js ON js.job_id = j.job_id
            LEFT JOIN skills sk ON sk.skill_id = js.skill_id
            WHERE 1=1
        """
        params: list[Any] = []

        if remote_only:
            sql += " AND j.remote = 1"
        if location.strip():
            sql += " AND LOWER(j.location) LIKE %s"
            params.append(f"%{location.strip().lower()}%")

        sql += """
            GROUP BY j.job_id, j.external_job_id, j.title, j.company, j.location,
                     j.remote, j.category, j.salary, j.url, j.description, j.posted_date
            ORDER BY j.posted_date DESC, j.job_id DESC
            LIMIT %s
        """
        params.append(limit)

        cursor.execute(sql, tuple(params))
        rows = cursor.fetchall()
        results = []
        for r in rows:
            row_dict = dict(r)
            skills_str = row_dict.pop("skills_list", None)
            row_dict["tags"] = [s for s in skills_str.split("||") if s] if skills_str else []
            row_dict["company_name"] = row_dict["company"]
            results.append(row_dict)
        return results, latest_cache
