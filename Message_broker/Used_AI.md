# Využití AI nástrojů při projektu

## Jaké nástroje AI byly použity

* **Gemini** - Kompletní návrh a debugging Message Broker mikroslužby (FastAPI WebSockets), implementace Pub/Sub vzoru (ukol 1, 2)

## Příklady promptů
* *"když ukončím publishera tak ok. když jsem ale vypnul klienta tak program spadl: asyncio.exceptions.IncompleteReadError"*
* *"no ted když ukončím klienta tak se pořád dále posíla a na serveru se to zobrazuje, to nevím jestli je správně..."*

## Co AI vygenerovala správně
* **Pub/Sub Architektura:** Správný a čistý návrh třídy `ConnectionManager` pro správu WebSocketů a routování zpráv podle témat.
* **Klientský skript (`mb_client.py`):** Funkční implementace klienta přes `argparse`, který uměl plynule přepínat mezi módy (Publisher/Subscriber) a formáty (JSON/MessagePack).

## Jaké chyby AI udělala a co bylo nutné opravit
* **Rozbití WebSocket disconnectu po nasazení binárních dat:** Při přechodu z `receive_text()` na obecné `receive()` (kvůli MessagePacku) server přestal automaticky odchytávat odpojení. Kód padal na `RuntimeError: Cannot call "receive" once a disconnect message has been received`. Museli jsme ručně dopsat detekci `message["type"] == "websocket.disconnect"`.
* **Pády při souběhu odpojení a odesílání:** Server padal, pokud se Subscriber odpojil přesně v milisekundě, kdy mu Broker zkoušel poslat zprávu. Museli jsme iteraci přes aktivní spojení obalit do `try-except RuntimeError` a použít kopii množiny `list(active_connections)`.
* **Pády klienta při ztrátě serveru:** Klientský skript neměl ošetřený výpadek Brokera a házel dlouhé chybové Tracebacky (`IncompleteReadError`). Museli jsme dopsat `try-except websockets.exceptions.ConnectionClosed`