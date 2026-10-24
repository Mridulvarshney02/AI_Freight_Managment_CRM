from uuid import uuid4
from sqlalchemy import select, update, func, or_, case, cast, Numeric
from app.shipments.store import get_engine, shipments, history
from app.shipments.fields import FIELDS, review_flags

class Conflict(Exception):
    pass

class NotFound(Exception):
    pass

def output(row):
    result = dict(row)
    result['review_flags'] = review_flags(result)
    for note in result.get('source_notes') or []:
        result['review_flags'].append(FIELDS[note['field']] + ': source workbook used a formula. Its cached value was imported, not recalculated; verify this field.')
    return result

def record_history(conn, row):
    conn.execute(history.insert().values(shipment_id=row['id'],version=row['version'],
        snapshot={k: row[k] for k in FIELDS}))

def list_shipments(search='',offset=0,limit=100):
    query = select(shipments)
    count = select(func.count()).select_from(shipments)
    if search.strip():
        # Literal substring search; wildcard characters in identifiers stay literal.
        term = search.strip().replace('\\','\\\\').replace('%','\\%').replace('_','\\_')
        condition = or_(*[shipments.c[k].ilike('%'+term+'%',escape='\\') for k in FIELDS])
        query = query.where(condition)
        count = count.where(condition)
    # Sort the entire result before pagination, not only the visible page.
    serial = func.trim(shipments.c.source_serial)
    numeric_serial = case(
        (serial.op('~')(r'^[0-9]+([.][0-9]+)?$'), cast(serial, Numeric)),
        else_=None,
    )
    ordering = (
        numeric_serial.asc().nulls_last(),
        func.nullif(serial, '').asc().nulls_last(),
        shipments.c.source_row.asc().nulls_last(),
        shipments.c.created_at.asc(),
        shipments.c.id.asc(),
    )
    with get_engine().connect() as conn:
        return {'total':conn.scalar(count),'items':[output(r) for r in conn.execute(
            query.order_by(*ordering).offset(offset).limit(limit)).mappings()]}

def get_shipment(shipment_id):
    with get_engine().connect() as conn:
        row=conn.execute(select(shipments).where(shipments.c.id==shipment_id)).mappings().first()
    if row is None:
        raise NotFound('Shipment not found.')
    return output(row)

def create_shipment(values):
    with get_engine().begin() as conn:
        row=conn.execute(shipments.insert().values(id=str(uuid4()),version=1,**values)
            .returning(shipments)).mappings().one()
        record_history(conn,row)
        return output(row)

def update_shipment(shipment_id,version,values):
    with get_engine().begin() as conn:
        row=conn.execute(update(shipments).where(shipments.c.id==shipment_id,
            shipments.c.version==version).values(**values,version=version+1,updated_at=func.now())
            .returning(shipments)).mappings().first()
        if row is None:
            raise Conflict('This shipment changed since you opened it. Reload it before editing again.')
        record_history(conn,row)
        return output(row)

def stats():
    with get_engine().connect() as conn:
        return {'total_shipments':conn.scalar(select(func.count()).select_from(shipments))}
