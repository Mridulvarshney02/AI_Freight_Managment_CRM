from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    Date,
    DateTime,
    Text,
)
from sqlalchemy.sql import func

from app.database import Base

class Query(Base):
    __tablename__ = "queries"

    id = Column(Integer, primary_key=True, index=True)
    company_name = Column(String, nullable=True)
    origin_port = Column(String, nullable=True)
    destination_port = Column(String, nullable=True)
    container_type = Column(String, nullable=True)
    query_received = Column(Boolean, default=False)
    quote_shared = Column(Boolean, default=False)
    next_action = Column(String)
    next_action_date = Column(Date)
    remarks = Column(Text)
    shipment_status = Column(String)
    created_at = Column(DateTime, server_default=func.now())

    validation_status = Column(
    String,
    nullable=False,
    default="Valid"
    )
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
    )
