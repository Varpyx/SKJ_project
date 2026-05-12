import asyncio
import json
import msgpack
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

import schemas
import database
from models import QueuedMessage


app = FastAPI(
    title="Pub/Sub Message Broker",
    description="Message broker s perzistentními frontami (Durable Queues)."
)


class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()

    def subscribe(self, websocket: WebSocket, topic: str):
        if topic not in self.active_connections:
            self.active_connections[topic] = set()
        self.active_connections[topic].add(websocket)
        print(f"[BROKER] Klient přihlášen k tématu: '{topic}'")

    def unsubscribe_all(self, websocket: WebSocket):
        for topic in list(self.active_connections.keys()):
            if websocket in self.active_connections.get(topic, set()):
                self.active_connections[topic].discard(websocket)
                if not self.active_connections[topic]:
                    del self.active_connections[topic]

    async def broadcast(self, message: str | bytes, topic: str, is_binary: bool = False):
        if topic in self.active_connections:
            for connection in list(self.active_connections[topic]):
                try:
                    if is_binary:
                        await connection.send_bytes(message)
                    else:
                        await connection.send_text(message)
                except RuntimeError:
                    self.unsubscribe_all(connection)


def save_message_to_db(topic: str, payload: bytes) -> int:
    db = database.SessionLocal()
    try:
        msg = QueuedMessage(topic=topic, payload=payload, is_delivered=False)
        db.add(msg)
        db.commit()
        db.refresh(msg)
        return msg.id
    finally:
        db.close()


def mark_message_delivered(message_id: int) -> bool:
    db = database.SessionLocal()
    try:
        msg = db.query(QueuedMessage).filter(QueuedMessage.id == message_id).first()
        if msg:
            msg.is_delivered = True
            db.commit()
            return True
        return False
    finally:
        db.close()


def get_undelivered_messages(topic: str) -> list[QueuedMessage]:
    db = database.SessionLocal()
    try:
        messages = db.query(QueuedMessage).filter(
            QueuedMessage.topic == topic,
            QueuedMessage.is_delivered == False
        ).order_by(QueuedMessage.created_at).all()
        return messages
    finally:
        db.close()


manager = ConnectionManager()


@app.on_event("startup")
async def startup():
    pass


@app.websocket("/broker")
async def broker_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    print("[BROKER] Nový klient připojen.")

    try:
        while True:
            message = await websocket.receive()

            if message["type"] == "websocket.disconnect":
                raise WebSocketDisconnect()

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

                if msg.action == "subscribe" and msg.topic:
                    manager.subscribe(websocket, msg.topic)

                    loop = asyncio.get_event_loop()
                    undelivered = await loop.run_in_executor(
                        None, get_undelivered_messages, msg.topic
                    )

                    for queued_msg in undelivered:
                        deliver_data = {
                            "action": "deliver",
                            "topic": queued_msg.topic,
                            "message_id": queued_msg.id,
                            "payload": msgpack.unpackb(queued_msg.payload)
                        }
                        if is_binary:
                            await websocket.send_bytes(msgpack.packb(deliver_data))
                        else:
                            await websocket.send_text(json.dumps(deliver_data))

                    response = {"action": "ack", "status": f"Subscribed to {msg.topic}"}
                    if is_binary:
                        await websocket.send_bytes(msgpack.packb(response))
                    else:
                        await websocket.send_text(json.dumps(response))

                elif msg.action == "publish" and msg.topic:
                    print(f"[BROKER] PUBLISH -> téma '{msg.topic}'")

                    payload_bytes = msgpack.packb(msg.payload) if is_binary else msgpack.packb(msg.payload)
                    loop = asyncio.get_event_loop()
                    message_id = await loop.run_in_executor(
                        None, save_message_to_db, msg.topic, payload_bytes
                    )
                    print(f"[BROKER] Zpráva uložena do DB s ID={message_id}")

                    deliver_msg = {
                        "action": "deliver",
                        "topic": msg.topic,
                        "message_id": message_id,
                        "payload": msg.payload
                    }

                    if msg.topic in manager.active_connections:
                        payload_bytes_out = msgpack.packb(deliver_msg) if is_binary else None
                        payload_text_out = json.dumps(deliver_msg) if not is_binary else None

                        for connection in list(manager.active_connections[msg.topic]):
                            try:
                                if is_binary:
                                    await connection.send_bytes(payload_bytes_out)
                                else:
                                    await connection.send_text(payload_text_out)
                            except RuntimeError:
                                manager.unsubscribe_all(connection)

                elif msg.action == "ack" and msg.message_id:
                    print(f"[BROKER] ACK pro zprávu ID={msg.message_id}")
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(
                        None, mark_message_delivered, msg.message_id
                    )

            except ValidationError:
                error_msg = {"action": "error", "message": "Neplatný formát"}
                if is_binary:
                    await websocket.send_bytes(msgpack.packb(error_msg))
                else:
                    await websocket.send_text(json.dumps(error_msg))

    except WebSocketDisconnect:
        manager.unsubscribe_all(websocket)
        print("[BROKER] Klient odpojen.")