from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class BrokerMessage(BaseModel):
    """
    Jednotný protokol pro všechny zprávy v Pub/Sub systému.

    Příklady zpráv:
    -------------
    1. Publisher posílá zprávu:
       {"action": "publish", "topic": "sensors", "payload": {"temp": 22.5}}

    2. Broker posílá zprávu Subscriberovi (s DB ID):
       {"action": "deliver", "topic": "sensors", "message_id": 42, "payload": {...}}

    3. Subscriber potvrzuje přijetí:
       {"action": "ack", "message_id": 42}
    """
    action: str = Field(
        ...,
        description="Typ akce: 'subscribe', 'publish', 'deliver' nebo 'ack'"
    )
    topic: Optional[str] = Field(
        None,
        description="Název tématu (např. 'sensors', 'orders')"
    )
    message_id: Optional[int] = Field(
        None,
        description="ID zprávy z databáze (pro ACK potvrzení)"
    )
    payload: Optional[Dict[str, Any]] = Field(
        None,
        description="Samotná data zprávy"
    )