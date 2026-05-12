"""
main.py – Hlavní FastAPI aplikace (Object Storage Service)
Spuštění: uvicorn main:app --reload --port 8001
"""

from typing import List, Optional, Literal
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Depends, FastAPI, Header, HTTPException, UploadFile, File as FastAPIFile, Form
from fastapi.responses import Response
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

import models
import schemas
from database import Base, engine, get_db, SessionLocal

import json
import websockets
from fastapi import BackgroundTasks
from pydantic import BaseModel

import httpx
import msgpack
import uuid
import asyncio
from contextlib import asynccontextmanager

models.Base.metadata.create_all(bind=engine)

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

class ImageProcessRequest(BaseModel):
    operation: Literal["grayscale", "invert", "flip", "brightness", "crop"]
    params: dict = {}

async def send_to_broker(payload: dict):
    try:
        async with websockets.connect("ws://localhost:8000/broker") as websocket:
            message = {
                "action": "publish",
                "topic": "image.jobs",
                "payload": payload
            }
            await websocket.send(json.dumps(message))
    except Exception as e:
        print(f"Chyba při odesílání do Brokera: {e}")

async def haystack_ack_listener():
    """Naslouchá potvrzením z Haystacku, ukládá metadata a řeší odložený billing."""
    while True:
        try:
            async with websockets.connect("ws://127.0.0.1:8000/broker") as ws:
                await ws.send(msgpack.packb({"action": "subscribe", "topic": "storage.ack"}))
                print("✅ S3 Gateway naslouchá na 'storage.ack'")

                while True:
                    msg = await ws.recv()
                    data = msgpack.unpackb(msg)

                    if data.get("action") == "deliver":
                        payload = data.get("payload", {})
                        file_id = payload.get("object_id")
                        message_id = data.get("message_id")

                        db = SessionLocal()
                        try:
                            db_file = db.query(models.File).filter(models.File.file_id == file_id).first()
                            
                            # ÚKOL 2: Zpracujeme pouze soubory, které čekají na upload
                            if db_file and db_file.status != "ready":
                                db_file.volume_id = payload.get("volume_id")
                                db_file.offset = payload.get("offset")
                                if "size" in payload:
                                    db_file.size = payload.get("size")
                                
                                # 1. Eventual Consistency: Soubor je konečně fyzicky zapsán
                                db_file.status = "ready"
                                
                                # 2. Odložený billing: Až teď zaúčtujeme transfer!
                                if db_file.bucket_id:
                                    bucket = db.query(models.Bucket).filter(models.Bucket.id == db_file.bucket_id).first()
                                    if bucket:
                                        bucket.current_storage_bytes += db_file.size
                                        if db_file.is_internal:
                                            bucket.internal_transfer_bytes += db_file.size
                                        else:
                                            bucket.ingress_bytes += db_file.size

                                db.commit()
                                print(f"✅ Metadata uložena pro soubor {file_id}. Status -> ready.")
                        finally:
                            db.close()

                        if message_id:
                            await ws.send(msgpack.packb({"action": "ack", "message_id": message_id}))
        except Exception as e:
            await asyncio.sleep(3)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(haystack_ack_listener())
    yield
    task.cancel()

app = FastAPI(
    title="Object Storage Service",
    lifespan=lifespan,
    version="1.0.0",
)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.post("/buckets/{bucket_id}/objects/{file_id}/process", tags=["process"])
async def process_image(bucket_id: int, file_id: str, request: ImageProcessRequest, background_tasks: BackgroundTasks, x_user_id: Optional[str] = Header(default="anonymous"), db: Session = Depends(get_db)):
    get_file_or_404(file_id, x_user_id, db)
    job_payload = {
        "bucket_id": bucket_id, "file_id": file_id, "user_id": x_user_id,
        "operation": request.operation, "params": request.params
    }
    background_tasks.add_task(send_to_broker, job_payload)
    return {"status": "processing_started", "file_id": file_id}

def get_file_or_404(file_id: str, user_id: str, db: Session) -> models.File:
    file_record = db.query(models.File).filter(models.File.file_id == file_id, models.File.user_id == user_id).first()
    if file_record is None:
        raise HTTPException(status_code=404, detail="Soubor nenalezen nebo k němu nemáte přístup.")
    return file_record

