# Legacy SQLite utility: do not mutate the retired reference database.
import os as _os
from pathlib import Path as _Path
from dotenv import load_dotenv as _load_dotenv
_load_dotenv(_Path(__file__).resolve().parents[2] / '.env')
if _os.getenv('PROCUREMENT_DATABASE_URL', '').strip():
    raise RuntimeError('This legacy SQLite utility is disabled after PostgreSQL configuration. Use PostgreSQL maintenance tools.')

import json
import sqlite3
from contextlib import closing
from pathlib import Path
from uuid import uuid4

from app.procurement.discovery_schemas import DiscoveryResult

DB_PATH = Path(__file__).resolve().parent / "procurement.db"


def connect():
    # Open only an existing database.
    db = sqlite3.connect(
        DB_PATH.as_uri() + "?mode=rw",
        uri=True,
        timeout=10,
    )
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db


def setup():
    with closing(connect()) as db:
        with db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS discovery_jobs (
                    id TEXT PRIMARY KEY,
                    query_id INTEGER NOT NULL,
                    request_json TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'queued'
                        CHECK (
                            status IN (
                                'queued',
                                'running',
                                'completed',
                                'failed'
                            )
                        ),
                    result_json TEXT,
                    error_message TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)

            db.execute("""
                CREATE INDEX IF NOT EXISTS
                    idx_discovery_jobs_query_id
                ON discovery_jobs(query_id)
            """)

    print("Discovery storage ready. Existing procurement records preserved.")


def create_job(
    *,
    query_id: int,
    pol: str,
    pod: str,
    booking_region: str,
    container_type: str,
    cargo_ready_date: str | None = None,
) -> str:
    # Capture the shipment requirements at the time research starts.
    request = {
        "query_id": query_id,
        "pol": pol,
        "pod": pod,
        "booking_region": booking_region,
        "container_type": container_type,
        "cargo_ready_date": cargo_ready_date,
    }

    job_id = str(uuid4())

    with closing(connect()) as db:
        with db:
            db.execute(
                """
                INSERT INTO discovery_jobs (
                    id, query_id, request_json
                )
                VALUES (?, ?, ?)
                """,
                (
                    job_id,
                    query_id,
                    json.dumps(request, ensure_ascii=False),
                ),
            )

    return job_id


def get_job(job_id: str) -> dict | None:
    with closing(connect()) as db:
        row = db.execute(
            "SELECT * FROM discovery_jobs WHERE id = ?",
            (job_id,),
        ).fetchone()

    if row is None:
        return None

    job = dict(row)
    job["request"] = json.loads(job.pop("request_json"))
    result_json = job.pop("result_json")
    job["result"] = json.loads(result_json) if result_json else None
    return job


def start_job(job_id: str) -> bool:
    """Claim a queued job. Only one worker can claim it successfully."""
    with closing(connect()) as db:
        with db:
            cursor = db.execute(
                """
                UPDATE discovery_jobs
                SET status = 'running',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND status = 'queued'
                """,
                (job_id,),
            )

            return cursor.rowcount == 1


def complete_job(job_id: str, result: DiscoveryResult):
    # Validate again before storing the final research result.
    validated = DiscoveryResult.model_validate(result.model_dump())

    with closing(connect()) as db:
        with db:
            row = db.execute(
                """
                SELECT request_json
                FROM discovery_jobs
                WHERE id = ? AND status = 'running'
                """,
                (job_id,),
            ).fetchone()

            if row is None:
                raise ValueError("Job does not exist or is not running.")

            request = json.loads(row["request_json"])
            result_data = validated.model_dump(mode="json")

            # Prevent saving another shipment's findings against this job.
            for field in (
                "query_id",
                "pol",
                "pod",
                "booking_region",
                "container_type",
                "cargo_ready_date",
            ):
                if request[field] != result_data[field]:
                    raise ValueError(
                        f"Research result does not match job field: {field}"
                    )

            cursor = db.execute(
                """
                UPDATE discovery_jobs
                SET status = 'completed',
                    result_json = ?,
                    error_message = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND status = 'running'
                """,
                (validated.model_dump_json(), job_id),
            )

            if cursor.rowcount != 1:
                raise ValueError("Job is no longer running.")


def fail_job(job_id: str, message: str):
    # Pass a short, safe error description, not credentials or raw responses.
    with closing(connect()) as db:
        with db:
            cursor = db.execute(
                """
                UPDATE discovery_jobs
                SET status = 'failed',
                    error_message = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND status = 'running'
                """,
                (message, job_id),
            )

            if cursor.rowcount != 1:
                raise ValueError("Job does not exist or is not running.")


if __name__ == "__main__":
    setup()