# Object Storage Service

Jednoduchá object storage služba inspirovaná Amazon S3, postavená na **FastAPI** + **SQLAlchemy** + **SQLite**.

---

## Rychlý start

```bash
# 1. Nainstaluj závislosti
pip install -r requirements.txt

# 2. Spusť server
uvicorn main:app --reload --port 8000

# 3. Otevři dokumentaci
# http://localhost:8000/docs

# 4. Testování pomocí HTTP souboru (volitelně)

Místo curl nebo /docs můžeš použít soubor `test.http`:

- **VS Code:** Nainstaluj rozšíření "REST Client" (humao.rest-client)
- **JetBrains:** Použij vestavěný HTTP Client

Otevři `test.http` v editoru a klikni na "Send Request" nad každou sekcí.
```

---

## Struktura projektu

```
object_storage/
├── main.py          ← FastAPI aplikace, všechny HTTP endpointy
├── database.py      ← Připojení k SQLite, SessionLocal, get_db()
├── models.py        ← SQLAlchemy ORM model (tabulka 'files')
├── schemas.py       ← Pydantic schémata (validace + serializace JSON)
├── storage.py       ← Logika práce se souborovým systémem (disk)
├── requirements.txt ← Závislosti projektu
│
├── storage.db       ← SQLite databáze (vytvoří se automaticky)
└── storage/         ← Fyzické soubory (vytvoří se automaticky)
    ├── alice/
    │   └── 550e8400-e29b-41d4-a716-446655440000
    └── bob/
        └── 3f2a1b4c-d5e6-47f8-9a0b-1c2d3e4f5a6b
```

---

## API Endpointy

### POST /files/upload – Nahrání souboru

```bash
curl -X POST http://localhost:8000/files/upload \
  -H "X-User-Id: alice" \
  -F "file=@dokument.pdf"
```

**Odpověď:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "filename": "dokument.pdf",
  "size": 102400
}
```

---

### GET /files – Seznam souborů

```bash
curl http://localhost:8000/files \
  -H "X-User-Id: alice"
```

**Odpověď:**
```json
{
  "files": [
    {
      "id": "550e8400-...",
      "user_id": "alice",
      "filename": "dokument.pdf",
      "size": 102400,
      "created_at": "2024-10-15T10:30:00"
    }
  ],
  "total": 1
}
```

---

### GET /files/{id} – Stažení souboru

```bash
curl http://localhost:8000/files/550e8400-e29b-41d4-a716-446655440000 \
  -H "X-User-Id: alice" \
  -o stazeny_dokument.pdf
```

Vrátí binární obsah souboru s hlavičkou `Content-Disposition: attachment`.

---

### DELETE /files/{id} – Smazání souboru

```bash
curl -X DELETE http://localhost:8000/files/550e8400-e29b-41d4-a716-446655440000 \
  -H "X-User-Id: alice"
```

**Odpověď:**
```json
{
  "message": "Soubor byl úspěšně smazán.",
  "id": "550e8400-e29b-41d4-a716-446655440000"
}
```

---

## Jak funguje autentizace

Tato verze používá zjednodušenou "autentizaci" – uživatel předá své ID v HTTP hlavičce `X-User-Id`. V produkčním systému by tato hlavička byla nahrazena **JWT tokenem** nebo **OAuth2**.

Každý endpoint ověří, že soubor patří danému uživateli:
- Uživatel `alice` nemůže stáhnout ani smazat soubory uživatele `bob`
- Vrátí se `404 Not Found` (neunikáme informaci, že soubor existuje)

---

## Architektura – tok dat

```
HTTP Request (multipart/form-data)
        │
        ▼
   FastAPI endpoint (main.py)
        │
        ├──► storage.py ──► disk (storage/<user>/<uuid>)
        │
        └──► SQLAlchemy (database.py)
                │
                ▼
           SQLite (storage.db)
           ┌─────────────────────────────────────────┐
           │ files                                   │
           │ id | file_id | user_id | filename | ... │
           └─────────────────────────────────────────┘
```

---

## Technologie

| Technologie | Účel |
|-------------|------|
| **FastAPI** | HTTP framework, automatická dokumentace, validace |
| **SQLAlchemy** | ORM pro práci s databází |
| **SQLite** | Databáze pro metadata (soubor storage.db) |
| **aiofiles** | Asynchronní I/O operace se soubory |
| **python-multipart** | Parsování file uploadů |
| **Pydantic** | Validace a serializace dat (integrován ve FastAPI) |
| **uvicorn** | ASGI server pro spuštění aplikace |
