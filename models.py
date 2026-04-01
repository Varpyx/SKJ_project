"""
models.py – SQLAlchemy ORM modely (= databázové tabulky)

Každá třída reprezentuje jednu tabulku v databázi.
Atributy třídy odpovídají sloupcům tabulky.

Používáme moderní SQLAlchemy 2.0 styl s Mapped[] a mapped_column():
  - Mapped[str]        → sloupec NOT NULL (nullable=False automaticky)
  - Mapped[str | None] → sloupec povolující NULL (nullable=True automaticky)
  - Datový typ (String, Integer...) SQLAlchemy odvodí z Python anotace
"""

from datetime import datetime

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class File(Base):
    """
    Tabulka 'files' – ukládá metadata o nahraných souborech.

    Sloupce:
    --------
    id          – primární klíč (autoincrement integer)
    file_id     – unikátní UUID souboru (náš veřejný identifikátor)
    user_id     – identifikátor uživatele (v této verzi předáváme jako header)
    filename    – původní název souboru při nahrání
    path        – absolutní/relativní cesta k souboru na disku
    size        – velikost souboru v bytech
    created_at  – časová značka nahrání (automaticky nastavená)
    """

    __tablename__ = "files"  # název tabulky v SQLite

    # Primární klíč – interní ID (autoincrement)
    # int → SQLAlchemy automaticky použije Integer; primary_key implikuje NOT NULL
    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Veřejný identifikátor souboru – UUID4 jako string (např. "a3f2...")
    # Mapped[str] → nullable=False automaticky (není potřeba psát explicitně)
    # String bez délky = VARCHAR bez limitu (vhodné pro SQLite; u PostgreSQL zvažte délku)
    file_id: Mapped[str] = mapped_column(String, unique=True, index=True)

    # ID uživatele – odděluje soubory různých uživatelů
    user_id: Mapped[str] = mapped_column(String, index=True)

    # Původní název souboru (např. "report.pdf")
    filename: Mapped[str] = mapped_column(String)

    # Cesta k souboru na disku (např. "storage/user123/abc-uuid")
    path: Mapped[str] = mapped_column(String)

    # Velikost souboru v bytech
    # int → SQLAlchemy automaticky použije Integer
    size: Mapped[int] = mapped_column()

    # Čas nahrání – default=datetime.utcnow se zavolá při každém novém záznamu
    # Mapped[datetime] → SQLAlchemy automaticky použije DateTime
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    def __repr__(self) -> str:
        """Textová reprezentace objektu – užitečné při debugování."""
        return (
            f"<File id={self.file_id!r} user={self.user_id!r} "
            f"name={self.filename!r} size={self.size}B>"
        )