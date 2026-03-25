"""
schemas.py – Pydantic schémata pro validaci dat

Pydantic schémata (modely) slouží ke dvěma účelům:
  1. Validace vstupních dat (FastAPI je použije automaticky)
  2. Serializace výstupních dat (definují tvar JSON odpovědi)

Jsou ODDĚLENÁ od SQLAlchemy modelů – SQLAlchemy model = tabulka v DB,
Pydantic schéma = tvar dat na API rozhraní.
"""

from datetime import datetime
from typing import List

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Schéma pro odpověď po úspěšném nahrání souboru
# ---------------------------------------------------------------------------
class FileUploadResponse(BaseModel):
    """
    Vráceno po POST /files/upload.
    Obsahuje základní metadata nově nahraného souboru.
    """

    id: str           # UUID souboru (file_id)
    filename: str     # původní název souboru
    size: int         # velikost v bytech

    class Config:
        # orm_mode=True umožňuje vytvořit schéma přímo z SQLAlchemy objektu:
        # FileUploadResponse.from_orm(db_file_object)
        from_attributes = True


# ---------------------------------------------------------------------------
# Schéma pro kompletní metadata souboru (s časem a user_id)
# ---------------------------------------------------------------------------
class FileMetadata(BaseModel):
    """
    Vráceno při výpisu souborů (GET /files).
    Obsahuje všechna metadata uložená v databázi.
    """

    id: str              # UUID souboru
    user_id: str         # vlastník souboru
    filename: str        # název souboru
    size: int            # velikost v bytech
    created_at: datetime # čas nahrání

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Schéma pro seznam souborů
# ---------------------------------------------------------------------------
class FileListResponse(BaseModel):
    """
    Odpověď na GET /files – seznam metadat souborů.
    """

    files: List[FileMetadata]
    total: int  # celkový počet souborů daného uživatele


# ---------------------------------------------------------------------------
# Schéma pro potvrzení smazání
# ---------------------------------------------------------------------------
class DeleteResponse(BaseModel):
    """
    Vráceno po úspěšném DELETE /files/{id}.
    """

    message: str  # textové potvrzení (např. "File deleted successfully")
    id: str       # UUID smazaného souboru
