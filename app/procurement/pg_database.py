import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

load_dotenv(Path(__file__).resolve().parents[2] / '.env')

@lru_cache(maxsize=1)
def get_engine():
    value = os.getenv('PROCUREMENT_DATABASE_URL', '').strip()
    if not value:
        raise RuntimeError('PROCUREMENT_DATABASE_URL is missing.')
    url = make_url(value)
    if url.get_backend_name() not in {'postgres', 'postgresql'}:
        raise RuntimeError('Procurement requires PostgreSQL.')
    url = url.set(drivername='postgresql+psycopg2')
    return create_engine(
        url, pool_pre_ping=True, pool_size=5, max_overflow=5,
        hide_parameters=True,
        connect_args={'sslmode': os.getenv('PROCUREMENT_SSLMODE', 'require'),
                      'connect_timeout': 15},
    )
