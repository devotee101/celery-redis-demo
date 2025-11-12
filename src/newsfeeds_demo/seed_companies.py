"""Utility to seed the companies management database from JSON configuration."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable, Sequence

from sqlalchemy.orm import Session

from .database import Company, Source, get_session_local, init_db


def _load_config(path: Path) -> Sequence[dict]:
    """Load and validate the JSON configuration file."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:  # pragma: no cover - simple IO guard
        raise SystemExit(f"Configuration file not found: {path}") from exc
    except json.JSONDecodeError as exc:  # pragma: no cover - simple IO guard
        raise SystemExit(f"Invalid JSON in configuration file {path}: {exc}") from exc

    if not isinstance(payload, list):
        raise SystemExit("Configuration should be a list of objects.")

    for entry in payload:
        if not isinstance(entry, dict):
            raise SystemExit("Each configuration entry must be an object.")
        if "company" not in entry or "sources" not in entry:
            raise SystemExit("Each entry must contain 'company' and 'sources'.")
        if not isinstance(entry["company"], str):
            raise SystemExit("'company' must be a string.")
        if not isinstance(entry["sources"], Sequence):
            raise SystemExit("'sources' must be a list of strings.")
    return payload


def _get_or_create_source(session: Session, source_name: str) -> tuple[Source, bool]:
    source = session.query(Source).filter(Source.name == source_name).one_or_none()
    created = False
    if source is None:
        source = Source(name=source_name)
        session.add(source)
        session.flush()
        created = True
    return source, created


def seed_database(entries: Iterable[dict]) -> dict[str, int]:
    """Seed the companies and sources tables from configuration entries."""
    init_db()
    SessionLocal = get_session_local()
    session: Session = SessionLocal()
    companies_created = 0
    sources_created = 0

    try:
        for entry in entries:
            company_name = entry["company"].strip()
            source_names = [src.strip() for src in entry.get("sources", []) if isinstance(src, str)]

            company = session.query(Company).filter(Company.name == company_name).one_or_none()
            if company is None:
                company = Company(name=company_name)
                session.add(company)
                session.flush()
                companies_created += 1

            for source_name in source_names:
                source, created = _get_or_create_source(session, source_name)
                if created:
                    sources_created += 1
                if source not in company.sources:
                    company.sources.append(source)

        session.commit()
        return {"companies_created": companies_created, "sources_created": sources_created}
    finally:
        session.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Seed the companies management database from a JSON file."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/companies.json"),
        help="Path to the companies JSON configuration file.",
    )
    args = parser.parse_args()

    entries = _load_config(args.config)
    stats = seed_database(entries)
    print(
        f"Seeding complete. Companies created: {stats['companies_created']}, "
        f"new sources created: {stats['sources_created']}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

