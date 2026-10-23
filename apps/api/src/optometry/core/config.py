"""Application configuration loaded from environment variables."""

import os
from pathlib import Path

from dotenv import load_dotenv

# Resolve the repository root from this file's location.
PROJECT_ROOT = Path(__file__).resolve().parents[5]

# Load local development settings without overwriting
# environment variables explicitly set by the operating system.
load_dotenv(PROJECT_ROOT / ".env")


def get_database_url() -> str:
    """Return the configured PostgreSQL connection string."""
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is not configured. "
            "Set it in the environment or root .env file."
        )

    return database_url
