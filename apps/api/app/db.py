import os
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


def _get_url() -> str:
    url = os.environ.get("DATABASE_URL", "postgresql+psycopg://localhost/hill_jobs")
    # Railway provides postgresql:// but psycopg v3 needs postgresql+psycopg://
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def get_engine():
    return create_engine(_get_url())


def get_session():
    return sessionmaker(bind=get_engine())


def get_db() -> Generator[Session, None, None]:
    SessionLocal = get_session()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class Base(DeclarativeBase):
    pass
