"""MySQL database connection management using mysql-connector-python and python-dotenv."""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Generator, Any
from dotenv import load_dotenv
import mysql.connector
from mysql.connector import errorcode

# Load environment variables from .env file in project directory
load_dotenv(override=True)


def get_env_or_secret(key: str, default: str = "") -> str:
    """Retrieve configuration securely from local environment variables (.env) or Streamlit Cloud secrets."""
    val = os.getenv(key)
    if val is not None and val != "":
        return val
    try:
        import streamlit as st
        if hasattr(st, "secrets") and key in st.secrets:
            return str(st.secrets[key])
    except Exception:
        pass
    return default


def get_db_config(database: str | None = None) -> dict[str, Any]:
    """Retrieve database connection parameters securely from environment variables or secrets."""
    # Reload environment variables from .env dynamically on each config request
    load_dotenv(override=True)

    default_db = get_env_or_secret("DB_NAME", "job_recommendation_db")
    target_db = database if database is not None else default_db
    
    port_str = get_env_or_secret("DB_PORT", "3306")
    try:
        port = int(port_str)
    except ValueError:
        port = 3306

    timeout_str = get_env_or_secret("DB_TIMEOUT", "10")
    try:
        timeout = int(timeout_str)
    except ValueError:
        timeout = 10

    cfg: dict[str, Any] = {
        "host": get_env_or_secret("DB_HOST", "localhost"),
        "port": port,
        "user": get_env_or_secret("DB_USER", "root"),
        "password": get_env_or_secret("DB_PASSWORD", ""),
        "database": target_db,
        "charset": "utf8mb4",
        "collation": "utf8mb4_unicode_ci",
        "autocommit": False,
        "connection_timeout": timeout,
    }

    # Cloud database SSL support (Aiven, Railway, AWS RDS, etc.)
    ssl_disabled = get_env_or_secret("DB_SSL_DISABLED", "").lower() in ("true", "1", "yes")
    if ssl_disabled:
        cfg["ssl_disabled"] = True
    ssl_ca = get_env_or_secret("DB_SSL_CA", "")
    if ssl_ca:
        cfg["ssl_ca"] = ssl_ca

    return cfg


def get_db_connection(database: str | None = None) -> mysql.connector.MySQLConnection:
    """Create and return a new MySQL connection. Caller is responsible for closing."""
    config = get_db_config(database=database)
    try:
        return mysql.connector.connect(**config)
    except mysql.connector.Error as exc:
        # If localhost fails with CR_CONN_HOST_ERROR (Windows IPv6 ::1 issue), fallback to 127.0.0.1
        if exc.errno in (errorcode.CR_CONN_HOST_ERROR, 2003) and config.get("host") == "localhost":
            fallback_config = dict(config)
            fallback_config["host"] = "127.0.0.1"
            return mysql.connector.connect(**fallback_config)
        raise


@contextmanager
def get_db_cursor(commit: bool = False, dictionary: bool = True) -> Generator[tuple[mysql.connector.MySQLConnection, Any], None, None]:
    """Context manager for safely acquiring and releasing a connection and cursor.
    Automatically rolls back on exceptions and commits if requested.
    """
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=dictionary)
        yield conn, cursor
        if commit:
            conn.commit()
    except Exception:
        if conn and conn.is_connected():
            conn.rollback()
        raise
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None and conn.is_connected():
            conn.close()


def sanitize_db_error(exc: Exception) -> str:
    """Provide a user-friendly, non-sensitive error explanation without exposing credentials or internal tracebacks."""
    if isinstance(exc, mysql.connector.Error):
        if exc.errno == errorcode.ER_ACCESS_DENIED_ERROR:
            return (
                "MySQL Access Denied: Incorrect username or password. "
                "Please verify DB_USER and DB_PASSWORD in your .env file."
            )
        elif exc.errno in (errorcode.CR_CONN_HOST_ERROR, 2003):
            host = get_env_or_secret("DB_HOST", "localhost")
            port = get_env_or_secret("DB_PORT", "3306")
            if host in ("localhost", "127.0.0.1"):
                return (
                    f"Cannot reach MySQL at {host}:{port}.\n\n"
                    "• If running on Streamlit Cloud (*.streamlit.app): Cloud servers cannot reach your home PC's localhost. "
                    "Configure cloud database secrets in Streamlit Cloud Settings > Secrets, or run locally on your PC via 'streamlit run job_search.py'.\n\n"
                    "• If running locally: Ensure MySQL80 is running in Windows Services and DB_PASSWORD in .env is correct."
                )
            return (
                f"Cannot connect to MySQL server at {host}:{port}. "
                "Ensure your remote database server is running and port is accessible."
            )
        elif exc.errno == errorcode.ER_BAD_DB_ERROR or exc.errno == 1049:
            db_name = os.getenv("DB_NAME", "job_recommendation_db")
            return (
                f"Unknown database '{db_name}'. "
                "Please execute 'sql/schema.sql' in MySQL Workbench to create the database and tables."
            )
        else:
            return f"MySQL Error (Code {exc.errno}): {exc.msg}"
    return f"Database Connection Error: {str(exc)}"