@app.post(
    "/files/upload",
    response_model=schemas.FileUploadResponse,
    status_code=202, # ÚKOL 2: Změněno na 202 Accepted
    tags=["files"],
)
async def upload_file(
    file: UploadFile = FastAPIFile(...),
    bucket_id: int = Form(...),
    x_user_id: Optional[str] = Header(default="anonymous"),
    x_internal_source: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    bucket = db.query(models.Bucket).filter(models.Bucket.id == bucket_id).first()
    if not bucket:
        raise HTTPException(status_code=404, detail="Bucket neexistuje.")
    
    file_content = await file.read()
    if len(file_content) == 0:
        raise HTTPException(status_code=400, detail="Soubor je prázdný.")
    if len(file_content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="Soubor je příliš velký.")

    file_id = str(uuid.uuid4())

    # 1. NEJPRVE ULOŽÍME DO DATABÁZE (Status: uploading)
    db_file = models.File(
        file_id=file_id,
        user_id=x_user_id,
        bucket_id=bucket_id,
        filename=file.filename or "unnamed",
        size=len(file_content),
        volume_id=None,
        offset=None,
        status="uploading",
        is_internal=(x_internal_source == "true")
    )
    db.add(db_file)
    db.commit()
    db.refresh(db_file)

    # 2. AŽ POTOM ODEŠLEME DO BROKERA
    try:
        # PŘIDÁNO: max_size=None (Tohle zabrání padání na větších fotkách)
        async with websockets.connect("ws://localhost:8000/broker", max_size=None) as ws:
            pub_msg = {
                "action": "publish",
                "topic": "storage.write",
                "payload": {
                    "object_id": file_id,
                    "image_bytes": file_content
                }
            }
            await ws.send(msgpack.packb(pub_msg))
    except Exception as e:
        # PŘIDÁNO: Výpis chyby do konzole, ať nejsme slepí!
        print(f"❌ FATAL ERROR PŘI ODESÍLÁNÍ DO BROKERA: {e}")
        raise HTTPException(status_code=500, detail=f"Nelze odeslat data: {e}")

    # 3. Vracíme rovnou odpověď
    return schemas.FileUploadResponse(
    id=db_file.file_id,        # Správně namapujeme file_id (UUID) na id !
    filename=db_file.filename,
    size=db_file.size,
    volume_id=db_file.volume_id,
    offset=db_file.offset,
    status=db_file.status
)

@app.get("/files", response_model=schemas.FileListResponse, tags=["files"])
def list_files(x_user_id: Optional[str] = Header(default="anonymous"), db: Session = Depends(get_db)):
    file_records = db.query(models.File).filter(models.File.user_id == x_user_id, models.File.is_deleted == False).order_by(models.File.created_at.desc()).all()
    files_metadata = [schemas.FileMetadata.model_validate(f) for f in file_records]
    return schemas.FileListResponse(files=files_metadata, total=len(files_metadata))


# ===========================================================================
# ENDPOINT 3 – Stažení souboru
# ===========================================================================
@app.get(
    "/download/{object_id}",
    summary="Stáhni soubor",
    tags=["download"],
    responses={
        200: {"description": "Obsah souboru (binární data)"},
        404: {"description": "Soubor nenalezen"},
    },
)
async def download_file(
    object_id: str,
    x_user_id: Optional[str] = Header(default="anonymous", description="ID uživatele"),
    x_internal_source: Optional[str] = Header(default=None, description="Pokud true, počítá se jako interní transfer"),
    db: Session = Depends(get_db),
):
    """
    **GET /download/{object_id}**

    Stáhne obsah souboru. 
    Respektuje Soft Delete – smazané soubory vrátí chybu 404.

    - Ověří, že soubor existuje a není v koši (is_deleted=False)
    - Vrátí binární obsah souboru s hlavičkou Content-Disposition
    """
    # 1) Ověř existenci záznamu v DB a přístupová práva
    file_record = get_file_or_404(object_id, x_user_id, db)

    if file_record.is_deleted:
        raise HTTPException(status_code=404, detail="Soubor byl smazán.")

    # ÚKOL 3: Čekání na status ready
    if file_record.status != "ready":
        for _ in range(10):
            await asyncio.sleep(0.2)
            db.refresh(file_record)
            if file_record.status == "ready":
                break
        if file_record.status != "ready":
            raise HTTPException(status_code=425, detail="Soubor se ještě zapisuje.")

    async with httpx.AsyncClient() as client:
        haystack_url = f"http://127.0.0.1:8002/volume/{file_record.volume_id}/{file_record.offset}/{file_record.size}"
        resp = await client.get(haystack_url)
        if resp.status_code != 200:
            raise HTTPException(status_code=500, detail="Chyba při čtení z Haystacku.")
        file_content = resp.content

    if file_record.bucket_id:
        bucket = db.query(models.Bucket).filter(models.Bucket.id == file_record.bucket_id).first()
        if bucket:
            if x_internal_source == "true":
                bucket.internal_transfer_bytes += file_record.size
            else:
                bucket.egress_bytes += file_record.size
            db.commit()
            
    # 5) Vrať soubor jako HTTP response
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
    "/download/{object_id}",
    response_model=schemas.DeleteResponse,
    summary="Smaž soubor (Soft Delete)",
    tags=["download"],
)
def delete_file(
    object_id: str,
    x_user_id: Optional[str] = Header(default="anonymous", description="ID uživatele"),
    db: Session = Depends(get_db),
):
    """
    **DELETE /download/{object_id}**

    Provádí 'Soft Delete' souboru. Soubor zůstává na disku i v DB, 
    ale je označen jako smazaný a nebude se zobrazovat v běžných výpisech.

    - Nastaví příznak is_deleted na True
    - Sníží zaplněné místo v bucketu (volitelné, záleží na logice aplikace)
    - Fyzický soubor na disku ZŮSTÁVÁ pro možnost obnovy
    """
    # 1) Ověř existenci záznamu v DB a přístupová práva
    file_record = get_file_or_404(object_id, x_user_id, db)

    # Kontrola, zda už soubor není smazaný (abychom neodečítali velikost vícekrát)
    if file_record.is_deleted:
        return schemas.DeleteResponse(message="Již smazáno.", id=file_id)

    file_record.is_deleted = True
    if file_record.bucket_id:
        bucket = db.query(models.Bucket).filter(models.Bucket.id == file_record.bucket_id).first()
        if bucket:
            bucket.current_storage_bytes -= file_record.size
    db.commit()
    return schemas.DeleteResponse(message="Soft delete proveden.", id=file_id)

