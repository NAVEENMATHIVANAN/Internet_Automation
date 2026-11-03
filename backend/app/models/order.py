
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, DateTime, JSON
from app.database import Base


class Order(Base):
    __tablename__ = "orders"

    id = Column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    order_id = Column(
        String,
        unique=True,
        nullable=False,
        default=lambda: f"ORD-{uuid.uuid4().hex[:12].upper()}"
    )

    customer_data = Column(JSON, nullable=False)
    service_address = Column(JSON, nullable=False)
    order_data = Column(JSON, nullable=False)
    qualification = Column(JSON, nullable=False)
    installation = Column(JSON, nullable=False)
    disclosures = Column(JSON, nullable=False)

    status = Column(
        String,
        nullable=False,
        default="RECEIVED"
    )

    automation_status = Column(
        String,
        nullable=False,
        default="PENDING"
    )

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
