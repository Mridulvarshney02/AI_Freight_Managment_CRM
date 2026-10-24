"""Shipment tables share the existing PostgreSQL connection, in a separate schema."""
from sqlalchemy import (MetaData, Table, Column, String, Text, Integer, DateTime,
                        ForeignKey, UniqueConstraint, func)
from sqlalchemy.dialects.postgresql import JSONB
from app.procurement.pg_database import get_engine
from app.shipments.fields import FIELDS

metadata = MetaData(schema='operations')
shipments = Table('shipments', metadata,
    Column('id', String(36), primary_key=True),
    *[Column(name, Text) for name in FIELDS],
    Column('version', Integer, nullable=False, default=1),
    Column('source_row', Integer),
    Column('source_notes', JSONB),
    Column('created_at', DateTime(timezone=True), server_default=func.now(), nullable=False),
    Column('updated_at', DateTime(timezone=True), server_default=func.now(), nullable=False))
history = Table('shipment_history', metadata,
    Column('id', Integer, primary_key=True),
    Column('shipment_id', String(36), ForeignKey('operations.shipments.id'), nullable=False),
    Column('version', Integer, nullable=False),
    Column('snapshot', JSONB, nullable=False),
    Column('recorded_at', DateTime(timezone=True), server_default=func.now(), nullable=False),
    UniqueConstraint('shipment_id','version'))
imports = Table('shipment_imports', metadata,
    Column('checksum', String(64), primary_key=True),
    Column('row_count', Integer, nullable=False),
    Column('created_at', DateTime(timezone=True), server_default=func.now(), nullable=False))
