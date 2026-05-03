import asyncio
import json
import sqlite3
import time
from pathlib import Path

import pytest
import httpx
import websockets

BROKER_URL = "ws://localhost:8000/broker"
S3_API_URL = "http://localhost:8001"
BROKER_DB_PATH = Path(__file__).parent.parent / "Message_broker" / "broker.db"

PROJECT_ROOT = Path(__file__).parent.parent
MINER_IMAGE = PROJECT_ROOT / "miner.png"
SKELETON_IMAGE = PROJECT_ROOT / "Skeleton.jpg"

OPERATIONS = [
    {"operation": "invert", "params": {}},
    {"operation": "flip", "params": {}},
    {"operation": "crop", "params": {"top": 2, "bottom": 2, "left": 2, "right": 2}},
    {"operation": "brightness", "params": {"value": 50}},
    {"operation": "grayscale", "params": {}},
]


def cleanup_broker_messages():
    """Smaže staré zprávy z broker DB pro čistý stav testu."""
    if not BROKER_DB_PATH.exists():
        return
    conn = sqlite3.connect(str(BROKER_DB_PATH))
    cursor = conn.cursor()
    cursor.execute("DELETE FROM queued_messages WHERE topic IN ('image.jobs', 'image.done')")
    conn.commit()
    conn.close()


@pytest.mark.asyncio
async def test_worker_processes_10_jobs():
    """Test that Worker processes 10 jobs (5 per image) and sends 10 confirmation messages."""
    cleanup_broker_messages()

    confirmations = []

    async def receive_confirmations():
        async with websockets.connect(BROKER_URL) as ws:
            await ws.send(json.dumps({"action": "subscribe", "topic": "image.done"}))
            ack = json.loads(await ws.recv())
            assert ack["action"] == "ack"

            while len(confirmations) < 10:
                try:
                    data = json.loads(await asyncio.wait_for(ws.recv(), timeout=60))
                    if data.get("action") == "deliver":
                        confirmations.append(data["payload"])
                        # ACK zprávy, aby se nehromadily v DB
                        ack_msg = {"action": "ack", "message_id": data["message_id"]}
                        await ws.send(json.dumps(ack_msg))
                except asyncio.TimeoutError:
                    break

    async def send_jobs(miner_id, skeleton_id, bucket_id):
        async with websockets.connect(BROKER_URL) as ws:
            for op in OPERATIONS:
                for file_id in [miner_id, skeleton_id]:
                    job = {
                        "action": "publish",
                        "topic": "image.jobs",
                        "payload": {
                            "bucket_id": bucket_id,
                            "file_id": file_id,
                            "user_id": "test-user",
                            "operation": op["operation"],
                            "params": op["params"],
                        },
                    }
                    await ws.send(json.dumps(job))
                    await asyncio.sleep(0.05)

    async with httpx.AsyncClient(base_url=S3_API_URL) as s3:
        bucket_name = f"test-integration-{int(time.time())}"
        bucket_resp = await s3.post("/buckets/", json={"name": bucket_name})
        assert bucket_resp.status_code == 201, f"Bucket creation failed: {bucket_resp.status_code} - {bucket_resp.text}"
        bucket_id = bucket_resp.json()["id"]

        with open(MINER_IMAGE, "rb") as f:
            resp = await s3.post(
                "/files/upload",
                data={"bucket_id": bucket_id},
                files={"file": ("miner.png", f, "image/png")},
                headers={"X-User-Id": "test-user"},
            )
        assert resp.status_code in (200, 201)
        miner_id = resp.json()["id"]

        with open(SKELETON_IMAGE, "rb") as f:
            resp = await s3.post(
                "/files/upload",
                data={"bucket_id": bucket_id},
                files={"file": ("skeleton.jpg", f, "image/jpeg")},
                headers={"X-User-Id": "test-user"},
            )
        assert resp.status_code in (200, 201)
        skeleton_id = resp.json()["id"]

    await asyncio.gather(
        receive_confirmations(),
        send_jobs(miner_id, skeleton_id, bucket_id),
    )

    assert len(confirmations) == 10, f"Expected 10 confirmations, got {len(confirmations)}"
    for c in confirmations:
        assert c["status"] == "success", f"Expected success, got {c}"
