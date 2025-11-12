# Newsfeeds System

A scalable news article ingestion and retrieval system using Celery, Redis, PostgreSQL, MinIO (S3-compatible storage), and FastAPI. The system is designed to fetch news articles for multiple companies from various news sources, store them in object storage, and provide REST APIs for management and retrieval.

## Architecture

The system consists of the following components:

- **Redis**: Message broker for Celery task queue
- **PostgreSQL**: Database for storing company and source configurations
- **MinIO (dev) / Amazon S3 (prod)**: Object storage for news articles
- **Celery Worker**: Processes tasks to fetch articles and store them in MinIO
- **News API** (FastAPI): REST API for retrieving news articles from MinIO
- **Companies API** (FastAPI): REST API for managing companies and sources in PostgreSQL
- **Scheduler**: Service that reads from PostgreSQL and enqueues tasks to Redis on a schedule (default: every 4 hours)
- **Search API** (FastAPI): Dummy Brave Search replacement returning fictitious articles for testing

## Prerequisites

- Docker and Docker Compose
- Python 3.12+ (only required if you want to run the CLI locally without Docker)

## Project Layout

```
.
├── docker-compose.yml          # Orchestrates all services
├── Dockerfile.worker           # Celery worker image
├── Dockerfile.news-api         # News API service image
├── Dockerfile.companies-api    # Companies API service image
├── Dockerfile.search-api       # Dummy Search API service image
├── Dockerfile.scheduler        # Scheduler service image
├── requirements.txt            # Python dependencies
├── config/
│   └── companies.json         # Sample company/source configuration
└── src/newsfeeds_demo/
    ├── __init__.py
    ├── celery_app.py          # Celery application configuration
    ├── tasks.py               # Celery tasks for fetching articles
    ├── storage.py             # S3 storage utilities (MinIO in development)
    ├── database.py            # PostgreSQL models and session management
    ├── news_api.py            # FastAPI service for reading articles
    ├── companies_api.py       # FastAPI service for managing companies/sources
    ├── search_api.py          # Dummy Search API used by the worker
    ├── scheduler.py           # Scheduled task enqueue service
    ├── cli.py                 # CLI tool for manual task enqueueing
    └── init_minio.py          # MinIO bucket initialization
```

## Getting Started

### 1. Start All Services

```bash
docker-compose up --build
```

This will start:

- Redis on port `6379`
- PostgreSQL on port `55432`
- MinIO on ports `9000` (API) and `9001` (Console)
- Celery worker (concurrency: 5)
- Search API on port `8002`
- News API on port `8000`
- Companies API on port `8001`
- Scheduler (runs every 4 hours)

### 2. Access Services

- **News API Swagger**: http://localhost:8000/docs
- **Companies API Swagger**: http://localhost:8001/docs
- **MinIO Console**: http://localhost:9001 (login: newsfeedadmin/newsfeedadmin)
- **Search API Swagger**: http://localhost:8002/docs

### 3. Initialize Database

The Companies API will automatically initialize the database schema on first startup. You can also manually create companies and sources via the API.

### 4. Add Companies and Sources

#### Option A: Seed from JSON configuration

Use the helper script to load `config/companies.json` into PostgreSQL (ensure the database container is running). The command must run from the repository root so the `config/` directory is mounted into the container:

```bash
docker compose run --rm companies-api \
  python -m newsfeeds_demo.seed_companies --config /config/companies.json
```

You can re-run the command safely; it upserts companies and sources without duplicating entries.

#### Option B: Create entries via API

Use the Companies API to create companies and associate news sources:

```bash
# Create a source
curl -X POST "http://localhost:8001/sources" \
  -H "Content-Type: application/json" \
  -d '{"name": "Financial Times"}'

# Create a company with sources
curl -X POST "http://localhost:8001/companies" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Airbus",
    "sources": ["Financial Times", "BBC", "Reuters"]
  }'
```

Or use the Swagger UI at http://localhost:8001/docs for interactive API exploration.

### 5. Enqueue Tasks

#### Option A: Manual CLI Enqueue

Install dependencies locally (optional):

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Enqueue tasks manually:

```bash
python -m newsfeeds_demo.cli "Airbus:Financial Times" "Airbus:BBC"
```

Or use a config file:

```bash
python -m newsfeeds_demo.cli --config config/companies.json
```

#### Option B: Automatic Scheduler

The scheduler service automatically reads all companies and their sources from PostgreSQL every 4 hours and enqueues tasks. You can adjust the interval by setting the `SCHEDULE_INTERVAL_HOURS` environment variable in `docker-compose.yml`.

### 6. Retrieve Articles

Once tasks have been processed and articles stored in MinIO, retrieve them via the News API:

```bash
# List all companies
curl http://localhost:8000/companies

# Get all news articles for a company (from all sources)
curl http://localhost:8000/companies/Airbus

# List sources for a company
curl http://localhost:8000/companies/Airbus/sources

# Get articles for a company and source
curl "http://localhost:8000/articles?company=Airbus&source=Financial Times"
```

