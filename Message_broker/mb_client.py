import asyncio
import websockets
import json
import msgpack
import argparse
from datetime import datetime


class MBClient:
    def __init__(self, uri: str, mode: str, data_format: str, topic: str):
        self.uri = uri
        self.mode = mode
        self.format = data_format
        self.topic = topic

    def serialize(self, data: dict):
        """Převede Python slovník do JSONu nebo MessagePacku podle nastavení."""
        if self.format == "msgpack":
            return msgpack.packb(data)  # Vrací bytes
        return json.dumps(data)  # Vrací text (string)

    def deserialize(self, data):
        """Převede příchozí data (bytes nebo string) zpět na Python slovník."""
        if self.format == "msgpack":
            return msgpack.unpackb(data)
        return json.loads(data)

    async def run(self):
        try:
            # Připojení k brokeru
            async with websockets.connect(self.uri) as websocket:
                print(f"Připojeno k {self.uri} | Režim: {self.mode.upper()} | Formát: {self.format.upper()}")

                try:
                    # ---------------------------------------------------------
                    # MÓD SUBSCRIBER
                    # ---------------------------------------------------------
                    if self.mode == "sub":
                        sub_msg = {"action": "subscribe", "topic": self.topic}
                        await websocket.send(self.serialize(sub_msg))
                        print(f"[*] Přihlášeno k odběru tématu '{self.topic}'. Čekám na zprávy...\n")

                        while True:
                            response = await websocket.recv()
                            data = self.deserialize(response)
                            print(f"[{datetime.now().strftime('%H:%M:%S')}] PŘIJATO: {data}")

                    # ---------------------------------------------------------
                    # MÓD PUBLISHER
                    # ---------------------------------------------------------
                    elif self.mode == "pub":
                        print(f"[*] Odesílám testovací data do tématu '{self.topic}' každé 2 vteřiny...\n")
                        counter = 1
                        while True:
                            pub_msg = {
                                "action": "publish",
                                "topic": self.topic,
                                "payload": {"temp": 22.5 + counter, "sensor_id": counter}
                            }
                            await websocket.send(self.serialize(pub_msg))
                            print(f"[{datetime.now().strftime('%H:%M:%S')}] ODESLÁNO: {pub_msg}")
                            counter += 1
                            await asyncio.sleep(2)

                # Odchycení ztráty spojení během běhu
                except websockets.exceptions.ConnectionClosed:
                    print("\n[!] Spojení s Brokerem bylo přerušeno (server se pravděpodobně vypnul).")
                except EOFError:
                    print("\n[!] Konec spojení (přerušeno).")

        # Odchycení chyby, pokud Broker vůbec neběží už při pokusu o připojení
        except ConnectionRefusedError:
            print(f"\n[!] Nelze se připojit k Brokeru na {self.uri}. Běží server?")

if __name__ == "__main__":
    # Nastavení spouštění z terminálu
    parser = argparse.ArgumentParser(description="Pub/Sub Client")
    parser.add_argument("--mode", choices=["pub", "sub"], required=True,
                        help="Režim: pub (Publisher) nebo sub (Subscriber)")
    parser.add_argument("--format", choices=["json", "msgpack"], default="json", help="Formát zpráv (default: json)")
    parser.add_argument("--topic", default="sensors", help="Téma (default: sensors)")
    args = parser.parse_args()

    # Vytvoření a spuštění klienta
    client = MBClient(
        uri="ws://localhost:8000/broker",
        mode=args.mode,
        data_format=args.format,
        topic=args.topic
    )

    # Bezpečné spuštění asynchronní smyčky
    try:
        asyncio.run(client.run())
    except KeyboardInterrupt:
        print("\nKlient ukončen.")