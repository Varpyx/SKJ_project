"""
models.py – SQLAlchemy modely pro Message Broker

Databázové modely pro perzistentní ukládání zpráv.
"""

from datetime import datetime

from sqlalchemy import String, LargeBinary, Boolean, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class QueuedMessage(Base):
    """
    Tabulka 'queued_messages' – perzistentní fronta zpráv.

    Sloupce:
    --------
    id          – primární klíč (autoincrement integer)
    topic       – název tématu (např. 'sensors', 'orders')
    payload     – serializovaná data zprávy (MessagePack jako BLOB)
    created_at  – čas vytvoření zprávy
    is_delivered – příznak doručení (False = čeká na ACK)
    """
    __tablename__ = "queued_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    topic: Mapped[str] = mapped_column(String, index=True)
    payload: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    is_delivered: Mapped[bool] = mapped_column(Boolean, default=False)

    def __repr__(self) -> str:
        return f"<QueuedMessage id={self.id} topic={self.topic!r} delivered={self.is_delivered}>"