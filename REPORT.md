# SKJ Project - Object Storage Service Report

## Změny provedené v projektu

### 1. Konfigurační soubory
- **.gitignore**: Přidán ignore soubor pro Python, venv, DB, IDE, storage/
- **test_file.txt**: Testovací soubor pro upload (obsah: "Hello World!")

### 2. Databázové modely (models.py)
- **Model Bucket**: Rozšířen o 4 nové sloupce pro billing:
  - `current_storage_bytes` - aktuální velikost uložených dat
  - `ingress_bytes` - kumulativní příchozí přenosy
  - `egress_bytes` - kumulativní odchozí přenosy
  - `internal_transfer_bytes` - interní přenosy v rámci cloudu
- **Model File**: Obsahuje `bucket_id` jako Foreign Key na Bucket

### 3. Migrace (Alembic)
- **Migrace 1** (f9f3495c6657): Vytvoření tabulky buckets a přidání bucket_id do files
- **Migrace 2** (85d9ca8e9e3b): Přidání bandwidth_bytes (následně nahrazeno)
- **Migrace 3** (e4fddf0d8373): Advanced billing - nahrazení bandwidth_bytes 4 novými sloupci

### 4. Pydantic Schémata (schemas.py)
- **BucketCreate**: Validace názvu bucketu (min 3, max 63 znaků, pattern ^[a-z0-9.-]+$)
- **BucketResponse**: Odpověď s id, name, created_at
- **BucketBillingResponse**: Aktualizováno pro 4 billing sloupce

### 5. FastAPI Endpoints (main.py)

| Endpoint | Metoda | Popis |
|----------|--------|-------|
| `/buckets/` | POST | Vytvoření nového bucketu |
| `/buckets/{bucket_id}/objects/` | GET | Výpis souborů v bucketu |
| `/buckets/{bucket_id}/billing/` | GET | Zobrazení billing statistik |
| `/files/upload` | POST | Nahrání souboru do bucketu |
| `/files/{file_id}` | GET | Stažení souboru |
| `/files/{file_id}` | DELETE | Smazání souboru |

### 6. Billing logika
- **Upload**: +current_storage_bytes (velikost souboru), +ingress_bytes (nebo +internal_transfer_bytes pokud X-Internal-Source: true)
- **Download**: +egress_bytes (nebo +internal_transfer_bytes)
- **Delete**: -current_storage_bytes (velikost smazaného souboru)

### 7. HTTP Hlavičky
- `X-User-Id`: Identifikace uživatele (default: anonymous)
- `X-Internal-Source`: Označení interního transferu (value: "true")

### 8. Testovací soubor (restapi.http)
- Připraveny testovací requesty pro:
  - Vytvoření bucketu
  - Upload souboru
  - Zobrazení billing
  - Download souboru
  - Smazání souboru
  - Test interního transferu

## Spuštění projektu
```bash
source skj-venv/bin/activate
uvicorn main:app --reload --port 8000
alembic upgrade head  # pokud je potřeba
```

## API Dokumentace
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc