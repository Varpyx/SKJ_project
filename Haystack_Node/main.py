"""
main.py - Haystack Node
Spuštění: uvicorn main:app --reload --port 8002
"""
import os
import asyncio
import msgpack
import websockets
from fastapi import FastAPI, Response
from contextlib import asynccontextmanager

from haystack import HaystackManager

BROKER_URI = "ws://127.0.0.1:8000/broker"
manager = HaystackManager(storage_dir="volumes", max_size_mb=100)

async def broker_listener():
    """Tato funkce běží na pozadí a naslouchá zprávám z brokera."""
    print("🎧 Haystack Node se připojuje k Brokeru...")

    while True:
        try:
            async with websockets.connect(BROKER_URI, max_size=None) as ws:
                # 1. Přihlášení k tématu pro zápis přes MessagePack
                subscribe_msg = {"action": "subscribe", "topic": "storage.write"}
                await ws.send(msgpack.packb(subscribe_msg))
                print("✅ Úspěšně přihlášen k 'storage.write'")

                # 2. Smyčka pro příjem dat
                while True:
                    message = await ws.recv()
                    data = msgpack.unpackb(message)

                    if data.get("action") == "deliver":
                        message_id = data.get("message_id")
                        payload = data.get("payload", {})

                        object_id = payload.get("object_id")
                        image_bytes = payload.get("image_bytes")

                        if not object_id or not image_bytes:
                            continue

                        # 3. ZÁPIS (Append-only) do Haystacku
                        volume_id, offset, size = manager.append_data(image_bytes)
                        print(f"💾 Uloženo: {object_id} -> Vol:{volume_id}, Offset:{offset}, Size:{size}")

                        # 4. Potvrzení Brokeru (ACK), aby zprávu vyřadil z perzistentní fronty
                        if message_id:
                            ack_broker = {"action": "ack", "message_id": message_id}
                            await ws.send(msgpack.packb(ack_broker))

                        # 5. Odeslání metadat o zápisu zpět Gatewayi (PUBLISH do tématu storage.ack)
                        ack_payload = {
                            "object_id": object_id,
                            "volume_id": volume_id,
                            "offset": offset,
                            "size": size
                        }
                        pub_msg = {
                            "action": "publish",
                            "topic": "storage.ack",
                            "payload": ack_payload
                        }
                        await ws.send(msgpack.packb(pub_msg))

        except websockets.ConnectionClosed:
            print("❌ Spojení s Brokerem bylo přerušeno. Zkusím to znovu za 3s...")
            await asyncio.sleep(3)
        except Exception as e:
            print(f"❌ Chyba listeneru: {e}")
            await asyncio.sleep(3)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Spravuje životní cyklus aplikace (spuštění a vypnutí)."""
    listener_task = asyncio.create_task(broker_listener())
    yield
    listener_task.cancel()
    manager.close()
    print("🛑 Haystack Node bezpečně ukončen.")

app = FastAPI(lifespan=lifespan)

@app.get("/volume/{volume_id}/{offset}/{size}")
def read_needle(volume_id: int, offset: int, size: int):
    """HTTP Endpoint pro rychlé čtení."""
    filepath = os.path.join(manager.storage_dir, f"volume_{volume_id}.dat")

    if not os.path.exists(filepath):
        return Response(status_code=404, content="Svazek nenalezen")

    with open(filepath, "rb") as f:
        f.seek(offset)
        image_data = f.read(size)

    return Response(content=image_data, media_type="image/jpeg")