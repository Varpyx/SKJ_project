"""
database.py – Nastavení databáze pomocí SQLAlchemy

Používáme SQLite (soubor storage.db) jako úložiště metadat.
SQLAlchemy nám poskytuje ORM vrstvu – místo psaní SQL
pracujeme s Python objekty (třídami).
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# ---------------------------------------------------------------------------
# Připojovací řetězec (connection string)
# ---------------------------------------------------------------------------
# "sqlite:///./storage.db" znamená:
#   - databázový engine: SQLite
#   - soubor: storage.db ve stejném adresáři jako aplikace
# Pro produkci bychom nahradili PostgreSQL/MySQL URL.
DATABASE_URL = "sqlite:///./storage.db"

# ---------------------------------------------------------------------------
# Engine – jádro připojení k databázi
# ---------------------------------------------------------------------------
# check_same_thread=False je nutné pro SQLite + FastAPI (asynchronní přístupy
# z různých vláken; u PostgreSQL toto nastavení nepotřebujeme).
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=True,  
)

# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------
# Každý HTTP request dostane vlastní session (=transakci).
# autocommit=False → změny musíme explicitně potvrdit (session.commit()).
# autoflush=False  → ORM nevypisuje SQL automaticky před každým dotazem.
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

# ---------------------------------------------------------------------------
# Deklarativní základní třída pro modely (SQLAlchemy 2.0 styl)
# ---------------------------------------------------------------------------
# Nový způsob: místo declarative_base() dědíme z DeclarativeBase.
# Výhoda: plná podpora typed mapped_column a lepší integrace s type-checkery.
class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Dependency pro FastAPI – poskytuje DB session endpointům
# ---------------------------------------------------------------------------
def get_db():
    """
    Generator, který FastAPI používá jako Dependency Injection.

    Použití v endpointu:
        def my_endpoint(db: Session = Depends(get_db)):
            ...

    Zaručuje, že session je vždy správně uzavřena, i když nastane výjimka.
    """
    db = SessionLocal()
    try:
        yield db          # předá session do endpointu
    finally:
        db.close()        # vždy zavře session po dokončení requestu