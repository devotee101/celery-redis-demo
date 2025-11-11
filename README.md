# Newsfeeds Celery Demo

This repository provides a minimal example of orchestrating a Python Celery worker with Redis using Docker Compose. It demonstrates how you could enqueue news retrieval jobs (for example, Brave Search API lookups) for a set of company/source combinations and have them processed asynchronously.

## Prerequisites

- Docker and Docker Compose
- Python 3.12 (only required if you want to run the CLI locally without Docker)

## Project Layout

- `docker-compose.yml` – brings up Redis and the Celery worker
- `Dockerfile.worker` – builds the worker image
- `src/newsfeeds_demo/` – demo Celery app, tasks, and CLI

## Getting Started

1. **Install dependencies (optional, for local CLI usage):**

   ```bash
   cd /home/ant/src/newsfeeds
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Start Redis and the worker:**

   ```bash
   docker-compose up --build
   ```

   This exposes Redis on `redis://localhost:6379` and starts a Celery worker listening for tasks on the `newsfeeds-demo` queue. The worker concurrency is pinned to 5 so only five Brave API calls (or other downstream requests) run at once.

3. **Enqueue tasks from the host:**

   With the virtual environment active (or `pip install -r requirements.txt` executed globally), run:

   ```bash
   python -m newsfeeds_demo.cli "Airbus:Financial Times" "Airbus:BBC" "British Steel:Sky News"
   ```

   Each `COMPANY:SOURCE` pair is pushed onto the Redis queue. The worker logs will show the mocked processing and returned payload.

   To enqueue a larger batch, prepare a JSON file like `config/companies.json` and use the `--config` flag:

   ```bash
   python -m newsfeeds_demo.cli --config config/companies.json
   ```

   The CLI infers all combinations listed in the JSON file (for example, 100 companies × 10 sources = 1000 jobs) and enqueues them while respecting the worker concurrency ceiling.

## Customising

- Update `src/newsfeeds_demo/tasks.py` with real Brave Search API calls or S3 persistence logic.
- Adjust Celery configuration in `src/newsfeeds_demo/celery_app.py` (queues, middlewares, retries, etc.).
- Extend the CLI to pull company/source configurations from Postgres or another source before enqueueing.
- Consider Celery rate limits (`task_annotations`) or retry policies if the Brave API enforces per-minute quotas.

## Stopping Services

Press `Ctrl+C` in the terminal running `docker-compose up`, then remove containers with:

```bash
docker-compose down
```
