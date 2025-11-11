import argparse
import json
import sys
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

from .celery_app import celery_app


def parse_pairs(raw_pairs: Iterable[str]) -> List[Tuple[str, str]]:
    """Return (company, source) tuples from CLI input."""
    parsed_pairs: List[Tuple[str, str]] = []
    for raw_pair in raw_pairs:
        try:
            company, source = raw_pair.split(":", maxsplit=1)
        except ValueError as exc:
            raise argparse.ArgumentTypeError(
                f"Invalid pair '{raw_pair}'. Expected format COMPANY:SOURCE"
            ) from exc

        parsed_pairs.append((company.strip(), source.strip()))

    return parsed_pairs


def load_pairs_from_config(path: Path) -> List[Tuple[str, str]]:
    """Load company/source pairs from a JSON config file."""
    try:
        payload = json.loads(path.read_text())
    except FileNotFoundError as exc:
        raise argparse.ArgumentTypeError(f"Config file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise argparse.ArgumentTypeError(f"Invalid JSON in config file: {path}") from exc

    if not isinstance(payload, list):
        raise argparse.ArgumentTypeError("Config must be a list of objects.")

    loaded_pairs: List[Tuple[str, str]] = []
    for entry in payload:
        if not isinstance(entry, dict):
            raise argparse.ArgumentTypeError("Each config entry must be an object.")

        try:
            company = entry["company"]
            sources: Sequence[str] = entry["sources"]
        except KeyError as exc:
            raise argparse.ArgumentTypeError(
                "Each entry must contain 'company' and 'sources'."
            ) from exc

        if not isinstance(company, str) or not isinstance(sources, Sequence):
            raise argparse.ArgumentTypeError(
                "'company' must be a string and 'sources' must be a list of strings."
            )

        for source in sources:
            if not isinstance(source, str):
                raise argparse.ArgumentTypeError("'sources' must contain only strings.")
            loaded_pairs.append((company.strip(), source.strip()))

    return loaded_pairs


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Enqueue demo newsfeed tasks into Celery via Redis."
    )
    parser.add_argument(
        "pairs",
        metavar="COMPANY:SOURCE",
        type=str,
        nargs="*",
        help=(
            "Company/source pair to enqueue. Provide multiple to enqueue multiple tasks. "
            "Use alongside --config to combine static and config-driven pairs."
        ),
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="Path to JSON file describing company/source combinations to enqueue.",
    )
    parser.add_argument(
        "--serialize",
        choices=["json", "text"],
        default="text",
        help="Format for printing task metadata after enqueue.",
    )

    args = parser.parse_args(argv)

    pairs: List[Tuple[str, str]] = []
    if args.config:
        pairs.extend(load_pairs_from_config(args.config))
    if args.pairs:
        pairs.extend(parse_pairs(args.pairs))

    if not pairs:
        parser.error("No tasks enqueued. Provide --config and/or COMPANY:SOURCE pairs.")

    results = []
    for company, source in pairs:
        async_result = celery_app.send_task(
            "newsfeeds_demo.fetch_article", kwargs={"company": company, "source": source}
        )
        results.append(
            {
                "company": company,
                "source": source,
                "task_id": async_result.id,
                "status": async_result.status,
            }
        )

    if args.serialize == "json":
        print(json.dumps(results, indent=2))
    else:
        for result in results:
            print(
                f"Queued {result['company']} / {result['source']} "
                f"(task_id={result['task_id']}, status={result['status']})"
            )

    return 0


if __name__ == "__main__":
    sys.exit(main())

