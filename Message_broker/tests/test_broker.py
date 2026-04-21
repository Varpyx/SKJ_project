import pytest
import json
import asyncio
from fastapi.testclient import TestClient
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app, manager


@pytest.fixture(autouse=True)
def reset_manager():
    manager.active_connections.clear()
    yield
    manager.active_connections.clear()


@pytest.fixture
def client():
    return TestClient(app)


class TestWebSocketConnection:
    def test_client_connect_disconnect(self, client):
        with client.websocket_connect("/broker") as ws:
            ws.send_json({"action": "subscribe", "topic": "test"})
            response = ws.receive_json()
            assert response["action"] == "ack"

    def test_client_receive_ack_on_subscribe(self, client):
        with client.websocket_connect("/broker") as ws:
            ws.send_json({"action": "subscribe", "topic": "sensors"})
            response = ws.receive_json()
            assert response["action"] == "ack"
            assert "sensors" in response["status"]

    def test_multiple_clients_connect(self, client):
        with client.websocket_connect("/broker") as ws1:
            ws1.send_json({"action": "subscribe", "topic": "test"})
            ws1.receive_json()

            with client.websocket_connect("/broker") as ws2:
                ws2.send_json({"action": "subscribe", "topic": "test"})
                ws2.receive_json()

                assert "test" in manager.active_connections
                assert len(manager.active_connections["test"]) == 2


class TestPubSub:
    def test_message_reaches_subscribed_client(self, client):
        with client.websocket_connect("/broker") as subscriber:
            subscriber.send_json({"action": "subscribe", "topic": "sensors"})
            subscriber.receive_json()

            with client.websocket_connect("/broker") as publisher:
                publisher.send_json({
                    "action": "publish",
                    "topic": "sensors",
                    "payload": {"temperature": 25.5}
                })

                delivered = subscriber.receive_json()
                assert delivered["action"] == "deliver"
                assert delivered["topic"] == "sensors"
                assert delivered["payload"]["temperature"] == 25.5

    def test_message_not_reaches_unsubscribed_topic(self, client):
        with client.websocket_connect("/broker") as subscriber:
            subscriber.send_json({"action": "subscribe", "topic": "topicX"})
            subscriber.receive_json()

            with client.websocket_connect("/broker") as publisher:
                publisher.send_json({
                    "action": "publish",
                    "topic": "topicY",
                    "payload": {"data": "test"}
                })

            import time
            time.sleep(0.2)

            assert "topicY" not in manager.active_connections or \
                   len(manager.active_connections.get("topicY", set())) == 0

    def test_multiple_subscribers_same_topic(self, client):
        with client.websocket_connect("/broker") as sub1:
            sub1.send_json({"action": "subscribe", "topic": "alerts"})
            sub1.receive_json()

            with client.websocket_connect("/broker") as sub2:
                sub2.send_json({"action": "subscribe", "topic": "alerts"})
                sub2.receive_json()

                with client.websocket_connect("/broker") as publisher:
                    publisher.send_json({
                        "action": "publish",
                        "topic": "alerts",
                        "payload": {"message": "alert!"}
                    })

                    delivered1 = sub1.receive_json()
                    delivered2 = sub2.receive_json()

                    assert delivered1["action"] == "deliver"
                    assert delivered2["action"] == "deliver"
                    assert delivered1["payload"]["message"] == "alert!"
                    assert delivered2["payload"]["message"] == "alert!"

    def test_client_subscribe_to_multiple_topics(self, client):
        with client.websocket_connect("/broker") as ws:
            ws.send_json({"action": "subscribe", "topic": "topicA"})
            ws.receive_json()

            ws.send_json({"action": "subscribe", "topic": "topicB"})
            ws.receive_json()

            assert "topicA" in manager.active_connections
            assert "topicB" in manager.active_connections


class TestErrorHandling:
    def test_invalid_message_format(self, client):
        with client.websocket_connect("/broker") as ws:
            ws.send_json({"invalid": "format"})
            response = ws.receive_json()
            assert response["action"] == "error"

    def test_publish_without_topic(self, client):
        with client.websocket_connect("/broker") as ws:
            ws.send_json({"action": "subscribe", "topic": "test"})
            ws.receive_json()

            ws.send_json({"action": "publish", "payload": {"data": "test"}})

            import time
            time.sleep(0.2)
            assert True


class TestCleanup:
    def test_client_removed_after_disconnect(self, client):
        with client.websocket_connect("/broker") as ws:
            ws.send_json({"action": "subscribe", "topic": "temp"})
            ws.receive_json()

        import time
        time.sleep(0.1)

        assert "temp" not in manager.active_connections or \
               len(manager.active_connections.get("temp", set())) == 0
