# AI Report: Transformace na Haystack Architekturu

**Co jsme použili za AI**
* Gemini

**Příklad promptu**
* **Architektonický (Zadání):** *"Máme udělat toto: Úkol 1: Haystack Storage Node (Zápis a Čtení) Vytvořte novou FastAPI aplikaci. Její hlavní zodpovědností je rychlý asynchronní zápis dat... step by step chci jít po těch jednotlivých bodech."*
* **Ladící (Debugging):** *"ERROR: Exception in ASGI application... pydantic_core._pydantic_core.ValidationError: 1 validation error for FileUploadResponse filename String should match pattern..."*

**Co AI udělalo dobře**
* **Strukturování problému:** Komplexní zadání (architekturu Facebooku) jsem rozpadl na stravitelné kroky – nejdřív jsme napsali samotný motor pro zápis na disk (`HaystackManager`), pak připojení na Brokera a až nakonec úpravu API.
* **Diagnostika asynchronních pastí:** Rychle jsem identifikoval skrytý systémový problém typu *Race Condition* (Závod o data), kdy Worker žádal o soubor dříve, než se zapsal, a navrhl jsem elegantní řešení pomocí asynchronního čekání (polling).

**Co AI udělalo špatně**
* **Nedůslednost při refaktoringu (Opuštěný kód):** Když jsme mazali atribut `path` z databáze, zapomněl jsem tě v prvním kroku upozornit, ať ho smažeš i z generování výpisů v `main.py`, což ti následně shodilo server na chybu 500.
* **Podcenění striktnosti Pydanticu:** Měl jsem už při návrhu předvídat, že uživatelé budou nahrávat soubory se závorkami (např. `fotka(5).jpg`), a rovnou tě upozornit na úpravu regulárního výrazu. Stejně tak jsem zpočátku opomněl přidat nová pole `volume_id` a `offset` do výstupních schémat, takže jsi je neviděl v odpovědi.