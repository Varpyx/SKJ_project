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
  * *Oprava:* Propašování uživatelského ID z API requestu přes Brokera až do Workera a následné přidání hlavičky `{"X-User