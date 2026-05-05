# Použité AI

* Gemini

## 1. Příklad promptu

1. *"okey bro, ted ty 2 věci mjsíme spojit. zde je nove zadání: Úkol: Image Processing Worker (Event-Driven)..."*
2. *"jo akorat nemame to naopka? dokumentace API (automaticky generovaná FastAPI): http://localhost:8000/docs ← Swagger UI [...] S3 je na 8000"*
3. *"Mám toto zadání, vše ostatní je hotové, jen potřebuji bod testování 3. - udělat webovku, která tyto obrázky které mám v bucketu zobrazí"*

## 2. Co AI navrhla správně na první dobrou

* **Kostra mikroslužeb:** Okamžité sestavení funkční asynchronní kostry v `worker.py` využívající `websockets` pro Broker a `httpx` pro neblokující komunikaci s REST API.
* **NumPy transformace:** Všech 5 matematických operací nad maticemi bylo implementováno přesně podle zadání hned v prvním návrhu (včetně řešení ořezu a prevence přetečení barev z `uint8`).
* **Integrace do S3:** Správné použití `BackgroundTasks` ve FastAPI pro okamžité odeslání HTTP odpovědi a asynchronní delegování zprávy do Brokera.
* **Struktura a UI React frontendu:**  Návrh jednostránkové klientské aplikace (SPA) přímo v jednom HTML souboru přes CDN (React + Babel) byl výborně strukturovaný. Od začátku obsahoval funkční správu stavů (useState), oddělení komponent (notifikace, historie jobů) a responzivní design, což umožnilo bleskové testování S3 API bez nutnosti složitě nastavovat Node.js/Webpack prostředí.




## 3. Co bylo nutné dodatečně upravit a ladit

* **Neshoda datových klíčů (Payload Mismatch):** * *Problém:* Worker ve zprávě od Brokera očekával klíč `object_id`, ale S3 Gateway odesílala klíč `file_id`. Výsledkem byla hodnota `None` a selhání stahování (Chyba 404).
  * *Oprava:* Úprava parsování JSON zprávy uvnitř `worker.py`, aby klíče přesně odpovídaly Pydantic schématu z `main.py`.
* **Chybějící bezpečnostní hlavičky (Auth Headers):**
  * *Problém:* První návrh Workera se snažil soubory z S3 stáhnout "naslepo". Tvůj backend ale striktně (a správně) vyžaduje hlavičku `X-User-Id`.
  * *Oprava:* Propašování uživatelského ID z API requestu přes Brokera až do Workera a následné přidání hlavičky `{"X-User-Id": user_id}`.
* **CORS preflight a přesměrování u koncových lomítek (Trailing Slash):**
  * *Problém:* Prohlížeč blokoval požadavky na S3 Gateway (chyby 307 Temporary Redirect a 405 Method Not Allowed). Důvodem byla snaha FastAPI přesměrovat frontendový dotaz bez lomítka na endpoint s lomítkem (např. /objects/), což u OPTIONS dotazů prohlížeč z bezpečnostních důvodů striktně zakazuje. K tomu byl navíc CORS middleware v kódu přidán chybně ještě před samotným vytvořením app = FastAPI().
  * *Oprava:* Sjednocení koncových lomítek mezi React fetch voláním a FastAPI routery a přesunutí bloku app.add_middleware až za inicializaci aplikace, aby mohl server správně odpovídat na ověřovací OPTIONS požadavky. Další úpravou bylo sjednocení klíčů v JSON odpovědích (frontend očekával objects, ale API vracelo files) a oprava URL pro stahování obrázků na funkční endpoint /files/{file_id}.

## 4. Integrační test (test_worker.py)

* **Příklad promptu:** *"Napište integrační test, který nasimuluje poslání 10 úloh do brokera a ověří, že Worker postupně všechny zpracuje a odešle 10 potvrzovacích zpráv. vezmi obrazky miner a skeleton ktere nahrajes na server, a na kazdy z nich das brokeru 5 uloh na operace pro workera popsane v worker.md napr grayscale, invert..."*

* **Co AI navrhla správně:**
  * Využití `pytest.mark.asyncio` pro asynchronní testování
  * Použití `asyncio.gather()` pro souběžné odesílání úloh a přijímání potvrzení
  * Upload testovacích obrázků (`miner.png`, `Skeleton.jpg`) přes S3 API před odesláním úloh
  * Odeslání 10 úloh (5 operací × 2 obrázky) na téma `image.jobs`
  * Sběr potvrzení ze tématu `image.done` přes WebSocket

* **Co bylo nutné dodatečně upravit:**
  * *Problém:* Crop operace selhala na malém obrázku (16x21 px) s parametry 10px z každé strany
  * *Oprava:* Změna crop parametrů ze 10px na 2px pro každou stranu, aby se vešly do rozměrů testovacích obrázků
  * *Problém:* Duplicitní zpracování úloh při restartu Workera (Broker ukládá zprávy do DB, Worker je nepotvrzoval)
  * *Oprava:* Přidání ACK zpráv v `worker.py` po zpracování každé úlohy (řádky 135-138 a 149-152) - Worker nyní odesílá `{"action": "ack", "message_id": message_id}`
  * *Problém:* Test se sčítal se starými zprávami v Broker DB při opakovaném spuštění
  * *Oprava:* Přidání `cleanup_broker_messages()` funkce pro mazání starých zpráv před testem (mazání z `queued_messages` tabulky)
  * *Problém:* Vytvoření bucketu s již existujícím názvem → HTTP 400
  * *Oprava:* Generování unikátního názvu bucketu s časovou značkou (`test-integration-{timestamp}`)
  * *Problém:* Test nepotvrzoval přijaté potvrzovací zprávy (image.done)
  * *Oprava:* Přidání ACK v `receive_confirmations()` funkci v testu - každá přijatá zpráva je potvrzena
  * *Problém:* Soubor `Skeleton profile picture.jpg` byl přejmenován na `Skeleton.jpg`
  * *Oprava:* Aktualizace cesty v testu na `SKELETON_IMAGE = PROJECT_ROOT / "Skeleton.jpg"`
  * *Problém:* Duplicitní zpracování úloh při restartu Workera (Broker ukládá zprávy do DB, Worker je nepotvrzoval)
  * *Oprava:* Přidání ACK zpráv v `worker.py` po zpracování každé úlohy (řádky 135-138 a 149-152)
  * *Problém:* Test se sčítal s starými zprávami v Broker DB při opakovaném spuštění
  * *Oprava:* Přidání `cleanup_broker_messages()` funkce pro mazání starých zpráv před testem
  * *Problém:* Vytvoření bucketu s již existujícím názvem → HTTP 400
  * *Oprava:* Generování unikátního názvu bucketu s časovou značkou (`test-integration-{timestamp}`)
  * *Problém:* Test nepotvrzoval přijaté potvrzovací zprávy (image.done)
  * *Oprava:* Přidání ACK v `receive_confirmations()` funkci v testu