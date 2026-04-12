"""
main.py – Hlavní FastAPI aplikace (Object Storage Service)

Spuštění:
    uvicorn main:app --reload --port 8000

Dokumentace API (automaticky generovaná FastAPI):
    http://localhost:8000/docs   ← Swagger UI
    http://localhost:8000/redoc  ← ReDoc

Architektura:
    HTTP Request
        ↓
    FastAPI endpoint (main.py)
        ↓
    SQLAlchemy (database.py + models.py)  ← metadata
        ↓
    storage.py  ← fyzické soubory na disku
"""

from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, UploadFile, File as FastAPIFile, Form
from fastapi.responses import Response
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

import models
import schemas
import storage
from database import Base, engine, get_db

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB v bytech
# ---------------------------------------------------------------------------
# Inicializace databáze
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# FastAPI aplikace
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Object Storage Service",
    description=(
        "Jednoduchá object storage služba inspirovaná Amazon S3.\n\n"
        "Umožňuje nahrávání, stahování, výpis a mazání souborů.\n"
        "Každý uživatel má vlastní izolovaný prostor v úložišti."
    ),
    version="1.0.0",
)


# ---------------------------------------------------------------------------
# Pomocná funkce – ověření přístupu k souboru
# ---------------------------------------------------------------------------
def get_file_or_404(file_id: str, user_id: str, db: Session) -> models.File:
    """
    Načte soubor z databáze a ověří, že patří danému uživateli.

    Parametry:
        file_id – UUID souboru (z URL)
        user_id – ID uživatele (z HTTP hlavičky X-User-Id)
        db      – databázová session

    Vrátí:
        models.File objekt z databáze

    Vyhodí:
        HTTPException 404 – soubor neexistuje nebo nepatří uživateli
    """
    # Dotaz do DB: najdi soubor s daným file_id a user_id
    file_record = (
        db.query(models.File)
        .filter(
            models.File.file_id == file_id,
            models.File.user_id == user_id,
        )
        .first()
    )

    if file_record is None:
        raise HTTPException(
            status_code=404,
            detail=f"Soubor s ID '{file_id}' nebyl nalezen nebo k němu nemáte přístup.",
        )

    return file_record


# ===========================================================================
# ENDPOINT 1 – Nahrání souboru
# ===========================================================================
@app.post(
    "/files/upload",
    response_model=schemas.FileUploadResponse,
    status_code=201,
    summary="Nahraj soubor",
    tags=["files"],
)
async def upload_file(
    file: UploadFile = FastAPIFile(..., description="Soubor k nahrání (multipart/form-data)"),
    bucket_id: int = Form(..., description="ID bucketu, do kterého se má soubor nahrát"),
    x_user_id: Optional[str] = Header(default="anonymous", description="ID uživatele"),
    x_internal_source: Optional[str] = Header(default=None, description="Pokud true, počítá se jako interní transfer"),
    db: Session = Depends(get_db),
):
    """
    **POST /files/upload**

    Nahraje soubor na server a uloží jeho metadata do databáze.

    - Soubor se pošle jako `multipart/form-data` (pole `file`)
    - Uživatel se identifikuje hlavičkou `X-User-Id`
    - Vrátí JSON s ID, názvem a velikostí souboru

    Postup zpracování:
    1. FastAPI automaticky parsuje multipart request a předá `UploadFile` objekt
    2. Přečteme binární obsah souboru
    3. Vygenerujeme UUID identifikátor
    4. Uložíme soubor na disk (do storage/<user_id>/<file_id>)
    5. Uložíme metadata do SQLite databáze
    6. Vrátíme odpověď s metadaty
    """
    # 0) KONTROLA BUCKETU - Musíme ověřit, jestli cílový bucket vůbec existuje
    bucket = db.query(models.Bucket).filter(models.Bucket.id == bucket_id).first()
    if not bucket:
        raise HTTPException(status_code=404, detail=f"Cílový bucket s ID {bucket_id} neexistuje.")
    # 1) Přečti celý obsah souboru do paměti (jako bytes)
    # Pro velmi velké soubory bychom četli po částech (streaming), ale
    # pro účely tohoto projektu je přečtení celého souboru v pořádku.
    file_content = await file.read()

    if len(file_content) == 0:
        raise HTTPException(status_code=400, detail="Nahraný soubor je prázdný.")

    # 2) Vygeneruj unikátní ID pro tento soubor
    file_id = storage.generate_file_id()

    # 2. KONTROLA: Není soubor příliš velký?
    if len(file_content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,  # 413 Payload Too Large je správný HTTP kód pro tuto chybu
            detail=f"Soubor je příliš velký. Maximální povolená velikost je {MAX_FILE_SIZE / 1024 / 1024} MB."
        )

    # 3) Ulož soubor fyzicky na disk (asynchronně)
    file_path, file_size = await storage.save_file(
        user_id=x_user_id,
        file_id=file_id,
        file_content=file_content,
    )

    # 4) Vytvoř záznam metadat v databázi
    db_file = models.File(
        file_id=file_id,
        user_id=x_user_id,
        bucket_id=bucket_id,  # <-- Propojení souboru s bucketem!
        filename=file.filename or "unnamed",
        path=file_path,
        size=file_size,
    )
    db.add(db_file)      # přidej objekt do session (zatím jen v paměti)
    bucket.current_storage_bytes += file_size
    if x_internal_source == "true":
        bucket.internal_transfer_bytes += file_size
    else:
        bucket.ingress_bytes += file_size
    db.commit()          # zapiš do databáze (trvalé uložení)
    db.refresh(db_file)  # načti zpět aktualizovaná data (např. created_at)

    # 5) Vrať odpověď – FastAPI automaticky serializuje do JSON
    return schemas.FileUploadResponse(
        id=db_file.file_id,
        filename=db_file.filename,
        size=db_file.size,
        path = db_file.path
    )


