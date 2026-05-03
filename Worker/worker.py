import asyncio
import io
import json
import os
import websockets
import httpx
import numpy as np
from PIL import Image

BROKER_URI = os.getenv("BROKER_URL", "ws://localhost:8000/broker")
S3_API_URL = "http://localhost:8001"  # Předpokládáme, že tvá S3 běží na portu 8001


async def process_image_numpy(image_bytes: bytes, operation: str, params: dict) -> bytes:
    """Provede transformaci obrázku čistě pomocí NumPy matic."""
    # Otevření obrázku přes Pillow a převod na NumPy pole (3D matice: Výška x Šířka x RGB)
    with Image.open(io.BytesIO(image_bytes)) as img:
        # Převedeme na RGB, kdyby to bylo např. PNG s průhledností (RGBA)
        img = img.convert('RGB')
        arr = np.array(img)

    # 1. INVERZE (Negativ)
    if operation == "invert":
        new_array = 255 - arr

    # 2. HORIZONTÁLNÍ PŘEKLOPENÍ (Zrcadlo)
    elif operation == "flip":
        new_array = arr[:, ::-1, :]

    # 3. OŘEZ (Crop)
    elif operation == "crop":
        # Z parametrů vytáhneme, kolik pixelů chceme odříznout (výchozí 0)
        top = params.get("top", 100)
        bottom = params.get("bottom", 100)
        left = params.get("left", 100)
        right = params.get("right", 100)

        h, w = arr.shape[:2]
        if top + bottom >= h or left + right >= w:
            raise ValueError(f"Ořez je mimo dimenze obrazu (rozlišení: {w}x{h}).")

        new_array = arr[top:h - bottom, left:w - right, :]

    # 4. ÚPRAVA JASU (Zesvětlení / Ztmavení)
    elif operation == "brightness":
        value = params.get("value", 50)
        # Převod na int16, aby nedošlo k přetečení (overflow)
        temp_array = arr.astype(np.int16) + value
        # Ořezání hodnot mimo rozsah 0-255 a převod zpět na uint8
        new_array = np.clip(temp_array, 0, 255).astype(np.uint8)

    # 5. ČERNOBÍLÝ FILTR (Grayscale)
    elif operation == "grayscale":
        # Rozdělení na kanály R, G, B
        R, G, B = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
        # Vážený průměr podle citlivosti lidského oka
        gray_array = 0.299 * R + 0.587 * G + 0.114 * B
        # Převod zpět na uint8. Výsledek je 2D pole (jen jas)
        new_array = gray_array.astype(np.uint8)

    else:
        raise ValueError(f"Neznámá operace: {operation}")

    # Převod NumPy pole zpět na obrázek a uložení do paměti (bytes)
    # U grayscale je mode 'L' (jas), u barevných 'RGB'
    mode = 'L' if operation == "grayscale" else 'RGB'
    result_img = Image.fromarray(new_array, mode=mode)

    out_io = io.BytesIO()
    result_img.save(out_io, format="JPEG")
    return out_io.getvalue()


async def worker_loop():
    print("🚀 Image Worker se spouští...")

    async with websockets.connect(BROKER_URI) as ws:
        # Přihlášení k odběru úloh
        sub_msg = {"action": "subscribe", "topic": "image.jobs"}
        await ws.send(json.dumps(sub_msg))
        print("✅ Naslouchám na tématu 'image.jobs'...")

        async with httpx.AsyncClient() as client:
            while True:
                try:
                    response = await ws.recv()
                    data = json.loads(response)

                    if data.get("action") != "deliver":
                        continue

                    message_id = data.get("message_id")
                    payload = data.get("payload", {})
                    bucket_id = payload.get("bucket_id")
                    file_id = payload.get("file_id")  # ZMĚNA: Hledáme file_id
                    user_id = payload.get("user_id", "anonymous")  # ZMĚNA: Potřebujeme user_id pro stažení
                    operation = payload.get("operation")
                    params = payload.get("params", {})

                    print(f"\n📥 Přijat job: {operation} na souboru {file_id} (Kbelík: {bucket_id})")

                    # 1. Stáhneme obrázek ze S3 (Použijeme správný endpoint /files/{file_id} a hlavičku)
                    headers = {"X-User-Id": user_id}
                    s3_download_url = f"{S3_API_URL}/files/{file_id}"
                    img_resp = await client.get(s3_download_url, headers=headers)

                    if img_resp.status_code != 200:
                        raise Exception(f"Obrázek se nepodařilo stáhnout. HTTP {img_resp.status_code}")

                    # 2. Provedeme NumPy operaci
                    processed_bytes = await process_image_numpy(img_resp.content, operation, params)

                    # 3. Nahrajeme výsledek zpět do S3 přes /files/upload
                    upload_data = {"bucket_id": bucket_id}
                    files = {'file': (f"processed_{file_id}.jpg", processed_bytes, "image/jpeg")}

                    # Přidáme hlavičku, aby S3 věděla, že jde o interní zpracování (neúčtuje se uživateli za Ingress)
                    headers["X-Internal-Source"] = "true"

                    upload_resp = await client.post(f"{S3_API_URL}/files/upload", data=upload_data, files=files,
                                                    headers=headers)

                    if upload_resp.status_code not in (200, 201):
                        raise Exception(f"Nepodařilo se nahrát upravený obrázek. HTTP {upload_resp.status_code}")

                    # 4. Odešleme zprávu o úspěchu
                    print("✅ Hotovo! Odesílám zprávu o dokončení.")
                    done_msg = {
                        "action": "publish",
                        "topic": "image.done",
                        "payload": {"status": "success", "file_id": file_id, "operation": operation}
                    }
                    await ws.send(json.dumps(done_msg))

                    # 5. Potvrdíme přijetí zprávy z brokera (ACK)
                    if message_id:
                        ack_msg = {"action": "ack", "message_id": message_id}
                        await ws.send(json.dumps(ack_msg))

                except Exception as e:
                    print(f"❌ Chyba při zpracování: {str(e)}")
                    # Odešleme chybovou zprávu
                    error_msg = {
                        "action": "publish",
                        "topic": "image.done",
                        "payload": {"status": "error", "message": str(e)}
                    }
                    await ws.send(json.dumps(error_msg))

                    # Potvrdíme přijetí zprávy z brokera i při chybě (ACK)
                    if message_id:
                        ack_msg = {"action": "ack", "message_id": message_id}
                        await ws.send(json.dumps(ack_msg))


if __name__ == "__main__":
    asyncio.run(worker_loop())