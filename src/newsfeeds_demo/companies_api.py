"""FastAPI service for managing companies and news sources in PostgreSQL."""

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import List, Optional
import os

from .database import get_db, init_db, Company, Source

app = FastAPI(
    title="Companies Management API",
    description="API for managing companies and their associated news sources",
    version="1.0.0",
)


# Pydantic models for request/response validation
class SourceBase(BaseModel):
    """Base model for source data."""

    name: str = Field(..., description="Name of the news source")


class SourceCreate(SourceBase):
    """Model for creating a new source."""

    pass


class SourceResponse(SourceBase):
    """Model for source response."""

    id: int

    class Config:
        from_attributes = True


class CompanyBase(BaseModel):
    """Base model for company data."""

    name: str = Field(..., description="Name of the company")


class CompanyCreate(CompanyBase):
    """Model for creating a new company."""

    sources: Optional[List[str]] = Field(
        default=[], description="List of source names to associate with the company"
    )


class CompanyUpdate(BaseModel):
    """Model for updating a company."""

    name: Optional[str] = Field(None, description="New name for the company")
    sources: Optional[List[str]] = Field(
        None, description="List of source names to associate with the company"
    )


class CompanyResponse(CompanyBase):
    """Model for company response."""

    id: int
    sources: List[SourceResponse]

    class Config:
        from_attributes = True


@app.on_event("startup")
async def startup_event():
    """Initialise database on startup."""
    init_db()


@app.get("/", tags=["Health"])
async def root():
    """Root endpoint providing API information."""
    return {
        "service": "Companies Management API",
        "version": "1.0.0",
        "status": "operational",
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.post("/sources", response_model=SourceResponse, status_code=status.HTTP_201_CREATED, tags=["Sources"])
async def create_source(source: SourceCreate, db: Session = Depends(get_db)):
    """
    Create a new news source.

    Args:
        source: Source creation data
        db: Database session

    Returns:
        Created source with ID
    """
    # Check if source already exists
    existing = db.query(Source).filter(Source.name == source.name).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Source '{source.name}' already exists",
        )

    db_source = Source(name=source.name)
    db.add(db_source)
    db.commit()
    db.refresh(db_source)
    return db_source


@app.get("/sources", response_model=List[SourceResponse], tags=["Sources"])
async def list_sources(db: Session = Depends(get_db)):
    """
    List all news sources.

    Args:
        db: Database session

    Returns:
        List of all sources
    """
    sources = db.query(Source).all()
    return sources


@app.get("/sources/{source_id}", response_model=SourceResponse, tags=["Sources"])
async def get_source(source_id: int, db: Session = Depends(get_db)):
    """
    Get a specific source by ID.

    Args:
        source_id: ID of the source
        db: Database session

    Returns:
        Source data
    """
    source = db.query(Source).filter(Source.id == source_id).first()
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Source with ID {source_id} not found"
        )
    return source


@app.delete("/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Sources"])
async def delete_source(source_id: int, db: Session = Depends(get_db)):
    """
    Delete a news source.

    Args:
        source_id: ID of the source to delete
        db: Database session
    """
    source = db.query(Source).filter(Source.id == source_id).first()
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Source with ID {source_id} not found"
        )
    db.delete(source)
    db.commit()


@app.post("/companies", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED, tags=["Companies"])
async def create_company(company: CompanyCreate, db: Session = Depends(get_db)):
    """
    Create a new company with optional associated sources.

    Args:
        company: Company creation data
        db: Database session

    Returns:
        Created company with ID and associated sources
    """
    # Check if company already exists
    existing = db.query(Company).filter(Company.name == company.name).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Company '{company.name}' already exists",
        )

    db_company = Company(name=company.name)
    db.add(db_company)

    # Associate sources if provided
    if company.sources:
        for source_name in company.sources:
            source = db.query(Source).filter(Source.name == source_name).first()
            if not source:
                # Create source if it doesn't exist
                source = Source(name=source_name)
                db.add(source)
            db_company.sources.append(source)

    db.commit()
    db.refresh(db_company)
    return db_company


@app.get("/companies", response_model=List[CompanyResponse], tags=["Companies"])
async def list_companies(db: Session = Depends(get_db)):
    """
    List all companies with their associated sources.

    Args:
        db: Database session

    Returns:
        List of all companies with their sources
    """
    companies = db.query(Company).all()
    return companies


@app.get("/companies/{company_id}", response_model=CompanyResponse, tags=["Companies"])
async def get_company(company_id: int, db: Session = Depends(get_db)):
    """
    Get a specific company by ID.

    Args:
        company_id: ID of the company
        db: Database session

    Returns:
        Company data with associated sources
    """
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company with ID {company_id} not found",
        )
    return company


@app.put("/companies/{company_id}", response_model=CompanyResponse, tags=["Companies"])
async def update_company(
    company_id: int, company_update: CompanyUpdate, db: Session = Depends(get_db)
):
    """
    Update a company's name and/or associated sources.

    Args:
        company_id: ID of the company to update
        company_update: Update data
        db: Database session

    Returns:
        Updated company data
    """
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company with ID {company_id} not found",
        )

    if company_update.name is not None:
        # Check if new name conflicts with existing company
        existing = db.query(Company).filter(Company.name == company_update.name).first()
        if existing and existing.id != company_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Company '{company_update.name}' already exists",
            )
        company.name = company_update.name

    if company_update.sources is not None:
        # Replace all sources
        company.sources.clear()
        for source_name in company_update.sources:
            source = db.query(Source).filter(Source.name == source_name).first()
            if not source:
                source = Source(name=source_name)
                db.add(source)
            company.sources.append(source)

    db.commit()
    db.refresh(company)
    return company


@app.delete("/companies/{company_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Companies"])
async def delete_company(company_id: int, db: Session = Depends(get_db)):
    """
    Delete a company.

    Args:
        company_id: ID of the company to delete
        db: Database session
    """
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company with ID {company_id} not found",
        )
    db.delete(company)
    db.commit()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("newsfeeds_demo.companies_api:app", host="0.0.0.0", port=8000, reload=False)

