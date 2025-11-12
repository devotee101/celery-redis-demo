"""Database models and session management for companies and sources."""

from sqlalchemy import Column, Integer, String, Table, ForeignKey, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from typing import Generator
import os

Base = declarative_base()

# Association table for many-to-many relationship between companies and sources
company_source_association = Table(
    "company_source",
    Base.metadata,
    Column("company_id", Integer, ForeignKey("companies.id"), primary_key=True),
    Column("source_id", Integer, ForeignKey("sources.id"), primary_key=True),
)


class Company(Base):
    """Company model representing a company being monitored."""

    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False, index=True)

    sources = relationship(
        "Source", secondary=company_source_association, back_populates="companies"
    )


class Source(Base):
    """News source model representing a news outlet."""

    __tablename__ = "sources"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False, index=True)

    companies = relationship(
        "Company", secondary=company_source_association, back_populates="sources"
    )


def get_database_url() -> str:
    """Get database URL from environment variable."""
    return os.getenv("DATABASE_URL", "postgresql://newsfeeds:newsfeeds@localhost:55432/newsfeeds")


def create_engine_from_env():
    """Create SQLAlchemy engine from environment configuration."""
    return create_engine(get_database_url(), pool_pre_ping=True)


_engine = None
_SessionLocal = None


def get_session_local():
    """Create a session factory for database operations."""
    global _engine, _SessionLocal
    if _engine is None:
        _engine = create_engine_from_env()
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
    return _SessionLocal


def get_db():
    """Dependency for FastAPI to get database session."""
    SessionLocal = get_session_local()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialise database tables."""
    engine = create_engine_from_env()
    Base.metadata.create_all(bind=engine)

