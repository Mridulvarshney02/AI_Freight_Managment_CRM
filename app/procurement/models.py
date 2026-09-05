from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Carrier(Base):
    __tablename__ = "carriers"

    id = Column(Integer, primary_key=True, index=True)
    canonical_name = Column(
        String(150),
        nullable=False,
        unique=True,
        index=True,
    )
    carrier_type = Column(String(30), nullable=True)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    lane_coverages = relationship(
        "CarrierLaneCoverage",
        back_populates="carrier",
    )


class TradeLane(Base):
    __tablename__ = "trade_lanes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
    )
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    carrier_coverages = relationship(
        "CarrierLaneCoverage",
        back_populates="trade_lane",
    )


class CarrierLaneCoverage(Base):
    __tablename__ = "carrier_lane_coverages"
    __table_args__ = (
        UniqueConstraint(
            "carrier_id",
            "trade_lane_id",
            name="uq_carrier_trade_lane",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)

    carrier_id = Column(
        Integer,
        ForeignKey("carriers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    trade_lane_id = Column(
        Integer,
        ForeignKey("trade_lanes.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # Raw workbook values retained for import auditing.
    major_countries_raw = Column(Text, nullable=True)
    ports_covered_raw = Column(Text, nullable=True)
    rate_acquisition_notes = Column(Text, nullable=True)
    remarks = Column(Text, nullable=True)

    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    carrier = relationship(
        "Carrier",
        back_populates="lane_coverages",
    )
    trade_lane = relationship(
        "TradeLane",
        back_populates="carrier_coverages",
    )