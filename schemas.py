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

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Schéma pro odpověď po úspěšném nahrání souboru
# ---------------------------------------------------------------------------
class FileUploadResponse(BaseModel):
    """
    Vráceno po POST /files/upload.
    Obsahuje základní metadata nově nahraného souboru.
    """

    # ... znamená povinné pole – server musí vždy vrátit ID souboru
    id: str = Field(..., description="UUID souboru")

    # ... znamená povinné pole – název souboru musí být vždy znám
    filename: str = Field(..., description="Původní název souboru")

    # gt=0 (greater than) – velikost musí být kladné číslo, prázdný soubor nedává smysl
    size: int = Field(..., description="Velikost souboru v bytech", gt=0)

    # ... znamená povinné pole – cesta musí být vždy uložena pro pozdější přístup
    path: str = Field(..., description="Cesta k souboru na disku")

    # from_attributes=True umožňuje vytvořit schéma přímo z SQLAlchemy objektu:
    # FileUploadResponse.model_validate(db_file_object)
    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Schéma pro kompletní metadata souboru (s časem a user_id)
# ---------------------------------------------------------------------------
class FileMetadata(BaseModel):
    """
    Vráceno při výpisu souborů (GET /files).
    Obsahuje všechna metadata uložená v databázi.
    """

    # ... znamená povinné pole – UUID jednoznačně identifikuje soubor
    id: str = Field(..., description="UUID souboru")

    # ... znamená povinné pole – každý soubor musí mít vlastníka
    user_id: str = Field(..., description="Vlastník souboru")

    # ... znamená povinné pole – název souboru musí být vždy znám
    filename: str = Field(..., description="Název souboru")

    # ... znamená povinné pole – cesta nutná pro stažení souboru
    path: str = Field(..., description="Cesta k souboru na disku")

    # gt=0 (greater than) – velikost musí být kladné číslo, prázdný soubor nedává smysl
    size: int = Field(..., description="Velikost v bytech", gt=0)

    # ... znamená povinné pole – čas nahrání je vždy nastaven databází
    created_at: datetime = Field(..., description="Čas nahrání")

    # from_attributes=True umožňuje vytvořit schéma přímo z SQLAlchemy objektu:
    # FileMetadata.model_validate(db_file_object)
    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Schéma pro seznam souborů
# ---------------------------------------------------------------------------
class FileListResponse(BaseModel):
    """
    Odpověď na GET /files – seznam metadat souborů.
    """

    # ... znamená povinné pole – seznam musí být vždy přítomen (i když prázdný)
    files: List[FileMetadata] = Field(..., description="Seznam souborů uživatele")

    # ge=0 (greater or equal) – počet souborů může být 0 (uživatel nic nenahrál)
    # na rozdíl od size zde nula smysl dává
    total: int = Field(..., description="Celkový počet souborů", ge=0)


# ---------------------------------------------------------------------------
# Schéma pro potvrzení smazání
# ---------------------------------------------------------------------------
class DeleteResponse(BaseModel):
    """
    Vráceno po úspěšném DELETE /files/{id}.
    """

    # ... znamená povinné pole – textové potvrzení musí být vždy vráceno
    message: str = Field(..., description="Potvrzení smazání")

    # ... znamená povinné pole – klient musí vědět, které ID bylo smazáno
    id: str = Field(..., description="UUID smazaného souboru")