# Report: Úkol 5 - Garantované doručení a perzistence (Durable Queues)

## Implementované změny

### 1. Nové soubory

| Soubor | Popis |
|--------|-------|
| `database.py` | SQLAlchemy nastavení (engine, session, Base) |
| `models.py` | Model `QueuedMessage` pro perzistenci zpráv |
| `alembic/` | Alembic konfigurace pro migrace |
| `alembic.ini` | Alembic nastavení |
| `alembic/env.py` | Prostředí pro migrace |
| `alembic/script.py.mako` | Šablona pro migrace |
| `alembic/versions/a1b2c3d4e5f6_queued_messages.py` | Migrace pro tabulku queued_messages |

### 2. Aktualizované soubory

| Soubor | Změna |
|--------|-------|
| `requirements.txt` | Přidán `sqlalchemy>=2.0.35` |
| `main.py` | Implementace durable queues flow |
| `mb_client.py` | Přidáno odesílání ACK |
| `schemas.py` | Rozšířena dokumentace protokolu |
| `tests/test_broker.py` | Přidány testy pro persistence |
| `tests/conftest.py` | Alembic fixture pro testy |

### 3. Databázový model (Alembic migrace)

```python
# alembic/versions/a1b2c3d4e5f6_queued_messages.py
def upgrade() -> None:
    op.create_table(
        'queued_messages',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('topic', sa.String(), index=True, nullable=False),
        sa.Column('payload', sa.LargeBinary(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('is_delivered', sa.Boolean(), default=False, nullable=False),
    )
```

### 4. Implementované flow

#### Publisher Flow
```
1. Publisher -> {"action": "publish", "topic": "X", "payload": {...}}
2. Broker ukládá do DB (is_delivered=False)
3. Broker přiděluje message_id
4. Broker broadcast {"action": "deliver", "message_id": N, ...}
```

#### Subscriber Flow
```
1. Subscriber -> {"action": "subscribe", "topic": "X"}
2. Broker posílá historické nezpracované zprávy
3. Broker posílá ACK potvrzení
```

#### ACK Flow
```
1. Subscriber -> {"action": "ack", "message_id": N}
2. Broker označí v DB: is_delivered=True
```

### 5. Řešení blokujících operací

**Použito:** `asyncio.get_event_loop().run_in_executor()`

```python
loop = asyncio.get_event_loop()
message_id = await loop.run_in_executor(
    None, save_message_to_db, topic, payload_bytes
)
```

Synchronní SQLAlchemy operace běží v threadpoolu, neblokuje async event loop.

### 6. Alembic příkazy

```bash
# Generovat novou migraci
alembic revision --autogenerate -m "popis"

# Aplikovat migrace
alembic upgrade head

# Vrátit migraci
alembic downgrade -1
```

## Testy

| Test | Popis | Status |
|------|-------|--------|
| `test_message_persisted_to_database` | Zpráva uložena s ID | ✅ |
| `test_undelivered_messages_on_subscribe` | Po reconnect přijmu historii | ✅ |
| `test_ack_marks_message_delivered` | ACK označí jako doručené | ✅ |
| `test_multiple_messages_delivered_in_order` | Pořadí zpráv | ✅ |

## Výsledek testů

```
14 passed in 1.31s
```

---

**Datum:** 21.04.2026
**Autor:** Durable Queues implementation (s Alembic migracemi)