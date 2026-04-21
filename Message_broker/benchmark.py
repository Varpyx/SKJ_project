import asyncio
import websockets
import time
import json
import msgpack

# Konfigurace benchmarku
URI = "ws://localhost:8000/broker"
TOPIC = "benchmark_test"
NUM_PUBS = 5
NUM_SUBS = 5
MSG_PER_PUB = 10000

# Každý odběratel dostane zprávy od všech vydavatelů
TOTAL_EXPECTED_PER_SUB = NUM_PUBS * MSG_PER_PUB  

async def subscriber(sub_id: int, data_format: str):
    """Odběratel, který čeká na přesný počet zpráv."""
    async with websockets.connect(URI) as ws:
        # 1. Přihlášení k odběru
        sub_msg = {"action": "subscribe", "topic": TOPIC}
        if data_format == "msgpack":
            await ws.send(msgpack.packb(sub_msg))
        else:
            await ws.send(json.dumps(sub_msg))
            
        # 2. Počkáme na potvrzení (ack) od serveru
        await ws.recv()

        # 3. Přijímání zpráv
        received = 0
        while received < TOTAL_EXPECTED_PER_SUB:
            await ws.recv()
            received += 1
            
        return received

async def publisher(pub_id: int, data_format: str):
    """Vydavatel, který co nejrychleji "vyplivne" všechny své zprávy."""
    async with websockets.connect(URI) as ws:
        pub_msg = {
            "action": "publish", 
            "topic": TOPIC, 
            "payload": {"sensor": pub_id, "temp": 42.0}
        }
        
        # Připravíme si zprávu dopředu, ať nezdržujeme cyklus serializací
        if data_format == "msgpack":
            payload = msgpack.packb(pub_msg)
        else:
            payload = json.dumps(pub_msg)

        # Odeslání zpráv v co nejrychlejším sledu
        for _ in range(MSG_PER_PUB):
            await ws.send(payload)

async def run_benchmark(data_format: str):
    print(f"\n🚀 Spouštím benchmark pro formát: {data_format.upper()}")
    print(f"Vytvářím {NUM_SUBS} Subscriberů a {NUM_PUBS} Publisherů...")
    
    # 1. Spustíme Odběratele jako úkoly na pozadí
    subs_tasks = [asyncio.create_task(subscriber(i, data_format)) for i in range(NUM_SUBS)]
    
    # Dáme serveru malou chvíli (1 vteřinu), aby bezpečně zaregistroval všechny odběratele
    await asyncio.sleep(1)
    
    print(f"Odesílám celkem {NUM_PUBS * MSG_PER_PUB} zpráv do Brokera...")
    
    # Začátek měření!
    start_time = time.perf_counter()
    
    # 2. Spustíme Vydavatele (začnou okamžitě bombardovat server)
    pubs_tasks = [asyncio.create_task(publisher(i, data_format)) for i in range(NUM_PUBS)]
    
    # Počkáme, až Publishery vše odešlou a Subscribeři vše přijmou
    await asyncio.gather(*pubs_tasks)
    await asyncio.gather(*subs_tasks)
    
    # Konec měření!
    end_time = time.perf_counter()
    elapsed_time = end_time - start_time
    
    # Výpočet statistik
    total_received = NUM_SUBS * TOTAL_EXPECTED_PER_SUB
    throughput = total_received / elapsed_time
    
    print("-" * 40)
    print(f"✅ HOTOVO ({data_format.upper()})")
    print(f"⏱️ Celkový čas:      {elapsed_time:.3f} sekund")
    print(f"📥 Přijato zpráv:    {total_received} (všemi odběrateli)")
    print(f"⚡ Propustnost:      {throughput:.0f} zpráv/sekundu")
    print("-" * 40)

async def main():
    # Spustíme oba testy za sebou pro přímé porovnání
    await run_benchmark("json")
    # Pauza mezi testy, aby se uvolnily síťové buffery
    await asyncio.sleep(2)
    await run_benchmark("msgpack")

if __name__ == "__main__":
    # Na Windows může běžný policy způsobovat chyby na konci event loopu,
    # proto explicitně nastavíme bezpečnější metodu pro zátěžové testy.
    import sys
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBenchmark přerušen.")