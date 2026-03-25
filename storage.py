"""
storage.py – Logika práce se souborovým systémem

Tento modul řeší fyzické ukládání souborů na disk.
Je záměrně oddělený od API logiky (main.py), aby bylo snadné
vyměnit backend (např. místo lokálního disku použít S3/MinIO).

Struktura adresářů na disku:
    storage/
    ├── user_alice/
    │   ├── 3f2a1b4c-...   ← fyzický soubor (bez přípony, identifikován UUID)
    │   └── 9e8d7c6b-...
    └── user_bob/
        └── 1a2b3c4d-...
"""

import os
import uuid

import aiofiles  # asynchronní čtení/zápis souborů (neblokuje event loop)

# ---------------------------------------------------------------------------
# Kořenový adresář úložiště
# ---------------------------------------------------------------------------
# Všechny soubory budou uloženy pod tímto adresářem.
# Lze přepsat env proměnnou STORAGE_ROOT pro flexibilitu.
STORAGE_ROOT = os.environ.get("STORAGE_ROOT", "storage")


def ensure_user_directory(user_id: str) -> str:
    """
    Zajistí existenci adresáře pro daného uživatele.

    Pokud adresář neexistuje, vytvoří ho (včetně STORAGE_ROOT).
    Vrátí cestu k adresáři uživatele.

    Příklad:
        ensure_user_directory("alice") → "storage/alice"
    """
    # Sestavíme cestu: storage/<user_id>
    user_dir = os.path.join(STORAGE_ROOT, user_id)

    # exist_ok=True → nevyhodí chybu, pokud adresář už existuje
    os.makedirs(user_dir, exist_ok=True)

    return user_dir


def generate_file_id() -> str:
    """
    Vygeneruje unikátní identifikátor souboru jako UUID4 string.

    UUID4 je náhodně generovaný – pravděpodobnost kolize je astronomicky malá
    (cca 1 ku 5,3 × 10^36). Používáme ho jako název souboru na disku
    i jako veřejný identifikátor v API.

    Příklad výstupu: "550e8400-e29b-41d4-a716-446655440000"
    """
    return str(uuid.uuid4())


def get_file_path(user_id: str, file_id: str) -> str:
    """
    Sestaví a vrátí absolutní cestu k souboru na disku.

    Parametry:
        user_id – identifikátor uživatele (slouží jako název adresáře)
        file_id – UUID souboru (slouží jako název souboru)

    Příklad:
        get_file_path("alice", "550e8400-...") → "storage/alice/550e8400-..."
    """
    return os.path.join(STORAGE_ROOT, user_id, file_id)


async def save_file(user_id: str, file_id: str, file_content: bytes) -> tuple[str, int]:
    """
    Asynchronně uloží binární obsah souboru na disk.

    Asynchronní operace (async/await) jsou důležité pro FastAPI – nezablokují
    event loop při čekání na I/O operace (zápis na disk, síť...).
    'aiofiles' zajišťuje, že zápis probíhá asynchronně.

    Parametry:
        user_id      – identifikátor uživatele
        file_id      – UUID souboru (bude název souboru na disku)
        file_content – binární obsah souboru (bytes)

    Vrátí:
        tuple (cesta_k_souboru, velikost_v_bytech)
    """
    # 1) Zajisti existenci adresáře pro uživatele
    ensure_user_directory(user_id)

    # 2) Urči cílovou cestu
    file_path = get_file_path(user_id, file_id)

    # 3) Asynchronně zapiš obsah souboru
    # "wb" = write binary (binární zápis – funguje pro text i obrázky i PDF)
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(file_content)

    # 4) Vrať cestu a skutečnou velikost zapsaného souboru
    file_size = os.path.getsize(file_path)
    return file_path, file_size


async def read_file(file_path: str) -> bytes:
    """
    Asynchronně načte obsah souboru z disku.

    Parametry:
        file_path – cesta k souboru (uložená v DB)

    Vrátí:
        bytes – binární obsah souboru

    Vyhodí:
        FileNotFoundError – pokud soubor na disku neexistuje
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Soubor nenalezen na disku: {file_path}")

    async with aiofiles.open(file_path, "rb") as f:
        return await f.read()


def delete_file_from_disk(file_path: str) -> bool:
    """
    Smaže soubor z disku.

    Parametry:
        file_path – cesta k souboru

    Vrátí:
        True  – soubor byl úspěšně smazán
        False – soubor na disku nebyl nalezen (DB záznam ale mohl existovat)
    """
    if os.path.exists(file_path):
        os.remove(file_path)
        return True
    return False