# ===========================================================================
# ENDPOINT 2 – Výpis souborů uživatele
# ===========================================================================
@app.get(
    "/files",
    response_model=schemas.FileListResponse,
    summary="Zobraz seznam souborů",
    tags=["files"],
)
def list_files(
    x_user_id: Optional[str] = Header(default="anonymous", description="ID uživatele"),
    db: Session = Depends(get_db),
):
    """
    **GET /files**

    Vrátí seznam všech souborů přihlášeného uživatele s jejich metadaty.

    - Uživatel vidí POUZE své vlastní soubory (filtrování podle X-User-Id)
    - Soubory jsou seřazeny od nejnovějšího
    """
    # Dotaz: všechny záznamy daného uživatele, seřazené sestupně podle created_at
    file_records = (
        db.query(models.File)
        .filter(models.File.user_id == x_user_id)
        .order_by(models.File.created_at.desc())
        .all()
    )

    # Převeď SQLAlchemy objekty na Pydantic schémata
    files_metadata = [
        schemas.FileMetadata(
            id=f.file_id,
            user_id=f.user_id,
            filename=f.filename,
            size=f.size,
            path = f.path,
            created_at=f.created_at,
        )
        for f in file_records
    ]

    return schemas.FileListResponse(
        files=files_metadata,
        total=len(files_metadata),
    )


# ===========================================================================
# ENDPOINT 3 – Stažení souboru
# ===========================================================================
@app.get(
    "/files/{file_id}",
    summary="Stáhni soubor",
    tags=["files"],
    responses={
        200: {"description": "Obsah souboru (binární data)"},
        404: {"description": "Soubor nenalezen"},
    },
)
async def download_file(
    file_id: str,
    x_user_id: Optional[str] = Header(default="anonymous", description="ID uživatele"),
    x_internal_source: Optional[str] = Header(default=None, description="Pokud true, počítá se jako interní transfer"),
    db: Session = Depends(get_db),
):
    """
    **GET /files/{file_id}**

    Stáhne obsah souboru.

    - Ověří, že soubor existuje a patří danému uživateli
    - Vrátí binární obsah souboru s hlavičkou Content-Disposition
      (prohlížeč ho nabídne ke stažení pod původním názvem)

    Vrátí:
        Response s binárním obsahem souboru a správnými hlavičkami.
    """
    # 1) Ověř existenci záznamu v DB a přístupová práva
    file_record = get_file_or_404(file_id, x_user_id, db)

    # 2) Načti soubor z disku
    try:
        file_content = await storage.read_file(file_record.path)
    except FileNotFoundError:
        # Soubor je v DB, ale chybí na disku – nekonzistentní stav
        raise HTTPException(
            status_code=500,
            detail="Soubor je evidován v databázi, ale fyzický soubor chybí na disku.",
        )

    # 3) Vrať soubor jako HTTP response
    # Content-Disposition: attachment → prohlížeč nabídne stažení (ne zobrazení)
    # filename= → navrhovaný název souboru při stažení
    #
    if file_record.bucket_id:
        bucket = db.query(models.Bucket).filter(models.Bucket.id == file_record.bucket_id).first()
        if bucket:
            if x_internal_source == "true":
                bucket.internal_transfer_bytes += file_record.size
            else:
                bucket.egress_bytes += file_record.size
            db.commit()
    # 
    return Response(
        content=file_content,
        media_type="application/octet-stream",  # generický binární typ
        headers={
            "Content-Disposition": f'attachment; filename="{file_record.filename}"',
            "X-File-Id": file_record.file_id,
            "X-File-Size": str(file_record.size),
        },
    )