def test_db_connection() -> tuple[bool, str]:
    """Test connection to the configured MySQL database and return health status."""
    try:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            return True, "Connected successfully to local MySQL Server."
        finally:
            cursor.close()
            conn.close()
    except Exception as exc:
        return False, sanitize_db_error(exc)


def init_db_schema() -> tuple[bool, str]:
    """Ensure all required tables (including saved_jobs) exist without dropping existing tables or data."""
    create_tables_sql = [
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            email VARCHAR(150) NOT NULL UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_users_email (email)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """,
        """
        CREATE TABLE IF NOT EXISTS searches (
            search_id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            skill_query VARCHAR(500) NULL,
            location VARCHAR(150) NULL,
            remote_only BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
            INDEX idx_searches_user (user_id),
            INDEX idx_searches_created (created_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """,
        """
        CREATE TABLE IF NOT EXISTS jobs (
            job_id INT AUTO_INCREMENT PRIMARY KEY,
            external_job_id VARCHAR(150) NOT NULL UNIQUE,
            title VARCHAR(255) NOT NULL,
            company VARCHAR(255) NULL,
            location VARCHAR(255) NULL,
            remote BOOLEAN DEFAULT FALSE,
            category VARCHAR(100) NULL,
            salary VARCHAR(255) NULL,
            url TEXT NULL,
            description MEDIUMTEXT NULL,
            posted_date DATE NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_jobs_company (company),
            INDEX idx_jobs_location (location),
            INDEX idx_jobs_remote (remote),
            INDEX idx_jobs_posted (posted_date)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """,
        """
        CREATE TABLE IF NOT EXISTS skills (
            skill_id INT AUTO_INCREMENT PRIMARY KEY,
            skill_name VARCHAR(100) NOT NULL UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_skills_name (skill_name)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """,
        """
        CREATE TABLE IF NOT EXISTS job_skills (
            job_skill_id INT AUTO_INCREMENT PRIMARY KEY,
            job_id INT NOT NULL,
            skill_id INT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uq_job_skill (job_id, skill_id),
            FOREIGN KEY (job_id) REFERENCES jobs(job_id) ON DELETE CASCADE,
            FOREIGN KEY (skill_id) REFERENCES skills(skill_id) ON DELETE CASCADE,
            INDEX idx_job_skills_job (job_id),
            INDEX idx_job_skills_skill (skill_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """,
        """
        CREATE TABLE IF NOT EXISTS search_results (
            search_result_id INT AUTO_INCREMENT PRIMARY KEY,
            search_id INT NOT NULL,
            job_id INT NOT NULL,
            relevance_score DECIMAL(6,2) NOT NULL,
            rank_position INT NOT NULL,
            UNIQUE KEY uq_search_job (search_id, job_id),
            FOREIGN KEY (search_id) REFERENCES searches(search_id) ON DELETE CASCADE,
            FOREIGN KEY (job_id) REFERENCES jobs(job_id) ON DELETE CASCADE,
            INDEX idx_search_results_search (search_id),
            INDEX idx_search_results_job (job_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """,
        """
        CREATE TABLE IF NOT EXISTS saved_jobs (
            saved_job_id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            job_id INT NOT NULL,
            saved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uq_user_job_saved (user_id, job_id),
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
            FOREIGN KEY (job_id) REFERENCES jobs(job_id) ON DELETE CASCADE,
            INDEX idx_saved_jobs_user (user_id),
            INDEX idx_saved_jobs_job (job_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """
    ]

    try:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            for stmt in create_tables_sql:
                cursor.execute(stmt)
            conn.commit()
            return True, "Schema initialized successfully."
        finally:
            cursor.close()
            conn.close()
    except Exception as exc:
        return False, sanitize_db_error(exc)
