"""Dummy Search API service simulating Brave Search responses."""

from datetime import datetime, timedelta
import random
from typing import List

from fastapi import FastAPI, Query

app = FastAPI(
    title="Dummy Search API",
    description="Simulates Brave Search API responses for testing.",
    version="1.0.0",
)


def _generate_article(company: str, source: str, index: int) -> dict:
    """Generate a deterministic dummy article entry."""
    published_at = datetime.utcnow() - timedelta(hours=index + 1)
    sentiment = random.choice(["positive", "neutral", "negative"])
    return {
        "title": f"{source} headline about {company} #{index + 1}",
        "url": f"https://{source.lower().replace(' ', '')}.example.com/{company.lower().replace(' ', '-')}/{index + 1}",
        "published_at": published_at.isoformat() + "Z",
        "snippet": (
            f"{source} covers recent developments at {company}, "
            f"highlighting strategic moves and industry impact."
        ),
        "sentiment": sentiment,
    }


@app.get("/", tags=["Health"])
async def root() -> dict:
    """Root endpoint providing service information."""
    return {
        "service": "Dummy Search API",
        "status": "operational",
        "version": "1.0.0",
    }


@app.get("/health", tags=["Health"])
async def health() -> dict:
    """Simple health check endpoint."""
    return {"status": "healthy"}


@app.get("/search", tags=["Search"])
async def search(
    company: str = Query(..., description="Company to search for"),
    source: str = Query(..., description="News source to filter results"),
    limit: int = Query(5, ge=1, le=10, description="Maximum number of results to return"),
) -> dict:
    """Return fictitious search results for a given company and source."""
    articles: List[dict] = [
        _generate_article(company, source, index) for index in range(limit)
    ]

    return {
        "company": company,
        "source": source,
        "fetched_at": datetime.utcnow().isoformat() + "Z",
        "articles": articles,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("newsfeeds_demo.search_api:app", host="0.0.0.0", port=8000, reload=False)

