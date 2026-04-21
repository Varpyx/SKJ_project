# Využití AI nástrojů při projektu

## Jaké nástroje AI byly použity

* **Gemini** - Kompletní návrh a debugging Message Broker mikroslužby (FastAPI WebSockets), implementace Pub/Sub vzoru (ukol 1, 2)

## Příklady promptů
* *"když ukončím publishera tak ok. když jsem ale vypnul klienta tak program spadl: asyncio.exceptions.IncompleteReadError"*
* *"no ted když ukončím klienta tak se pořád dále posíla a na serveru se to zobrazuje, to nevím jestli je správně..."*

## Co AI vygenerovala správně
* **Pub/Sub Architektura:** Správný a čistý návrh třídy `ConnectionManager` pro správu WebSocketů a routování zpráv podle témat.
* **Klientský skript (`mb_client.py`):** Funkční implementace klienta přes `argparse`, který uměl plynule přepínat mezi módy (Publisher/Subscriber) a formáty (JSON/MessagePack).

## AI a návrh ConnectionManageru

AI navrhla elegantní třídu `ConnectionManager`, která:
- Udržuje slovník `active_connections: dict[str, set[WebSocket]]`
- Mapuje názvy témat na množiny připojených WebSocketů
- Implementuje metody `connect()`, `subscribe()`, `unsubscribe_all()`, `broadcast()`
- Používá `set.discard()` (ne `remove()`) pro bezpečné odpojení bez výjimek

### Klíčová rozhodnutí od AI
1. **Proč množina (`set`)?** WebSocket může být současně přihlášen k více tématům
2. **Proč slovník témat?** Efektivní broadcast - zpráva jde jen příjemcům daného tématu
3. **Proč `list()` kopie?** Bezpečná iterace i při souběžném odpojení

## Jaké chyby AI udělala a co bylo nutné opravit
* **Rozbití WebSocket disconnectu po nasazení binárních dat:** Při přechodu z `receive_text()` na obecné `receive()` (kvůli MessagePacku) server přestal automaticky odchytávat odpojení. Kód padal na `RuntimeError: Cannot call "receive" once a disconnect message has been received`. Museli jsme ručně dopsat detekci `message["type"] == "websocket.disconnect"`.
* **Pády při souběhu odpojení a odesílání:** Server padal, pokud se Subscriber odpojil přesně v milisekundě, kdy mu Broker zkoušel poslat zprávu. Museli jsme iteraci přes aktivní spojení obalit do `try-except RuntimeError` a použít kopii množiny `list(active_connections)`.
* **Pády klienta při ztrátě serveru:** Klientský skript neměl ošetřený výpadek Brokera a házel dlouhé chybové Tracebacky (`IncompleteReadError`). Museli jsme dopsat `try-except websockets.exceptions.ConnectionClosed`

---

## Úkol 4: Automatizované testy (pytest)

* **ChatGPT/OpenCode** - Napsání integračních testů pro Message Broker pomocí pytest, pytest-asyncio a httpx TestClient.

### AI a návrh asynchronních testů v Pytestu

Psaní async testů pro WebSockety je ošemetné. AI navrhla:

#### Použitý přístup
```python
with client.websocket_connect("/broker") as ws:
    ws.send_json({"action": "subscribe", "topic": "test"})
    response = ws.receive_json()
    assert response["action"] == "ack"
```

#### Proč to funguje
- `TestClient` z FastAPI testuje ASGI aplikaci přímo (bez síťového stacku)
- `websocket_connect()` vytváří správný ASGI scope
- `send_json()`/`receive_json()` serializují a čekají na odpověď

#### Úskalí, která AI správně neodhadla
- **Syntaxe:** `TestClient.websocket_connect()` vs `client.websocket_connect()` - opraveno
- **Pořadí spojení:** Websockety musí zůstat otevřené během testu, ne sequential
- **Cleanup:** Nutný `reset_manager()` fixture pro každý test

### Co AI vygenerovala
* Vytvořena testovací struktura v `tests/` složce (`__init__.py`, `conftest.py`, `test_broker.py`)
* 10 integračních testů pokrývajících:
  * Připojení a odpojení klienta
  * Subscribe/unsubscribe k tématům
  * Pub/Sub funkcionalitu (zpráva dorazí správnému klientovi)
  * Izolaci témat (zpráva do Y nedojde klientovi na X)
  * Error handling (neplatný formát, publish bez tématu)
  * Úklid po odpojení klienta

### Jaké chyby AI udělala a co bylo nutné opravit
* **Syntaxe:** Původně `TestClient.websocket_connect()` místo `client.websocket_connect()` - opraveno.
* **Pořadí spojení:** Websockety musí zůstat otevřené během testu (ne sequential).
* **Timeout:** Publisher bez subscribera čekal na odpověď - test upraven.

---

## Úkol 5: Garantované doručení a perzistence (Durable Queues)

* **ChatGPT/OpenCode** - Návrh a implementace perzistentních front, databázový model, synchronizační logika.

### Co AI vygenerovala
* **Databázová vrstva:** `database.py` s SQLAlchemy engine, session a Base
* **Model QueuedMessage:** Tabulka pro ukládání zpráv s poli `id`, `topic`, `payload`, `created_at`, `is_delivered`
* **Durable queues flow v `main.py`:** Publisher flow (uložení → broadcast), Subscriber flow (načtení historie), ACK flow (označení)
* **Řešení blokády:** Použití `asyncio.get_event_loop().run_in_executor()` pro synchronní DB operace
* **Alembic migrace:** `alembic/versions/a1b2c3d4e5f6_queued_messages.py` pro vytvoření tabulky `queued_messages`

### Jaké chyby AI udělala a co bylo nutné opravit
* **Async event loop blokáda:** Synchronní SQLAlchemy by zablokoval WebSocket handler. Řešení: `run_in_executor()` přesouvá operace do threadpoolu.
* **Test timeout:** Test `test_undelivered_messages_on_subscribe` timeoutoval - publisher neměl subscribera a čekal na odpověď. Opraveno přímým dotazem na DB místo WebSocket response.
* **Test reconnect:** Původní test očekával více zpráv, ale historie se posílá správně. Test přepsán na jednodušší verzi kontrolující DB záznamy.
* **Alembic config:** Původně chyběla `sqlalchemy.url` v alembic.ini, takže migrace netvořila tabulky. Opraveno přidáním URL do sekce `[alembic]`.
* **Test fixture pořadí:** Fixtury běžely po načtení aplikace, ale startup handler neaplikoval migrace. Opraveno změnou fixture na session scope.

### Volba řešení: run_in_executor vs AsyncSession

**Zvoleno:** `asyncio.get_event_loop().run_in_executor(None, sync_func, args)`

**Proč:**
- Jednodušší implementace (nevyžaduje AsyncSQLAlchemy setup)
- SQLite nepotřebuje async (nízká zátěž)
- `run_in_executor` je dostatečný pro tento případ

**AsyncSession by bylo lepší pro:**
- Vysoký počet concurrent spojení
- PostgreSQL s connection pool
- Produkční nasazení