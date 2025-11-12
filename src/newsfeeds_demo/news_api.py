"""FastAPI service for reading news articles from MinIO storage."""

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from typing import Optional
import os
import logging

from .storage import (
    get_article_json,
    get_articles_for_company,
    list_companies,
    list_sources_for_company,
)
from .init_minio import init_bucket

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="News Articles API",
    description="API for retrieving news articles stored in MinIO",
    version="1.0.0",
)


@app.on_event("startup")
async def startup_event():
    """Initialize MinIO bucket on startup."""
    try:
        init_bucket()
    except Exception as e:
        logger.warning(f"Failed to initialize MinIO bucket on startup: {e}")


@app.get("/", tags=["Health"])
async def root():
    """Root endpoint providing API information."""
    return {
        "service": "News Articles API",
        "version": "1.0.0",
        "status": "operational",
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/companies", tags=["Companies"])
async def list_all_companies():
    """
    List all companies that have news articles stored.

    Returns:
        List of company names
    """
    bucket_name = os.getenv("MINIO_BUCKET", "newsfeeds")
    try:
        companies = list_companies(bucket_name)
        return {"companies": companies, "count": len(companies)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list companies: {str(e)}")


@app.get("/companies/{company}", tags=["Companies"])
async def get_company_news(
    company: str,
    limit_per_source: Optional[int] = Query(
        None,
        ge=1,
        le=100,
        description="Optional limit applied to the number of articles returned per source",
    ),
):
    """
    Retrieve all news articles for a company across every available source.

    Args:
        company: Name of the company
        limit_per_source: Optional limit for the number of articles per source

    Returns:
        Aggregated article data across all sources
    """
    bucket_name = os.getenv("MINIO_BUCKET", "newsfeeds")
    try:
        articles = get_articles_for_company(company, bucket_name)
        if not articles:
            raise HTTPException(
                status_code=404,
                detail=f"No articles found for company '{company}'",
            )

        total_articles_available = sum(
            len(entry.get("articles", []))
            for entry in articles
            if isinstance(entry.get("articles"), list)
        )

        if limit_per_source is not None:
            trimmed_articles = []
            for entry in articles:
                entry_copy = dict(entry)
                if isinstance(entry_copy.get("articles"), list):
                    entry_copy["articles"] = entry_copy["articles"][:limit_per_source]
                trimmed_articles.append(entry_copy)
        else:
            trimmed_articles = articles

        sources = sorted(
            {entry.get("source") for entry in articles if entry.get("source")}
        )

        return {
            "company": company,
            "source_count": len(sources),
            "sources": sources,
            "total_articles_available": total_articles_available,
            "items": trimmed_articles,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve articles for company: {str(e)}",
        )


@app.get("/companies/{company}/sources", tags=["Companies"])
async def list_company_sources(company: str):
    """
    List all news sources available for a specific company.

    Args:
        company: Name of the company

    Returns:
        List of source names for the company
    """
    bucket_name = os.getenv("MINIO_BUCKET", "newsfeeds")
    try:
        sources = list_sources_for_company(company, bucket_name)
        return {"company": company, "sources": sources, "count": len(sources)}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to list sources for company: {str(e)}"
        )


@app.get("/articles", tags=["Articles"])
async def get_article(
    company: str = Query(..., description="Name of the company"),
    source: str = Query(..., description="Name of the news source"),
):
    """
    Retrieve news articles for a specific company and source.

    Args:
        company: Name of the company
        source: Name of the news source

    Returns:
        Article data including list of articles, metadata, and fetch information
    """
    bucket_name = os.getenv("MINIO_BUCKET", "newsfeeds")
    try:
        article_data = get_article_json(company, source, bucket_name)
        if article_data is None:
            raise HTTPException(
                status_code=404,
                detail=f"No articles found for company '{company}' and source '{source}'",
            )
        return article_data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve article: {str(e)}"
        )




if __name__ == "__main__":
    import uvicorn

    uvicorn.run("newsfeeds_demo.news_api:app", host="0.0.0.0", port=8000, reload=False)