@app.post("/buckets/", response_model=schemas.BucketResponse, status_code=201, tags=["buckets"])
def create_bucket(bucket_in: schemas.BucketCreate, db: Session = Depends(get_db)):
    db_bucket = models.Bucket(name=bucket_in.name)
    db.add(db_bucket)
    try:
        db.commit()
        db.refresh(db_bucket)
        return db_bucket
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Bucket již existuje.")

@app.get("/buckets/{bucket_id}/objects/", response_model=schemas.FileListResponse, tags=["buckets"])
def list_bucket_objects(bucket_id: int, db: Session = Depends(get_db)):
    bucket = db.query(models.Bucket).filter(models.Bucket.id == bucket_id).first()
    if not bucket:
        raise HTTPException(status_code=404, detail="Bucket nebyl nalezen.")
    file_records = db.query(models.File).filter(models.File.bucket_id == bucket_id, models.File.is_deleted == False).order_by(models.File.created_at.desc()).all()
    files_metadata = [schemas.FileMetadata.model_validate(f) for f in file_records]
    return schemas.FileListResponse(files=files_metadata, total=len(files_metadata))

@app.get("/buckets/{bucket_id}/billing/", response_model=schemas.BucketBillingResponse)
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


# ===========================================================================
# ADMIN ENDPOINTY — pro kompakci volume skriptem compact.py
# ===========================================================================

@app.get(
    "/admin/volume/{volume_id}/objects",
    response_model=List[schemas.VolumeObjectInfo],
    tags=["admin"],
)
def get_volume_objects(volume_id: int, db: Session = Depends(get_db)):
    """Vrátí všechny nesmazané soubory v daném svazku, seřazené podle offsetu."""
    files = (
        db.query(models.File)
        .filter(
            models.File.volume_id == volume_id,
            models.File.is_deleted == False,
        )
        .order_by(models.File.offset)
        .all()
    )
    return files


@app.put("/admin/objects/{file_id}/relocate", tags=["admin"])
def relocate_object(file_id: str, new_offset: int, db: Session = Depends(get_db)):
    """Aktualizuje offset souboru po kompakci."""
    file_record = db.query(models.File).filter(models.File.file_id == file_id).first()
    if not file_record:
        raise HTTPException(status_code=404, detail="Soubor nenalezen.")
    file_record.offset = new_offset
    db.commit()
    return {"status": "ok"}