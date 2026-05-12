import os
import sys
import httpx

S3_GATEWAY = "http://127.0.0.1:8001"
VOLUMES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "volumes")


def compact_volume(volume_id: int):
    print(f"🔍 Kompaktuji volume {volume_id}...")

    old_path = os.path.join(VOLUMES_DIR, f"volume_{volume_id}.dat")
    new_path = os.path.join(VOLUMES_DIR, f"volume_{volume_id}_compacted.dat")

    if not os.path.exists(old_path):
        print(f"❌ Volume soubor neexistuje: {old_path}")
        sys.exit(1)

    old_size = os.path.getsize(old_path)

    resp = httpx.get(
        f"{S3_GATEWAY}/admin/volume/{volume_id}/objects",
        timeout=30,
    )
    resp.raise_for_status()
    files = resp.json()

    if not files:
        os.remove(old_path)
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
    #os.rename(new_path, old_path) ABY VYTVOŘIL COMPACTED FILE ZAKOMETOVAT!

    new_size = os.path.getsize(old_path)
    saved = old_size - new_size
    print(f"✅ Volume {volume_id} zkompaktován: {old_size}B → {new_size}B (ušetřeno {saved}B)")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Použití: python compact.py <volume_id>")
        sys.exit(1)
    compact_volume(int(sys.argv[1]))
