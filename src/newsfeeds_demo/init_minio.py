"""Script to initialize the local S3 bucket (MinIO in development)."""

from __future__ import annotations

import logging
import os
import time

from .storage import ensure_bucket_exists, get_s3_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def init_bucket(max_retries: int = 10, retry_delay: int = 2) -> None:
    """Initialise the configured bucket, retrying if the endpoint is not ready."""
    bucket_name = os.getenv("MINIO_BUCKET") or os.getenv("S3_BUCKET") or "newsfeeds"

    for attempt in range(max_retries):
        try:
            client = get_s3_client()
            ensure_bucket_exists(client, bucket_name)
            logger.info("Successfully ensured bucket '%s' exists", bucket_name)
            return
        except Exception as exc:  # pylint: disable=broad-except
            if attempt >= max_retries - 1:
                logger.error(
                    "Failed to initialize bucket '%s' after %s attempts: %s",
                    bucket_name,
                    max_retries,
                    exc,
                )
                raise
            logger.warning(
                "Attempt %s/%s to initialise bucket '%s' failed: %s; retrying in %ss",
                attempt + 1,
                max_retries,
                bucket_name,
                exc,
                retry_delay,
            )
            time.sleep(retry_delay)


if __name__ == "__main__":
    init_bucket()

