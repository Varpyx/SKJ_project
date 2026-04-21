"""
database.py – Databázové nastavení pro Message Broker

Používáme SQLite (soubor broker.db) pro perzistentní ukládání zpráv.
SQLAlchemy poskytuje ORM vrstvu pro práci s databází.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

DATABASE_URL = "sqlite:///./broker.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


class Base(DeclarativeBase):
    pass


def init_db():
    """Inicializuje databázi - vytvoří všechny tabulky."""
    import models
    Base.metadata.create_all(bind=engine)


def get_db():
    """Generator pro dependency injection v FastAPI."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()