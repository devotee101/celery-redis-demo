"""Helpers for recording dead-lettered tasks for later inspection."""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict

import redis

DEAD_LETTER_KEY = os.getenv("DEAD_LETTER_KEY", "newsfeeds:dead_letter")


def _get_redis_client() -> redis.Redis:
    """Return a Redis client using the Celery broker URL by default."""
    url = os.getenv("REDIS_URL") or os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    return redis.Redis.from_url(url)


def record_dead_letter(payload: Dict[str, Any]) -> None:
    """Persist a dead-letter entry to Redis for later reporting."""
    client = _get_redis_client()
    entry = {
        "recorded_at": time.time(),
        **payload,
    }
    client.lpush(DEAD_LETTER_KEY, json.dumps(entry))

