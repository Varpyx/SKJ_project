## 🛠️ Co projekt obsahuje a co se udělalo

* **Broker (`main.py`):** Asynchronní server ve FastAPI, který řídí spojení, spravuje témata (Topics) a routuje zprávy od vydavatelů (Publishers) k odběratelům (Subscribers).
* **Robustnost:** Server je obrněn proti pádům při náhlém odpojení klientů (odchycení `WebSocketDisconnect` a `RuntimeError`) a bezpečně uvolňuje paměť.
* **Klient (`mb_client.py`):** CLI aplikace, která umí fungovat jako odesílatel i příjemce.
* **Podpora dvou formátů:** Celý systém podporuje posílání zpráv ve standardním textovém **JSON** formátu i v efektivním binárním **MessagePack** formátu.

---

## ⚙️ Instalace a spuštění

Před spuštěním nainstalujte potřebné závislosti (ujistěte se, že máte aktivní virtuální prostředí):

```bash
pip install -r requirements.txt
```

## Manuální testování: 

* Server: uvicorn main:app --reload --port 8000


* Sub: 
  * python mb_client.py --mode sub --format json (json)
  * python mb_client.py --mode sub --format msgpack (binární)


* Pub:
  * python mb_client.py --mode pub --format json (json)
  * python mb_client.py --mode pub --format msgpack (binarní)


* při vypnutí subu stále posílá pub data, při vypnutí pubu program nespadne