# ===========================================================================
# ENDPOINT 4 – Smazání souboru
# ===========================================================================
@app.delete(
    "/files/{file_id}",
    response_model=schemas.DeleteResponse,
    summary="Smaž soubor",
    tags=["files"],
)
def delete_file(
    file_id: str,
    x_user_id: Optional[str] = Header(default="anonymous", description="ID uživatele"),
    db: Session = Depends(get_db),
):
    """
    **DELETE /files/{file_id}**

    Smaže soubor ze storage a odstraní jeho metadata z databáze.

    - Nejprve smaže fyzický soubor z disku
    - Poté smaže záznam z databáze
    - Obě operace jsou v tomto pořadí záměrné:
      pokud selže smazání z DB, fyzický soubor je pryč,
      ale máme o tom záznam (lépe než opak – zombie soubory bez záznamu)

    Vrátí:
        Potvrzení smazání s ID souboru.
    """
    # 1) Ověř existenci záznamu v DB a přístupová práva
    file_record = get_file_or_404(file_id, x_user_id, db)

    # 2) Smaž fyzický soubor z disku
    deleted_from_disk = storage.delete_file_from_disk(file_record.path)

    if not deleted_from_disk:
        # Soubor na disku nebyl – logujeme varování, ale pokračujeme
        # (chceme alespoň vyčistit DB záznam)
        print(f"VAROVÁNÍ: Soubor {file_record.path} nebyl nalezen na disku.")

    # 3) Sníž storage_bytes v bucketu
    if file_record.bucket_id:
        bucket = db.query(models.Bucket).filter(models.Bucket.id == file_record.bucket_id).first()
        if bucket:
            bucket.current_storage_bytes -= file_record.size

    # 4) Odstraň záznam z databáze
    db.delete(file_record)
    db.commit()

    return schemas.DeleteResponse(
        message="Soubor byl úspěšně smazán.",
        id=file_id,
    )


# ===========================================================================
# Health check endpoint
# ===========================================================================
@app.get("/health", tags=["system"], summary="Stav služby")
def health_check():
    """
    Jednoduchý endpoint pro ověření, že služba běží.
    Používá se pro monitoring a load balancery.
    """
    return {"status": "ok", "service": "object-storage"}


# ===========================================================================
# ENDPOINTY PRO BUCKETY
# ===========================================================================

@app.post(
    "/buckets/",
    response_model=schemas.BucketResponse,
    status_code=201,
    summary="Vytvoř nový bucket",
    tags=["buckets"],
)
def create_bucket(
        bucket_in: schemas.BucketCreate,
        db: Session = Depends(get_db)
):
    """Vytvoří nový bucket. Název musí být unikátní."""
    db_bucket = models.Bucket(name=bucket_in.name)
    db.add(db_bucket)

    try:
        db.commit()
        db.refresh(db_bucket)
        return db_bucket
    except IntegrityError:
        # Odchycení chyby, pokud by unikátní název (unique=True) už existoval
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"Bucket s názvem '{bucket_in.name}' již existuje."
        )

@app.get(
    "/buckets/{bucket_id}/objects/",
    response_model=schemas.FileListResponse,
    summary="Vypiš objekty v bucketu",
    tags=["buckets"],
)
def list_bucket_objects(
        bucket_id: int,
        db: Session = Depends(get_db)
):
    """Vrátí seznam všech souborů, které patří do daného bucketu."""
    # 1. Nejprve ověříme, zda bucket vůbec existuje
    bucket = db.query(models.Bucket).filter(models.Bucket.id == bucket_id).first()
    if not bucket:
        raise HTTPException(status_code=404, detail="Bucket nebyl nalezen.")

    # 2. Vytáhneme všechny soubory spojené s tímto bucketem
    file_records = (
        db.query(models.File)
        .filter(models.File.bucket_id == bucket_id)
        .order_by(models.File.created_at.desc())
        .all()
    )

    # Převedeme na Pydantic schémata pro odpověď (využijeme tvůj existující FileMetadata)
    files_metadata = [
        schemas.FileMetadata(
            id=f.file_id,
            user_id=f.user_id,
            filename=f.filename,
            size=f.size,
            path=f.path,
            created_at=f.created_at,
        )
        for f in file_records
    ]

    return schemas.FileListResponse(
        files=files_metadata,
        total=len(files_metadata),
    )

# pridan billing bucket
@app.get("/buckets/{bucket_id}/billing/",
          response_model=schemas.BucketBillingResponse)
def get_bucket_billing(bucket_id: int, db: Session = Depends(get_db)):
    bucket = db.query(models.Bucket).filter(models.Bucket.id == bucket_id).first()
    if not bucket:
        raise HTTPException(status_code=404, detail="Bucket nebyl nalezen.")
    return schemas.BucketBillingResponse(
        bucket_id=bucket.id,
        current_storage_bytes=bucket.current_storage_bytes,
        ingress_bytes=bucket.ingress_bytes,
        egress_bytes=bucket.egress_bytes,
        internal_transfer_bytes=bucket.internal_transfer_bytes
    )