import os
import re
import sys
import httpx

S3_GATEWAY = "http://127.0.0.1:8001"
VOLUMES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "volumes")
MAX_VOLUME_BYTES = 3 * 1024 * 1024  # odpovídá max_size_mb=3 v main.py


def get_all_volume_ids() -> list[int]:
    ids = []
    pat = re.compile(r"^volume_(\d+)\.dat$")
    for f in os.listdir(VOLUMES_DIR):
        m = pat.match(f)
        if m:
            ids.append(int(m.group(1)))
    return sorted(ids)


def volume_path(volume_id: int) -> str:
    return os.path.join(VOLUMES_DIR, f"volume_{volume_id}.dat")


def compact_volume(volume_id: int):
    print(f"🔍 Kompaktuji volume {volume_id}...")

    old_path = volume_path(volume_id)
    new_path = os.path.join(VOLUMES_DIR, f"volume_{volume_id}_compacted.dat")

    if not os.path.exists(old_path):
        print(f"❌ Volume soubor neexistuje: {old_path}")
        return

    old_size = os.path.getsize(old_path)

    resp = httpx.get(
        f"{S3_GATEWAY}/admin/volume/{volume_id}/objects",
        timeout=30,
    )
    resp.raise_for_status()
    files = resp.json()

    if not files:
        os.remove(old_path)
        httpx.delete(f"{S3_GATEWAY}/admin/volume/{volume_id}/purge", timeout=10)
        print(f"🗑️ Volume {volume_id} je prázdný — smazán.")
        return

    new_offset = 0
    with open(old_path, "rb") as old_f, open(new_path, "wb") as new_f:
        for f in files:
            file_id = f["file_id"]
            size = f["size"]
            old_offset = f["offset"]

            old_f.seek(old_offset)
            data = old_f.read(size)

            new_f.write(data)

            resp = httpx.put(
                f"{S3_GATEWAY}/admin/objects/{file_id}/relocate",
                params={"new_offset": new_offset},
                timeout=10,
            )
            resp.raise_for_status()

            new_offset += size

    os.remove(old_path)
    # ABY VYTVOŘIL COMPACTED FILE ZAKOMETOVAT!
    os.rename(new_path, old_path) 

    new_size = os.path.getsize(old_path)
    saved = old_size - new_size
    httpx.delete(f"{S3_GATEWAY}/admin/volume/{volume_id}/purge", timeout=10)
    print(f"✅ Volume {volume_id} zkompaktován: {old_size}B → {new_size}B (ušetřeno {saved}B)")


def delete_volume_if_empty(volume_id: int):
    resp = httpx.get(f"{S3_GATEWAY}/admin/volume/{volume_id}/objects", timeout=30)
    if resp.status_code == 200 and not resp.json():
        os.remove(volume_path(volume_id))
        httpx.delete(f"{S3_GATEWAY}/admin/volume/{volume_id}/purge", timeout=10)
        print(f"🗑️ Volume {volume_id} smazán (prázdný)")


def move_files_to_fill(src_volume_id: int, dst_volume_id: int, max_bytes: int) -> int:
    src_path = volume_path(src_volume_id)
    dst_path = volume_path(dst_volume_id)
    if not os.path.exists(src_path):
        return max_bytes

    resp = httpx.get(f"{S3_GATEWAY}/admin/volume/{src_volume_id}/objects", timeout=30)
    resp.raise_for_status()
    files = resp.json()
    if not files:
        return max_bytes

    dst_size = os.path.getsize(dst_path)
    remaining = max_bytes

    with open(src_path, "rb") as src_f, open(dst_path, "ab") as dst_f:
        new_offset = dst_size
        for f in files:
            if f["size"] > remaining:
                break
            src_f.seek(f["offset"])
            data = src_f.read(f["size"])
            dst_f.write(data)
            httpx.put(
                f"{S3_GATEWAY}/admin/objects/{f['file_id']}/relocate",
                params={"new_offset": new_offset, "new_volume_id": dst_volume_id},
                timeout=10,
            ).raise_for_status()
            print(f"  📦 Přesunut {f['file_id']} ({f['size']}B) z volume {src_volume_id} do {dst_volume_id}")
            new_offset += f["size"]
            remaining -= f["size"]

    return remaining


if __name__ == "__main__":
    orig_ids = get_all_volume_ids()
    if not orig_ids:
        print("⚠️  Žádné svazky ke kompakci.")
        sys.exit(0)

    for i, vid in enumerate(orig_ids):
        if not os.path.exists(volume_path(vid)):
            continue
        compact_volume(vid)

        remaining = MAX_VOLUME_BYTES - os.path.getsize(volume_path(vid))
        if remaining <= 0:
            continue

        for src_id in orig_ids[i + 1:]:
            if remaining <= 0:
                break
            if not os.path.exists(volume_path(src_id)):
                continue
            remaining = move_files_to_fill(src_id, vid, remaining)
            delete_volume_if_empty(src_id)
