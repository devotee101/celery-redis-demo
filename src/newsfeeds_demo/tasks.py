"""Celery tasks for fetching and storing news articles."""

from __future__ import annotations

import os
import time
from typing import Any, Dict

import httpx

from .celery_app import celery_app
from .storage import save_article_json
from .dead_letter import record_dead_letter


def _call_search_api(company: str, source: str, limit: int = 5) -> Dict[str, Any]:
    """Call the dummy search API and return the parsed JSON payload."""
    base_url = os.getenv("SEARCH_API_BASE_URL", "http://localhost:8002")
    url = f"{base_url.rstrip('/')}/search"

    with httpx.Client(timeout=10.0) as client:
        response = client.get(url, params={"company": company, "source": source, "limit": limit})
        response.raise_for_status()
        return response.json()


@celery_app.task(name="newsfeeds_demo.fetch_article")
def fetch_article(company: str, source: str) -> dict[str, Any]:
    """
    Fetch articles for a company from a source and store in MinIO.

    Args:
        company: Name of the company to search for.
        source: Name of the news source to query.

    Returns:
        Dictionary containing task result metadata.
    """
    start_timestamp = time.time()

    try:
        article_data = _call_search_api(company, source)
    except Exception as exc:  # pylint: disable=broad-except
        record_dead_letter(
            {
                "company": company,
                "source": source,
                "error": str(exc),
                "stage": "search_api",
                "started_at": start_timestamp,
            }
        )
        raise

    # Ensure required metadata present
    article_data.setdefault("company", company)
    article_data.setdefault("source", source)
    article_data.setdefault("fetched_at", time.time())

    bucket_name = os.getenv("MINIO_BUCKET", "newsfeeds")
    try:
        object_path = save_article_json(company, source, article_data, bucket_name)
        return {
        "status": "success",
            "company": company,
            "source": source,
            "object_path": object_path,
            "articles_count": len(article_data.get("articles", [])),
            "started_at": start_timestamp,
            "finished_at": time.time(),
        }
    except Exception as exc:  # pylint: disable=broad-except
        record_dead_letter(
            {
                "company": company,
                "source": source,
                "error": str(exc),
                "stage": "storage",
                "started_at": start_timestamp,
            }
        )
        raise

