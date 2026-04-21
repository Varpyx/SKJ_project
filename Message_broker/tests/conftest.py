import pytest
import os
import sys
import sqlite3
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app, manager
import database
import models


@pytest.fixture(scope="session", autouse=True)
def setup_database_once():
    import os
    if os.path.exists("broker.db"):
        os.remove("broker.db")
    
    from alembic import command
    from alembic.config import Config
    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")
    yield


@pytest.fixture(autouse=True)
def reset_manager():
    manager.active_connections.clear()
    yield
    manager.active_connections.clear()


@pytest.fixture(autouse=True)
def clean_db_tables():
    db = database.SessionLocal()
    try:
        db.query(models.QueuedMessage).delete()
        db.commit()
    finally:
        db.close()
    yield


@pytest.fixture
def client():
    return TestClient(app)


def get_ws_url():
    return "/broker"
