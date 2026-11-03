"""Application configuration loaded from environment variables."""

import os
from pathlib import Path

from dotenv import load_dotenv

# resolve the repository root from this file's location.
PROJECT_ROOT = Path(__file__).resolve().parents[5]

# environment variables explicitly set by the operating system.
load_dotenv(PROJECT_ROOT / ".env")


# loads the database url record.
def get_database_url() -> str:
    """Return the configured PostgreSQL connection string."""
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is not configured. "
            "Set it in the environment or root .env file."
        )

    return database_url


# loads the jwt secret key record.
def get_jwt_secret_key() -> str:
    secret = os.getenv("JWT_SECRET_KEY")

    if not secret:
        raise RuntimeError("JWT_SECRET_KEY is not configured")

    return secret


# loads the redis connection url
def get_redis_url() -> str:
    redis_url = os.getenv("REDIS_DEVELOPMENT_URL")

    if not redis_url:
        raise RuntimeError("REDIS_DEVELOPMENT_URL is not configured")

    return redis_url


# loads the dedicated redis test connection url
def get_test_redis_url() -> str:
    redis_url = os.getenv("REDIS_TESTING_URL")
    if not redis_url:
        raise RuntimeError("REDIS_TESTING_URL is not configured")
    return redis_url
