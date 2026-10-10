from sqlalchemy import (MetaData, Table, Column, String, Integer, Text,
                        DateTime, ForeignKey, UniqueConstraint, CheckConstraint, func)
from sqlalchemy.dialects.postgresql import JSONB

metadata = MetaData(schema='procurement')
requests = Table('requests', metadata,
    Column('id', String(36), primary_key=True),
    Column('payload', JSONB, nullable=False),
    Column('status', String(30), nullable=False),
    Column('error', Text),
    Column('created_at', DateTime(timezone=True), server_default=func.now(), nullable=False),
    Column('updated_at', DateTime(timezone=True), server_default=func.now(), nullable=False),
    CheckConstraint("status IN ('planning','ready','needs_review','failed')"),
)
destinations = Table('request_destinations', metadata,
    Column('id', Integer, primary_key=True),
    Column('request_id', String(36), ForeignKey('procurement.requests.id', ondelete='RESTRICT'), nullable=False),
    Column('position', Integer, nullable=False),
    Column('pod', Text, nullable=False),
    Column('plan', JSONB, nullable=False),
    UniqueConstraint('request_id','position'),
)
drafts = Table('drafts', metadata,
    Column('id', String(36), primary_key=True),
    Column('request_id', String(36), ForeignKey('procurement.requests.id', ondelete='RESTRICT'), nullable=False),
    Column('destination_id', Integer, ForeignKey('procurement.request_destinations.id', ondelete='RESTRICT'), nullable=False),
    Column('entry_id', Integer, nullable=False),
    Column('contact_id', Integer, nullable=False),
    Column('payload', JSONB, nullable=False),
    Column('created_at', DateTime(timezone=True), server_default=func.now(), nullable=False),
    UniqueConstraint('request_id','destination_id','entry_id','contact_id'),
)
