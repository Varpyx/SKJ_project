import asyncio
import json
from pathlib import Path

import pytest
import httpx
import websockets

BROKER_URL = "ws://localhost:8000/broker"
S3_API_URL = "http://localhost:8001"

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


@pytest.mark.asyncio
async def test_worker_processes_10_jobs():
    """Test that Worker processes 10 jobs (5 per image) and sends 10 confirmation messages."""
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
        bucket_resp = await s3.post("/buckets/", json={"name": "test-integration"})
        assert bucket_resp.status_code == 201
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
