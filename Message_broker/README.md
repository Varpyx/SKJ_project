# Message Broker

WebSocket-based Pub/Sub broker s perzistentními frontami (Durable Queues).

## SUB/PUB komunikace

### Terminal 1 - Server
```bash
cd Message_broker
source venv/bin/activate
uvicorn main:app --port 8000
```

### Terminal 2 - Subscriber (poslouchá)
```bash
cd Message_broker
source venv/bin/activate
python mb_client.py --mode sub --topic test
```

### Terminal 3 - Publisher (odesílá)
```bash
cd Message_broker
source venv/bin/activate
python mb_client.py --mode pub --topic test
```

Příklad zprávy (publisher):
```json
{"action": "publish", "topic": "test", "payload": {"data": "hello world"}}
```

## Přepínání formátů

Podpora JSON i MessagePack:
```bash
python mb_client.py --mode sub --topic test --format msgpack
python mb_client.py --mode pub --topic test --format msgpack
```

## Automatizované testy

```bash
cd Message_broker
source venv/bin/activate
pytest tests/ -v
```

## Databáze

Zprávy se ukládají do `broker.db` (SQLite).

```bash
sqlite3 broker.db "SELECT * FROM queued_messages;"
```

## Alembic migrace

```bash
# Aplikovat migrace
alembic upgrade head

# Zobrazit historii
alembic history

# Vrátit migraci
alembic downgrade -1
```