# Worker předpokládá, že na portu 8000 běží Message Broker a na portu 8001 běží S3 Gateway.


python worker.py

# 🖼️ Dokumentace NumPy operací
## 1. Inverze (invert)

Vypočítá barevný negativ odečtením hodnot od maximální intenzity (255).

    Kód: new_array = 255 - img_array

## 2. Zrcadlové překlopení (flip)

Využívá slicing matice k obrácení pořadí sloupců.

    Kód: img_array[:, ::-1, :]

## 3. Ořez (crop)

Ořízne okraje matice podle zadaných pixelů. Pokud je ořez větší než rozměr obrázku, worker vrátí chybovou zprávu.

    Parametry: top, bottom, left, right (v pixelech).

## 4. Úprava jasu (brightness)

Zvýší nebo sníží intenzitu barev.

    Saturace: Využívá np.clip(..., 0, 255), aby nedošlo k barevnému přetečení (overflow) při překročení limitů 8-bitového kódování.

    Parametr: value (např. 50 pro zesvětlení, -30 pro ztmavení).

## 5. Černobílý filtr (grayscale)

Převede RGB matici na matici jasu (Grayscale) pomocí váženého průměru (Luma transformace):

    Vzorec: 0.299*R + 0.587*G + 0.114*B

## 📡 Komunikační protokol

Worker očekává zprávu typu publish v tématu image.jobs s následujícím payloadem:
JSON

{
  "bucket_id": 1,
  "file_id": "uuid-souboru",
  "user_id": "anonymous",
  "operation": "invert",
  "params": {}
}

# Jak to celé zapnout (3 terminály)

Otevři si ve svém editoru nebo systému tři samostatné terminály. V každém z nich se ujisti, že máš aktivované virtuální prostředí (uvidíš před cestou nápis (.venv)).

## Terminál 1: Message Broker
Tady běží centrála, která přeposílá zprávy.
Bash

cd Message_broker
uvicorn main:app --port 8000

## Terminál 2: S3 Gateway (Tvoje API)
Tady běží tvůj webový server, kam se připojují uživatelé.
Bash

cd Rest_Api
uvicorn main:app --port 8001

## Terminál 3: Image Worker
Tady běží ten nenápadný dělník, co dělá tu těžkou matematiku.
Bash

cd Worker
python worker.py

# Jak posílat příkazy

Otevři si prohlížeč a jdi na dokumentaci své S3 Gateway: 👉 http://127.0.0.1:8001/docs

Najdi endpoint POST /buckets/{bucket_id}/objects/{file_id}/process.

Do políček vyplň:

    bucket_id: (např. 1)

    file_id: (ten dlouhý kód, např. f4a6b2c7-...)

    x-user-id: (např. anonymous)

Do velkého pole Request body vložíš jeden z těch JSON kódů níže podle toho, co chceš s fotkou udělat.

## 3. JSON parametry pro různé režimy

Tady jsou přesné JSON bloky, které stačí zkopírovat a vložit do Request body ve Swaggeru.

### Režim 1: Inverze (Negativ)
Obrátí všechny barvy (udělá negativ). Nepotřebuje žádné parametry.
JSON

{
  "operation": "invert",
  "params": {}
}

### Režim 2: Zrcadlo (Flip)
Překlopí obrázek horizontálně. Nepotřebuje žádné parametry.
JSON

{
  "operation": "flip",
  "params": {}
}

### Režim 3: Černobílý filtr (Grayscale)
Udělá z barevné fotky černobílou. Nepotřebuje žádné parametry.
JSON

{
  "operation": "grayscale",
  "params": {}
}

### Režim 4: Ořez (Crop)
Odřízne zadaný počet pixelů z každé strany. V objektu params musíš uvést, kolik chceš uříznout. (Pozor: Součet odříznutých pixelů nesmí být větší než samotná fotka!)
JSON

{
  "operation": "crop",
  "params": {
    "top": 100,
    "bottom": 100,
    "left": 150,
    "right": 150
  }
}

### Režim 5: Jas (Brightness)
Zesvětlí nebo ztmaví fotku. V objektu params posíláš klíč value.

    Zesvětlení (kladné číslo):

JSON

{
  "operation": "brightness",
  "params": {
    "value": 60
  }
}

    Ztmavení (záporné číslo):
JSON

{
  "operation": "brightness",
  "params": {
    "value": -40
  }
}

# 🧪 Integrační test

Test ověří, že Worker zpracuje 10 úloh (5 operací na 2 obrázky) a odešle 10 potvrzovacích zpráv.

## Požadavky
- Broker běží na portu 8000
- S3 Gateway běží na portu 8001
- Worker je spuštěn a připojen k brokerovi (s ACK mechanismem)

## Spuštění testu

```bash
# Terminál 1: Broker
cd Message_broker && uvicorn main:app --port 8000

# Terminál 2: S3 Gateway
cd Rest_Api && uvicorn main:app --port 8001

# Terminál 3: Worker
cd Worker && python worker.py

# Terminál 4: Test
cd Worker && pytest test_worker.py -v
```

## Co test dělá
1. Vyčistí staré zprávy z Broker DB (`cleanup_broker_messages()`)
2. Vytvoří testovací bucket s unikátním názvem přes S3 API
3. Nahraje `miner.png` a `Skeleton.jpg` do S3
4. Odešle 10 úloh na téma `image.jobs` (operace: invert, flip, crop, brightness, grayscale)
5. Souběžně sbírá potvrzení ze tématu `image.done` a odesílá ACK
6. Ověří, že přišlo přesně 10 potvrzení se statusem "success"

## Testované operace
- `invert` - negativ
- `flip` - horizontální překlopení
- `crop` - ořez (2px z každé strany)
- `brightness` - úprava jasu (value: 50)
- `grayscale` - černobílý filtr

## Důležité implementační detaily
- **ACK mechanismus:** Worker nyní potvrzuje přijetí zpráv z brokera (řádky 135-138, 149-152 v worker.py)
- **Čištění DB:** Před každým testem se mažou staré zprávy z `queued_messages` tabulky
- **Unikátní bucket:** Název bucketu obsahuje timestamp pro zamezení kolizí
- **Worker ukončení:** `KeyboardInterrupt` (Ctrl+C) je normální způsob ukončení Workera

## Známé problémy a řešení
- **Chyba `AssertionError` na bucket vytvoření:** Příčinou je duplicitní název bucketu → řešení: timestamp v názvu
- **Worker zpracovává úlohy i bez testu:** Příčinou je chybějící ACK → řešení: Worker nyní odesílá ACK
- **Test selže s více než 10 potvrzeními:** Příčinou jsou staré zprávy v DB → řešení: `cleanup_broker_messages()`
}

