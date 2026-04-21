# Report: Automatizované testy pro Message Broker

## Úkol 4: Automatizované testy (pytest)

### Implementované změny

#### 1. Přidány testovací závislosti
Do `Message_broker/requirements.txt` byly přidány:
```
pytest>=8.0.0
pytest-asyncio>=0.23.0
httpx>=0.27.0
```

#### 2. Vytvořena testovací struktura
```
Message_broker/
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   └── test_broker.py
```

#### 3. Testovací scénáře

| Test | Popis | Status |
|------|-------|--------|
| `test_client_connect_disconnect` | Úspěšné připojení a odpojení klienta | ✅ |
| `test_client_receive_ack_on_subscribe` | Přijetí ACK zprávy po subscribe | ✅ |
| `test_multiple_clients_connect` | Připojení více klientů současně | ✅ |
| `test_message_reaches_subscribed_client` | Zpráva do tématu X dorazí klientovi odebírajícímu X | ✅ |
| `test_message_not_reaches_unsubscribed_topic` | Zpráva do Y NEDORAZÍ klientovi pouze na X | ✅ |
| `test_multiple_subscribers_same_topic` | Více odběratelů na stejné téma | ✅ |
| `test_client_subscribe_to_multiple_topics` | Jeden klient odebírá více témat | ✅ |
| `test_invalid_message_format` | Ošetření neplatného formátu zprávy | ✅ |
| `test_publish_without_topic` | Ošetření publish bez tématu | ✅ |
| `test_client_removed_after_disconnect` | Úklid po odpojení klienta | ✅ |

### Technologie použité pro testování
- **pytest** - Framework pro psaní testů
- **pytest-asyncio** - Podpora pro async testy
- **httpx** - HTTP client s podporou WebSocketů
- **TestClient** z FastAPI - Pro testování WebSocket endpointů

### Spuštění testů
```bash
cd Message_broker
pip install -r requirements.txt
pytest tests/ -v
```

### Výsledek
```
============================= test session starts ==============================
tests/test_broker.py::TestWebSocketConnection::test_client_connect_disconnect PASSED
tests/test_broker.py::TestWebSocketConnection::test_client_receive_ack_on_subscribe PASSED
tests/test_broker.py::TestWebSocketConnection::test_multiple_clients_connect PASSED
tests/test_broker.py::TestPubSub::test_message_reaches_subscribed_client PASSED
tests/test_broker.py::TestPubSub::test_message_not_reaches_unsubscribed_topic PASSED
tests/test_broker.py::TestPubSub::test_multiple_subscribers_same_topic PASSED
tests/test_broker.py::TestPubSub::test_client_subscribe_to_multiple_topics PASSED
tests/test_broker.py::TestErrorHandling::test_invalid_message_format PASSED
tests/test_broker.py::TestErrorHandling::test_publish_without_topic PASSED
tests/test_broker.py::TestCleanup::test_client_removed_after_disconnect PASSED

============================== 10 passed in 0.54s ==============================
```

---
