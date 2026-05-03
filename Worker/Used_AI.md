# Použité AI

* Gemini

## 1. Příklad promptu

1. *"okey bro, ted ty 2 věci mjsíme spojit. zde je nove zadání: Úkol: Image Processing Worker (Event-Driven)..."*
2. *"jo akorat nemame to naopka? dokumentace API (automaticky generovaná FastAPI): http://localhost:8000/docs ← Swagger UI [...] S3 je na 8000"*

## 2. Co AI navrhla správně na první dobrou

* **Kostra mikroslužeb:** Okamžité sestavení funkční asynchronní kostry v `worker.py` využívající `websockets` pro Broker a `httpx` pro neblokující komunikaci s REST API.
* **NumPy transformace:** Všech 5 matematických operací nad maticemi bylo implementováno přesně podle zadání hned v prvním návrhu (včetně řešení ořezu a prevence přetečení barev z `uint8`).
* **Integrace do S3:** Správné použití `BackgroundTasks` ve FastAPI pro okamžité odeslání HTTP odpovědi a asynchronní delegování zprávy do Brokera.

## 3. Co bylo nutné dodatečně upravit a ladit

* **Neshoda datových klíčů (Payload Mismatch):** * *Problém:* Worker ve zprávě od Brokera očekával klíč `object_id`, ale S3 Gateway odesílala klíč `file_id`. Výsledkem byla hodnota `None` a selhání stahování (Chyba 404).
  * *Oprava:* Úprava parsování JSON zprávy uvnitř `worker.py`, aby klíče přesně odpovídaly Pydantic schématu z `main.py`.
* **Chybějící bezpečnostní hlavičky (Auth Headers):**
  * *Problém:* První návrh Workera se snažil soubory z S3 stáhnout "naslepo". Tvůj backend ale striktně (a správně) vyžaduje hlavičku `X-User-Id`.
  * *Oprava:* Propašování uživatelského ID z API requestu přes Brokera až do Workera a následné přidání hlavičky `{"X-User-Id": user_id}`.

## 4. Integrační test (test_worker.py)

* **Příklad promptu:** *"Napište integrační test, který nasimuluje poslání 10 úloh do brokera a ověří, že Worker postupně všechny zpracuje a odešle 10 potvrzovacích zpráv. vezmi obrazky miner a skeleton ktere nahrajes na server, a na kazdy z nich das brokeru 5 uloh na operace pro workera popsane v worker.md napr grayscale, invert..."*

* **Co AI navrhla správně:**
  * Využití `pytest.mark.asyncio` pro asynchronní testování
  * Použití `asyncio.gather()` pro souběžné odesílání úloh a přijímání potvrzení
  * Upload testovacích obrázků (`miner.png`, `Skeleton profile picture.jpg`) přes S3 API před odesláním úloh
  * Odeslání 10 úloh (5 operací × 2 obrázky) na téma `image.jobs`
  * Sběr potvrzení ze tématu `image.done` přes WebSocket

* **Co bylo nutné dodatečně upravit:**
  * *Problém:* Crop operace selhala na malém obrázku (16x21 px) s parametry 10px z každé strany
  * *Oprava:* Změna crop parametrů ze 10px na 2px pro každou stranu, aby se vešly do rozměrů testovacích obrázků