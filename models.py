"""
models.py – SQLAlchemy ORM modely (= databázové tabulky)

Každá třída reprezentuje jednu tabulku v databázi.
Atributy třídy odpovídají sloupcům tabulky.
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String

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
    id = Column(Integer, primary_key=True, index=True)

    # Veřejný identifikátor souboru – UUID4 jako string (např. "a3f2...")
    # index=True urychlí vyhledávání podle tohoto sloupce
    # unique=True zabraňuje duplicitním záznamům
    file_id = Column(String, unique=True, index=True, nullable=False)

    # ID uživatele – odděluje soubory různých uživatelů
    user_id = Column(String, index=True, nullable=False)

    # Původní název souboru (např. "report.pdf")
    filename = Column(String, nullable=False)

    # Cesta k souboru na disku (např. "storage/user123/abc-uuid")
    path = Column(String, nullable=False)

    # Velikost souboru v bytech
    size = Column(Integer, nullable=False)

    # Čas nahrání – default=datetime.utcnow se zavolá při každém novém záznamu
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        """Textová reprezentace objektu – užitečné při debugování."""
        return (
            f"<File id={self.file_id!r} user={self.user_id!r} "
            f"name={self.filename!r} size={self.size}B>"
        )
