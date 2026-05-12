# AGENTS.md

## Architecture — 4 services

| Service | Dir | Entrypoint | Port | Type |
|---|---|---|---|---|
| Message Broker | `Message_broker/` | `main:app` | 8000 | FastAPI + WebSocket Pub/Sub |
| S3 Gateway (Rest API) | `Rest_Api/` | `main:app` | 8001 | FastAPI file storage API |
| Haystack Node | `Haystack_Node/` | `main:app` | 8002 | FastAPI + bg WS listener |
| Image Worker | `Worker/` | `worker.py` | — | standalone asyncio script |

**Data flow (image processing):** User → S3 Gateway (8001) → Broker `image.jobs` (8000) → Worker → S3 Gateway

**Data flow (file storage):** S3 Gateway → Broker `storage.write` → Haystack Node (append-only volumes) → ACK `storage.ack` → S3 Gateway updates `volume_id`/`offset` in DB

S3 Gateway slouží jako jediný bod kontaktu pro uživatele (API klienty). Uživatel nikdy nekomunikuje přímo s Haystack Node.

- **Čtení (`GET /download/{object_id}`):** S3 Gateway zkontroluje databázi (a oprávnění). Pokud má soubor `status == "ready"`, přečte `volume_id`, `offset`, `size` a interně zavolá Haystack Node na `/volume/{volume_id}/{offset}/{size}`. Přijatá data obratem přepošle uživateli.
- **Mazání (`DELETE /download/{object_id}`):** Striktní Soft Delete — nastaví `is_deleted = True` v DB S3 Gateway. Haystack Node se o mazání nedozví, data ve `volume_X.dat` fyzicky zůstávají.

## Startup (4 terminals, order matters)

```bash
# Terminal 1 — Broker
cd Message_broker && uvicorn main:app --port 8000

# Terminal 2 — S3 Gateway
cd Rest_Api && uvicorn main:app --port 8001

# Terminal 3 — Haystack Node
cd Haystack_Node && uvicorn main:app --port 8002

# Terminal 4 — Worker
cd Worker && python worker.py
```

## Tests

```bash
# Broker unit tests (standalone, no deps needed)
cd Message_broker && alembic upgrade head && pytest tests/ -v

# Worker integration test (requires all 3 services above running)
cd Worker && pytest test_worker.py -v
```

Worker integration test auto-cleans `broker.db`, creates a temp bucket, uploads 2 images (`miner.png`, `Skeleton.jpg`), sends 10 jobs (5 ops × 2 images), and expects 10 success confirmations.

## Other commands

```bash
# CLI Pub/Sub client (talk to broker directly)
cd Message_broker && python mb_client.py --mode pub --topic sensors
cd Message_broker && python mb_client.py --mode sub --topic sensors --format msgpack

# Benchmark (broker must be running)
cd Message_broker && python benchmark.py

# Haystack volume compaction (S3 Gateway must be running)
cd Haystack_Node && source ../venv/bin/activate && python compact.py <volume_id>

# Alembic migrations (Message_broker)
cd Message_broker && alembic upgrade head
cd Message_broker && alembic downgrade -1
```

## Conventions & gotchas

- **Auth:** `X-User-Id` header (no real auth). Internal transfers use `X-Internal-Source: true`.
- **Buckets required:** Create bucket first via `POST /buckets/` before uploading files.
- **File size limit:** 10 MB.
- **Soft delete:** Files get `is_deleted=True` flag, stay on disk. Not shown in `GET /files`. Haystack Node se o mazání nedozví — data ve `volume_X.dat` zůstávají.
- **Worker image ops:** `invert`, `flip`, `crop` (params: top/bottom/left/right), `brightness` (params: value), `grayscale`.
- **Broker stores undelivered messages in SQLite persistently** — messages survive restarts until ACKed.
- **Haystack volumes:** append-only binary files at `Haystack_Node/volumes/volume_{id}.dat`. Default max 100 MB per volume.
- **Eventual consistency:** S3 Gateway waits up to 2s for Haystack ACK before serving downloads (checks `volume_id is None` as proxy for `status == "ready"`).
- **Broker supports JSON and MessagePack.** Haystack Node and S3 Gateway communicate with broker using MessagePack for binary data.
- **S3 Gateway README says port 8000** — actual code uses **8001**.
- **venv** at project root (`venv/`); activate before running anything: `source venv/bin/activate`.
