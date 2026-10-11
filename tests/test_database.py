"""Tests for transactional database persistence, rollbacks, and profile scoping."""

from unittest.mock import MagicMock, patch
# pyrefly: ignore [missing-import]
import pytest
from database.connection import test_db_connection as check_db_connection
from database.repository import (
    save_search_transaction,
    toggle_save_job,
    get_saved_jobs,
)

# Check if a live local MySQL database is currently available
IS_MYSQL_AVAILABLE, MYSQL_DIAGNOSTIC = check_db_connection()


def test_db_connection_diagnostic_output():
    """Verify test_db_connection returns a valid boolean status and string message."""
    is_conn, msg = check_db_connection()
    assert isinstance(is_conn, bool)
    assert isinstance(msg, str)
    assert len(msg) > 0


def test_transaction_rollback_on_failure():
    """Verify that if an error occurs while persisting search results,
    the transaction is rolled back and connections are reliably closed.
    """
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor

    # Simulate error on inserting second ranked job
    mock_cursor.execute.side_effect = [
        None,  # INSERT searches succeeds
        None,  # INSERT jobs (job 1)
        None,  # SELECT job_id (job 1)
        None,  # INSERT search_results (job 1)
        RuntimeError("Simulated database failure during batch"),  # Error on job 2
    ]

    mock_cursor.lastrowid = 42
    mock_cursor.fetchone.return_value = {"job_id": 101}

    sample_ranked = [
        {"job": {"external_job_id": "job_1", "title": "Dev 1"}, "relevance_score": 80.0},
        {"job": {"external_job_id": "job_2", "title": "Dev 2"}, "relevance_score": 60.0},
    ]

    with patch("database.repository.get_db_connection", return_value=mock_conn):
        with pytest.raises(RuntimeError, match="Transaction failed and was rolled back"):
            save_search_transaction(
                user_id=1,
                skill_query="python",
                location="Berlin",
                remote_only=False,
                ranked_jobs=sample_ranked,
            )

    # Verify rollback was called and connection/cursor closed
    mock_conn.rollback.assert_called_once()
    mock_cursor.close.assert_called_once()
    mock_conn.close.assert_called_once()


def test_duplicate_job_import_syntax():
    """Verify that jobs are upserted with ON DUPLICATE KEY UPDATE in MySQL queries."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.lastrowid = 1
    mock_cursor.fetchone.return_value = {"job_id": 10}

    sample_ranked = [
        {
            "job": {
                "external_job_id": "arbeitnow_test-slug",
                "title": "Software Engineer",
                "company_name": "Tech Corp",
                "location": "Berlin",
                "remote": True,
                "url": "https://example.com",
                "description": "Clean description",
            },
            "relevance_score": 95.0,
        }
    ]

    with patch("database.repository.get_db_connection", return_value=mock_conn):
        search_id = save_search_transaction(
            user_id=1,
            skill_query="python",
            location="Berlin",
            remote_only=False,
            ranked_jobs=sample_ranked,
        )

    assert search_id == 1
    # Check that ON DUPLICATE KEY UPDATE was part of the executed SQL queries
    executed_queries = [call[0][0] for call in mock_cursor.execute.call_args_list if call[0]]
    job_upsert_query = [q for q in executed_queries if "INSERT INTO jobs" in q]
    assert len(job_upsert_query) > 0
    assert "ON DUPLICATE KEY UPDATE" in job_upsert_query[0]
    mock_conn.commit.assert_called_once()


def test_mocked_saved_jobs_operations():
    """Verify bookmark retrieval and toggle execution with properly parameterized SQL tuples."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_conn.is_connected.return_value = True

    # Mock cursor responses for get_saved_jobs
    mock_cursor.fetchall.return_value = [
        {
            "job_id": 5,
            "external_job_id": "job_5",
            "title": "Data Engineer",
            "company": "DataCorp",
            "location": "Berlin",
            "remote": False,
            "category": "Data",
            "salary": None,
            "url": "http://example.com",
            "description": "SQL and Python",
            "posted_date": None,
            "saved_at": None,
            "skills_list": "python||sql",
        }
    ]

    with patch("database.connection.get_db_connection", return_value=mock_conn):
        saved = get_saved_jobs(user_id=42)

    assert len(saved) == 1
    assert saved[0]["job_id"] == 5
    assert saved[0]["tags"] == ["python", "sql"]

    # Verify that cursor.execute was called with a single-element tuple (user_id,)
    query_call = mock_cursor.execute.call_args
    assert query_call is not None
    params = query_call[0][1]
    assert isinstance(params, tuple)
    assert params == (42,)


@pytest.mark.skipif(not IS_MYSQL_AVAILABLE, reason="Requires live configured MySQL Server")
def test_live_mysql_profile_scoped_bookmarks():
    """Live integration test: verifies user-scoped bookmark isolation in local MySQL."""
    from database.repository import get_or_create_user

    # Create two test users
    user_a = get_or_create_user("Test User A", "test_user_a_scoped@example.com")
    user_b = get_or_create_user("Test User B", "test_user_b_scoped@example.com")

    # Bookmark a test job for User A
    toggle_save_job(user_a["user_id"], 1)

    saved_a = get_saved_jobs(user_a["user_id"])
    saved_b = get_saved_jobs(user_b["user_id"])

    # User A should have the bookmark, User B should not
    job_ids_a = {j["job_id"] for j in saved_a}
    job_ids_b = {j["job_id"] for j in saved_b}
    assert 1 in job_ids_a
    assert 1 not in job_ids_b
