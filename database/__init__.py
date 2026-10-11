"""Database package for MySQL connection and repository operations."""
from .connection import get_db_connection, test_db_connection, init_db_schema, get_db_config
from .repository import (
    get_or_create_user,
    list_all_users,
    save_search_transaction,
    get_user_searches,
    get_search_results_by_id,
    toggle_save_job,
    is_job_saved,
    get_saved_jobs,
    get_analytics_metrics,
    get_cached_jobs_for_fallback,
)

__all__ = [
    "get_db_connection",
    "test_db_connection",
    "init_db_schema",
    "get_db_config",
    "get_or_create_user",
    "list_all_users",
    "save_search_transaction",
    "get_user_searches",
    "get_search_results_by_id",
    "toggle_save_job",
    "is_job_saved",
    "get_saved_jobs",
    "get_analytics_metrics",
    "get_cached_jobs_for_fallback",
]
