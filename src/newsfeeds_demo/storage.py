"""S3 storage utilities supporting AWS and local MinIO development."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError


def _resolve_bool(env_var: str, default: str = "false") -> bool:
    return os.getenv(env_var, default).strip().lower() in {"1", "true", "yes"}


def get_s3_client():
    """Create and return an S3 client (works for AWS and MinIO)."""
    endpoint = os.getenv("S3_ENDPOINT") or os.getenv("MINIO_ENDPOINT")
    region = os.getenv("S3_REGION", "us-east-1")
    access_key = (
        os.getenv("AWS_ACCESS_KEY_ID")
        or os.getenv("S3_ACCESS_KEY")
        or os.getenv("MINIO_ACCESS_KEY")
        or "minioadmin"
    )
    secret_key = (
        os.getenv("AWS_SECRET_ACCESS_KEY")
        or os.getenv("S3_SECRET_KEY")
        or os.getenv("MINIO_SECRET_KEY")
        or "minioadmin"
    )
    session_token = os.getenv("AWS_SESSION_TOKEN")

    addressing_style = os.getenv("S3_ADDRESSING_STYLE", "auto")
    use_ssl = _resolve_bool("S3_USE_SSL", "true")

    config = Config(
        region_name=region,
        signature_version="s3v4",
        s3={"addressing_style": addressing_style},
    )

    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        aws_session_token=session_token,
        use_ssl=use_ssl,
        config=config,
    )


def ensure_bucket_exists(client, bucket_name: str) -> None:
    """Ensure an S3 bucket exists, creating it when necessary."""
    try:
        client.head_bucket(Bucket=bucket_name)
        return
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code")
        if error_code not in ("404", "NoSuchBucket", "NotFound"):
            raise RuntimeError(f"Failed to check bucket {bucket_name}: {exc}") from exc

    region = client.meta.region_name or os.getenv("S3_REGION", "us-east-1")
    create_kwargs = {"Bucket": bucket_name}
    if region and region != "us-east-1":
        create_kwargs["CreateBucketConfiguration"] = {"LocationConstraint": region}

    try:
        client.create_bucket(**create_kwargs)
    except ClientError as exc:
        raise RuntimeError(f"Failed to create bucket {bucket_name}: {exc}") from exc


def _make_object_path(company: str, source: str) -> str:
    source_snake = source.lower().replace(" ", "_").replace("-", "_")
    return f"{company}/{source_snake}.json"


def save_article_json(company: str, source: str, article_data: dict, bucket_name: str) -> str:
    """Persist article data to S3 as JSON."""
    client = get_s3_client()
    ensure_bucket_exists(client, bucket_name)
    object_path = _make_object_path(company, source)

    try:
        client.put_object(
            Bucket=bucket_name,
            Key=object_path,
            Body=json.dumps(article_data, indent=2).encode("utf-8"),
            ContentType="application/json",
        )
        return object_path
    except ClientError as exc:
        raise RuntimeError(f"Failed to save article for {company}/{source}: {exc}") from exc


def get_article_json(company: str, source: str, bucket_name: str) -> Optional[dict]:
    """Retrieve article JSON from S3."""
    client = get_s3_client()
    object_path = _make_object_path(company, source)

    try:
        response = client.get_object(Bucket=bucket_name, Key=object_path)
        payload = response["Body"].read()
        return json.loads(payload.decode("utf-8"))
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code")
        if error_code in ("NoSuchKey", "404"):
            return None
        raise RuntimeError(f"Failed to retrieve article for {company}/{source}: {exc}") from exc


def list_companies(bucket_name: str) -> list[str]:
    """List distinct companies (top-level prefixes) in the bucket."""
    client = get_s3_client()
    companies: set[str] = set()
    continuation_token = None

    try:
        while True:
            kwargs = {
                "Bucket": bucket_name,
                "Delimiter": "/",
                "Prefix": "",
            }
            if continuation_token:
                kwargs["ContinuationToken"] = continuation_token

            response = client.list_objects_v2(**kwargs)
            for prefix in response.get("CommonPrefixes", []):
                name = prefix.get("Prefix", "").rstrip("/")
                if name:
                    companies.add(name)

            if not response.get("IsTruncated"):
                break
            continuation_token = response.get("NextContinuationToken")

        return sorted(companies)
    except ClientError as exc:
        raise RuntimeError(f"Failed to list companies: {exc}") from exc


def list_sources_for_company(company: str, bucket_name: str) -> list[str]:
    """List all sources (files) under a company prefix."""
    client = get_s3_client()
    prefix = f"{company}/"
    continuation_token = None
    sources: list[str] = []

    try:
        while True:
            kwargs = {"Bucket": bucket_name, "Prefix": prefix}
            if continuation_token:
                kwargs["ContinuationToken"] = continuation_token

            response = client.list_objects_v2(**kwargs)
            for obj in response.get("Contents", []):
                key = obj.get("Key", "")
                if not key.endswith(".json"):
                    continue
                source_file = Path(key).stem
                source_name = source_file.replace("_", " ").title()
                sources.append(source_name)

            if not response.get("IsTruncated"):
                break
            continuation_token = response.get("NextContinuationToken")

        return sorted(set(sources))
    except ClientError as exc:
        raise RuntimeError(f"Failed to list sources for {company}: {exc}") from exc


def get_articles_for_company(company: str, bucket_name: str) -> list[dict[str, Any]]:
    """Retrieve all article payloads stored for a company across every source."""
    client = get_s3_client()
    prefix = f"{company}/"
    continuation_token = None
    articles: list[dict[str, Any]] = []

    try:
        while True:
            kwargs = {"Bucket": bucket_name, "Prefix": prefix}
            if continuation_token:
                kwargs["ContinuationToken"] = continuation_token

            response = client.list_objects_v2(**kwargs)
            for obj in response.get("Contents", []):
                key = obj.get("Key", "")
                if not key.endswith(".json"):
                    continue

                try:
                    payload = client.get_object(Bucket=bucket_name, Key=key)["Body"].read()
                    data = json.loads(payload.decode("utf-8"))
                except ClientError as exc:
                    error_code = exc.response.get("Error", {}).get("Code")
                    if error_code in ("NoSuchKey", "404"):
                        continue
                    raise RuntimeError(
                        f"Failed to retrieve article object {key}: {exc}"
                    ) from exc

                if isinstance(data, dict):
                    data.setdefault("company", company)
                    if not data.get("source"):
                        source_slug = Path(key).stem.replace("_", " ")
                        data["source"] = source_slug
                    articles.append(data)

            if not response.get("IsTruncated"):
                break

            continuation_token = response.get("NextContinuationToken")

        return articles
    except ClientError as exc:
        raise RuntimeError(
            f"Failed to list article objects for {company}: {exc}"
        ) from exc