Or use the Swagger UI at http://localhost:8000/docs.

## API Documentation

### News API (Port 8000)

- `GET /` - API information
- `GET /health` - Health check
- `GET /companies` - List all companies with articles
- `GET /companies/{company}` - Get all news articles for a company (from all sources)
- `GET /companies/{company}/sources` - List sources for a company
- `GET /articles?company={company}&source={source}` - Get articles for a company/source pair

**Swagger Documentation**: http://localhost:8000/docs

### Companies API (Port 8001)

- `GET /` - API information
- `GET /health` - Health check
- `POST /sources` - Create a news source
- `GET /sources` - List all sources
- `GET /sources/{source_id}` - Get a specific source
- `DELETE /sources/{source_id}` - Delete a source
- `POST /companies` - Create a company with optional sources
- `GET /companies` - List all companies with their sources
- `GET /companies/{company_id}` - Get a specific company
- `PUT /companies/{company_id}` - Update a company
- `DELETE /companies/{company_id}` - Delete a company

**Swagger Documentation**: http://localhost:8001/docs

### Search API (Port 8002)

- `GET /` - API information
- `GET /health` - Health check
- `GET /search?company={company}&source={source}&limit={n}` - Return dummy Brave-style results

**Swagger Documentation**: http://localhost:8002/docs

## Storage Structure

Articles are stored in MinIO with the following structure:

```
newsfeeds/
  ├── Company Name/
  │   ├── source_name_snake_case.json
  │   └── another_source.json
  └── Another Company/
      └── source_name.json
```

Source names are converted to snake_case for filenames, while company names are preserved as-is for folder names.

## Configuration

### Environment Variables

#### Worker

- `CELERY_BROKER_URL`: Redis broker URL (default: `redis://redis:6379/0`)
- `CELERY_BACKEND_URL`: Redis backend URL (default: `redis://redis:6379/1`)
- `S3_ENDPOINT`: Override S3/MinIO endpoint URL (defaults to AWS S3)
- `S3_REGION`: AWS region (default: `us-east-1`)
- `S3_USE_SSL`: Whether to use HTTPS when talking to the endpoint (default: `true`)
- `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`: Credentials for AWS S3 (or MinIO)
- `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY`: Local development credentials (fallback when AWS vars absent)
- `MINIO_ENDPOINT`: Convenience alias for `S3_ENDPOINT` during local development
- `MINIO_BUCKET` / `S3_BUCKET`: Bucket name (default: `newsfeeds`)
- `SEARCH_API_BASE_URL`: Base URL for the dummy Brave Search API (default: `http://search-api:8000` in Docker)
- `REDIS_URL`: Override for Redis connection used when recording dead-lettered jobs (defaults to `CELERY_BROKER_URL`)
- `DEAD_LETTER_KEY`: Redis list key for dead-letter records (default: `newsfeeds:dead_letter`)

#### News API

- `S3_ENDPOINT` / `MINIO_ENDPOINT`: Endpoint URL
- `S3_REGION`: AWS region
- `S3_USE_SSL`: Use HTTPS
- `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` (or MinIO equivalents)
- `MINIO_BUCKET` / `S3_BUCKET`: Bucket name

#### Companies API

- `DATABASE_URL`: PostgreSQL connection string

#### Scheduler

- `DATABASE_URL`: PostgreSQL connection string
- `CELERY_BROKER_URL`: Redis broker URL
- `SCHEDULE_INTERVAL_HOURS`: Interval between scheduler runs in hours (default: `4`)

### Worker Concurrency

The Celery worker is configured with `--concurrency=5` to limit concurrent API calls and avoid overwhelming external services. Adjust this in `docker-compose.yml` if needed.

## Development

### Running Locally (Without Docker)

1. Start Redis, PostgreSQL, and MinIO separately or via Docker Compose
2. Set environment variables accordingly
3. Run services directly:

```bash
# Worker
celery -A newsfeeds_demo.celery_app worker --loglevel=info --concurrency=5

# News API
python -m newsfeeds_demo.news_api

# Companies API
python -m newsfeeds_demo.companies_api

# Scheduler
python -m newsfeeds_demo.scheduler
```

### Code Standards

This codebase follows UK Government coding standards:

- Type hints throughout
- Comprehensive docstrings
- Error handling with appropriate exceptions
- Logging for operational visibility
- Pydantic models for request/response validation
- SQLAlchemy for database operations

## Stopping Services

Press `Ctrl+C` in the terminal running `docker-compose up`, then remove containers:

```bash
docker-compose down
```

To also remove volumes (database and MinIO data):

```bash
docker-compose down -v
```

## Production Considerations

- Replace MinIO with AWS S3 or compatible service
- Use managed PostgreSQL (RDS, etc.)
- Use managed Redis (ElastiCache, etc.)
- Configure proper authentication and authorization
- Set up monitoring and alerting
- Implement proper secret management
- Configure HTTPS/TLS
- Set up backup strategies for database and object storage
- Consider using Celery Beat for more sophisticated scheduling
- Implement rate limiting and retry policies for external APIs
