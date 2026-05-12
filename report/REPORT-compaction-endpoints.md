# Report: Volume kompakce + přejmenování endpointů

## 1. Nový admin endpoint — seznam objektů ve svazku

**Soubor:** `Rest_Api/main.py`
**Endpoint:** `GET /admin/volume/{volume_id}/objects`
**Účel:** Vrátí všechny nesmazané soubory v daném svazku, seřazené podle offsetu.

```bash
curl -s http://localhost:8001/admin/volume/1/objects | python3 -m json.tool
```

Odpověď:
```json
[
  {
    "file_id": "uuid-souboru",
    "offset": 0,
    "size": 12345,
    "volume_id": 1
  }
]
```

---

## 2. Nový admin endpoint — relokace offsetu

**Soubor:** `Rest_Api/main.py`
**Endpoint:** `PUT /admin/objects/{file_id}/relocate?new_offset=<int>`
**Účel:** Aktualizuje offset souboru v DB po přesunu v rámci kompakce.

```bash
curl -s -X PUT "http://localhost:8001/admin/objects/uuid-souboru/relocate?new_offset=0"
```

---

## 3. Kompakční skript — `Haystack_Node/compact.py`

**Účel:** Provede defragmentaci volume souboru — odstraní "díry" po smazaných souborech.

**Algoritmus:**
1. Zavolá `GET /admin/volume/{id}/objects` → získá aktivní soubory
2. Pokud je svazek prázdný → smaže volume soubor
3. Pro každý soubor: přečte data ze starého souboru, zapíše těsně za sebe do nového
4. Po každém zápisu zavolá `PUT /admin/objects/{id}/relocate` s novým offsetem
5. Smaže starý soubor, přejmenuje nový na původní název

**Spuštění:**
```bash
cd Haystack_Node && source ../venv/bin/activate && python compact.py 1
```

**Příklad výstupu:**
```
🔍 Kompaktuji volume 1...
✅ Volume 1 zkompaktován: 1024000B → 850000B (ušetřeno 174000B)
```

---

## 4. Schéma VolumeObjectInfo

**Soubor:** `Rest_Api/schemas.py`, třída `VolumeObjectInfo`

Používá `from_attributes = True`, takže vrací data přímo z SQLAlchemy modelu.

---

## 5. Přejmenování endpointů pro download a delete

| Původní | Nový |
|---|---|
| `GET /files/{file_id}` | `GET /download/{object_id}` |
| `DELETE /files/{file_id}` | `DELETE /download/{object_id}` |

**Ovlivněné soubory:**
- `Worker/worker.py` — stažení obrázku pro zpracování
- `Worker/image-gallery.html` — stažení obrázku pro náhled
- `Rest_Api/restapi.http` — testovací requesty

**Ne změněno:**
- `POST /files/upload` (nahrávání)
- `GET /files` (výpis souborů)

**Použití:**
```bash
# Stažení
curl -s "http://localhost:8001/download/uuid-souboru" -H "X-User-Id: user" -o soubor.jpg

# Smazání (soft delete)
curl -s -X DELETE "http://localhost:8001/download/uuid-souboru" -H "X-User-Id: user"
```

---

## 6. Testování kompakce (end-to-end)

**Předpoklad:** Běží Broker (8000), S3 Gateway (8001), Haystack Node (8002).

```bash
# 1. Vytvoř bucket a nahraj 2 soubory
curl -s -X POST http://localhost:8001/buckets/ -H "Content-Type: application/json" \
  -d '{"name": "test-compact"}' | python3 -m json.tool

# ID bucketu si zapamatuj (např. 1)

curl -s -X POST http://localhost:8001/files/upload -H "X-User-Id: test" \
  -F "file=@miner.png" -F "bucket_id=1" | python3 -m json.tool
# → získej file_id_1

curl -s -X POST http://localhost:8001/files/upload -H "X-User-Id: test" \
  -F "file=@Skeleton.jpg" -F "bucket_id=1" | python3 -m json.tool
# → získej file_id_2

# 2. Ověř, že endpoint vrací 2 objekty
curl -s http://localhost:8001/admin/volume/1/objects | python3 -m json.tool

# 3. Smaž jeden soubor (soft delete)
curl -s -X DELETE "http://localhost:8001/download/file_id_1" -H "X-User-Id: test"

# 4. Ověř, že admin endpoint vrací už jen 1 objekt
curl -s http://localhost:8001/admin/volume/1/objects | python3 -m json.tool

# 5. Zkontroluj velikost volume před kompakcí
ls -la Haystack_Node/volumes/

# 6. Spusť kompakci
cd Haystack_Node && source ../venv/bin/activate && python compact.py 1

# 7. Ověř zmenšení volume
ls -la Haystack_Node/volumes/

# 8. Ověř stažení zbývajícího souboru
curl -s "http://localhost:8001/download/file_id_2" -H "X-User-Id: test" -o /tmp/test.jpg
ls -la /tmp/test.jpg
```
