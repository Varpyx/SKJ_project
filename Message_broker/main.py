import json
import msgpack
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

import schemas

# ---------------------------------------------------------------------------
# Inicializace aplikace
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Pub/Sub Message Broker",
    description="Asynchronní message broker využívající WebSockety."
)


# ---------------------------------------------------------------------------
# Třída ConnectionManager (Správce spojení a témat)
# ---------------------------------------------------------------------------
class ConnectionManager:
    def __init__(self):
        # Mapa: název tématu -> množina připojených WebSocketů
        # Příklad: {"orders": {ws1, ws2}, "emails": {ws2, ws3}}
        self.active_connections: dict[str, set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket):
        """Přijme nové spojení od klienta."""
        await websocket.accept()

    def subscribe(self, websocket: WebSocket, topic: str):
        """Přidá klienta k odběru konkrétního tématu."""
        if topic not in self.active_connections:
            self.active_connections[topic] = set()

        self.active_connections[topic].add(websocket)
        print(f"[BROKER] Klient se přihlásil k odběru tématu: '{topic}'")

    def unsubscribe_all(self, websocket: WebSocket):
        """Bezpečně odstraní klienta ze VŠECH témat (např. při výpadku)."""
        for topic in list(self.active_connections.keys()):
            if websocket in self.active_connections[topic]:
                self.active_connections[topic].discard(websocket)

                # Udržujeme paměť čistou - prázdná témata mažeme
                if not self.active_connections[topic]:
                    del self.active_connections[topic]

    async def broadcast(self, message: str, topic: str):
        """Rozešle zprávu asynchronně všem klientům v daném tématu."""
        if topic in self.active_connections:
            for connection in self.active_connections[topic]:
                await connection.send_text(message)


# Vytvoříme jedinou globální instanci našeho manažera
manager = ConnectionManager()


# ---------------------------------------------------------------------------
# WebSocket Endpoint
# ---------------------------------------------------------------------------
@app.websocket("/broker")
async def broker_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    print("[BROKER] Nový klient připojen.")

    try:
        while True:
            message = await websocket.receive()

            # --- OPRAVA 1: Explicitní detekce odpojení ---
            # Pokud nám FastAPI řekne, že se klient odpojil, vyvoláme výjimku ručně
            if message["type"] == "websocket.disconnect":
                raise WebSocketDisconnect()

            # Detekce formátu
            is_binary = False
            if "text" in message and message["text"] is not None:
                raw_data = json.loads(message["text"])
            elif "bytes" in message and message["bytes"] is not None:
                raw_data = msgpack.unpackb(message["bytes"])
                is_binary = True
            else:
                continue

            try:
                msg = schemas.BrokerMessage(**raw_data)

                # --- LOGIKA: SUBSCRIBE ---
                if msg.action == "subscribe" and msg.topic:
                    manager.subscribe(websocket, msg.topic)

                    response = {"action": "ack", "status": f"Subscribed to {msg.topic}"}
                    if is_binary:
                        await websocket.send_bytes(msgpack.packb(response))
                    else:
                        await websocket.send_text(json.dumps(response))

                # --- LOGIKA: PUBLISH ---
                elif msg.action == "publish" and msg.topic:
                    print(f"[BROKER] Zpráva -> téma '{msg.topic}' (Binární: {is_binary})")

                    deliver_msg = {
                        "action": "deliver",
                        "topic": msg.topic,
                        "message_id": 1000 + raw_data.get("payload", {}).get("sensor_id", 0),
                        "payload": msg.payload
                    }

                    if msg.topic in manager.active_connections:
                        payload_bytes = msgpack.packb(deliver_msg) if is_binary else None
                        payload_text = json.dumps(deliver_msg) if not is_binary else None

                        # --- OPRAVA 2: Bezpečné odesílání do všech připojení ---
                        # Použijeme list(...), abychom udělali kopii množiny pro případ,
                        # že se z ní někdo odpojí během iterace.
                        for connection in list(manager.active_connections[msg.topic]):
                            try:
                                if is_binary:
                                    await connection.send_bytes(payload_bytes)
                                else:
                                    await connection.send_text(payload_text)
                            except RuntimeError:
                                # Pokud klient umřel přesně v momentě odesílání,
                                # odchytíme to a klienta bezpečně odstraníme.
                                manager.unsubscribe_all(connection)

            except ValidationError:
                error_msg = {"action": "error", "message": "Neplatný formát"}
                if is_binary:
                    await websocket.send_bytes(msgpack.packb(error_msg))
                else:
                    await websocket.send_text(json.dumps(error_msg))

    except WebSocketDisconnect:
        # Sem se to dostane, jakmile vyvoláme raise WebSocketDisconnect()
        manager.unsubscribe_all(websocket)
        print("[BROKER] Klient se odpojil. Uklízím spojení.")