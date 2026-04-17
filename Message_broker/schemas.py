from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

class BrokerMessage(BaseModel):
    """
    Jednotný protokol pro všechny zprávy v našem Pub/Sub systému.
    """
    action: str = Field(
        ...,
        description="Typ akce: 'subscribe', 'publish', 'deliver' nebo 'ack'"
    )
    topic: Optional[str] = Field(
        None,
        description="Název tématu (např. 'orders', 'emails')"
    )
    message_id: Optional[int] = Field(
        None,
        description="ID zprávy (užitečné pro potvrzování - ack)"
    )
    payload: Optional[Dict[str, Any]] = Field(
        None,
        description="Samotná data zprávy (JSON objekt)"
    )