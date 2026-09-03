from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from dotenv import load_dotenv

import os

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
from pathlib import Path

DATABASE_URL = os.getenv("DATABASE_URL")

print(f"DATABASE_URL: {DATABASE_URL}")
print(f"Current working directory: {Path.cwd()}")
print(f"Resolved DB path: {(Path.cwd() / 'freight_queries.db').resolve()}")
# Create SQLite engine
engine = create_engine(
    DATABASE_URL, # type: ignore
    echo=True
    )
    


# Create session factory
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False
)

# Base class for all models
class Base(DeclarativeBase):
    pass

if __name__ == "__main__":
    print("Database connection initialized successfully!")
    print(DATABASE_URL)