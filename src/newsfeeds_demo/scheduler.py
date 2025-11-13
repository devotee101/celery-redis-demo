"""Scheduled service to read from PostgreSQL and enqueue tasks to Redis."""

import os
import time
import logging
import argparse
from sqlalchemy.orm import Session

from .database import get_session_local, Company
from .celery_app import celery_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def enqueue_company_source_tasks():
    """
    Read all companies and their sources from PostgreSQL and enqueue tasks to Redis.

    This function queries the database for all companies and their associated sources,
    then enqueues a Celery task for each company-source combination.
    """
    SessionLocal = get_session_local()
    db: Session = SessionLocal()

    try:
        companies = db.query(Company).all()
        total_tasks = 0

        for company in companies:
            for source in company.sources:
                try:
                    async_result = celery_app.send_task(
                        "newsfeeds_demo.fetch_article",
                        kwargs={"company": company.name, "source": source.name},
                    )
                    total_tasks += 1
                    logger.info(
                        f"Enqueued task for {company.name} / {source.name} "
                        f"(task_id={async_result.id})"
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to enqueue task for {company.name} / {source.name}: {e}"
                    )

        logger.info(f"Successfully enqueued {total_tasks} tasks")
        return total_tasks

    except Exception as e:
        logger.error(f"Error reading from database: {e}")
        raise
    finally:
        db.close()


def run_scheduler():
    """
    Run the scheduler in a loop, executing every N hours as specified by environment variable.

    The interval is controlled by SCHEDULE_INTERVAL_HOURS environment variable,
    defaulting to 4 hours if not set.
    """
    interval_hours = int(os.getenv("SCHEDULE_INTERVAL_HOURS", "4"))
    interval_seconds = interval_hours * 3600

    logger.info(f"Starting scheduler with interval of {interval_hours} hours")

    while True:
        try:
            logger.info("Starting scheduled task enqueue cycle")
            enqueue_company_source_tasks()
            logger.info(f"Sleeping for {interval_hours} hours until next cycle")
            time.sleep(interval_seconds)
        except KeyboardInterrupt:
            logger.info("Scheduler interrupted by user")
            break
        except Exception as e:
            logger.error(f"Error in scheduler loop: {e}")
            logger.info("Continuing after error, will retry on next cycle")
            time.sleep(interval_seconds)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scheduler service for enqueueing news feed tasks")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run the scheduler once immediately and exit (instead of running in a loop)",
    )
    args = parser.parse_args()

    if args.once:
        logger.info("Running scheduler once (manual trigger)")
        enqueue_company_source_tasks()
    else:
        run_scheduler()

