import os

from celery import Celery


def _build_url(env_var: str, default: str) -> str:
    """Return a Celery connection URL pulled from the environment."""
    return os.getenv(env_var, default)


BROKER_URL = _build_url("CELERY_BROKER_URL", "redis://localhost:6379/0")
BACKEND_URL = _build_url("CELERY_BACKEND_URL", "redis://localhost:6379/1")

celery_app = Celery("newsfeeds_demo", broker=BROKER_URL, backend=BACKEND_URL)
celery_app.conf.task_default_queue = "newsfeeds-demo"
celery_app.conf.task_default_routing_key = "newsfeeds-demo"
celery_app.autodiscover_tasks(["newsfeeds_demo"])

