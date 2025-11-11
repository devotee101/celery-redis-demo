import random
import time

from .celery_app import celery_app


@celery_app.task(name="newsfeeds_demo.fetch_article")
def fetch_article(company: str, source: str) -> dict:
    """Mock fetch of articles for a company from a source."""
    start_timestamp = time.time()
    # Simulate work with a random sleep to demonstrate async processing.
    simulated_latency = round(random.uniform(0.5, 2.0), 2)
    time.sleep(simulated_latency)

    return {
        "company": company,
        "source": source,
        "summary": f"Example coverage for {company} from {source}.",
        "latency_seconds": simulated_latency,
        "started_at": start_timestamp,
        "finished_at": time.time(),
    }

