"""One-shot, verified migration into a NEW procurement schema. Never overwrites data."""
import argparse
import json
import sqlite3
from pathlib import Path
from sqlalchemy import create_engine, MetaData, Integer, Text, DefaultClause, inspect, select, text
from sqlalchemy.pool import NullPool
from app.procurement.pg_database import get_engine
from app.procurement.request_tables import metadata as request_metadata

REQUIRED = {'procurement_entries', 'shipping_line_contacts', 'shipping_line_aliases',
            'port_aliases', 'lane_origin_scope'}
OPTIONAL = {'contact_changes', 'discovery_jobs'}

def canonical(rows):
    return sorted(json.dumps(dict(r), sort_keys=True, ensure_ascii=False) for r in rows)

def migrate(source_path):
    path = Path(source_path).resolve()
    if not path.is_file():
        raise RuntimeError('SQLite source not found.')
    source = create_engine('sqlite://', poolclass=NullPool, creator=lambda: sqlite3.connect(
        path.as_uri() + '?mode=ro', uri=True))
    try:
        with source.connect() as src:
            src.exec_driver_sql('BEGIN')  # Consistent read snapshot; no writes.
            names = set(inspect(src).get_table_names())
            if REQUIRED - names:
                raise RuntimeError('Source is missing required procurement tables.')
            if names - REQUIRED - OPTIONAL:
                raise RuntimeError('Unexpected source tables; review migration before proceeding.')
            original = MetaData()
            original.reflect(bind=src, only=sorted(names))
            target = MetaData(schema='procurement')
            snapshots = {}
            for name in sorted(names):
                old = original.tables[name]
                snapshots[name] = [dict(r) for r in src.execute(select(old)).mappings()]
                new = old.to_metadata(target, schema='procurement')
                for col in new.columns:
                    if col.primary_key and isinstance(col.type, Integer):
                        col.autoincrement = True
                    if isinstance(col.type, Text) and col.server_default is not None:
                        if 'CURRENT_TIMESTAMP' in str(col.server_default.arg).upper():
                            col.server_default = DefaultClause(text('(CURRENT_TIMESTAMP::text)'))
            with get_engine().begin() as dst:
                dst.execute(text('CREATE SCHEMA IF NOT EXISTS procurement'))
                dst.execute(text('SELECT pg_advisory_xact_lock(26092601)'))
                if inspect(dst).get_table_names(schema='procurement'):
                    raise RuntimeError('Target procurement schema contains tables; refusing to overwrite.')
                target.create_all(dst)
                counts = {}
                for name in sorted(names):
                    table = target.tables['procurement.' + name]
                    rows = snapshots[name]
                    if rows:
                        dst.execute(table.insert(), rows)
                    copied = dst.execute(select(table)).mappings().all()
                    if canonical(rows) != canonical(copied):
                        raise RuntimeError('Row comparison failed for ' + name)
                    for col in table.primary_key.columns:
                        if isinstance(col.type, Integer):
                            maximum = max((r[col.name] for r in rows), default=0)
                            sequence = dst.execute(text('SELECT pg_get_serial_sequence(:tbl, :col)'),
                                {'tbl': 'procurement.' + name, 'col': col.name}).scalar_one()
                            if sequence:
                                dst.execute(text('SELECT setval(CAST(:seq AS regclass), :n, :used)'),
                                    {'seq': sequence, 'n': max(1, maximum), 'used': bool(maximum)})
                    counts[name] = len(rows)
                request_metadata.create_all(dst)
            for name, count in counts.items():
                print(f'{name}: {count} rows copied and compared')
            print('Migration committed. SQLite source was not modified.')
    finally:
        source.dispose()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', default='app/procurement/procurement.db')
    args = parser.parse_args()
    try:
        migrate(args.source)
    except Exception as exc:
        if isinstance(exc, RuntimeError):
            raise SystemExit(str(exc))
        raise SystemExit(f'Migration failed ({type(exc).__name__}); target transaction rolled back. No credentials printed.')
