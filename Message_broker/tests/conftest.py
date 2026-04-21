import pytest
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


def get_ws_url():
    return "/broker"
