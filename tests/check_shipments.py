"""Run only against an empty disposable PostgreSQL DB; never the company database.
SHIPMENT_TEST_DATABASE_URL is required. Does not use .env as its test target.
"""
import os
import sys
from pathlib import Path
from datetime import datetime
from tempfile import TemporaryDirectory
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
target=os.environ.get('SHIPMENT_TEST_DATABASE_URL')
if not target:
    raise SystemExit('Set SHIPMENT_TEST_DATABASE_URL to an EMPTY DISPOSABLE test database.')
os.environ['PROCUREMENT_DATABASE_URL']=target
os.environ['PROCUREMENT_SSLMODE']=os.getenv('SHIPMENT_TEST_SSLMODE','require')
os.environ['PROCUREMENT_API_TOKEN']='test-token-only'
from sqlalchemy import inspect,text,select,func
from fastapi.testclient import TestClient
from app.shipments.store import get_engine,shipments,history
from app.shipments.import_workbook import import_rows,read_workbook
from app.shipments.fields import FIELDS,review_flags
from app.operations_api import app
engine=get_engine()
with engine.connect() as conn:
    if inspect(conn).has_table('shipments',schema='operations') or inspect(conn).has_table('requests',schema='procurement'):
        raise SystemExit('Refusing a nonempty test target.')
rows=[dict.fromkeys(FIELDS),dict.fromkeys(FIELDS)]
rows[0].update(source_row=2,source_serial='1',shipper='Synthetic % Exporter',etd='5th April',container_no='TEST-A; TEST-B')
rows[1].update(source_row=3,source_serial='1',shipper='Synthetic Two',booking_date='2026-10-21')
import_rows(rows)
assert not inspect(engine).has_table('shipments',schema='operations')
import_rows(rows,True)
import_rows(rows,True)
try:
    import_rows([{**rows[0],'shipper':'Different'}],True)
    raise AssertionError('Changed import should be refused')
except ValueError:
    pass
client=TestClient(app)
assert client.get('/shipments').status_code==401
assert client.get('/procurement/requests').status_code==401
client.headers['X-Procurement-Token']='test-token-only'
listing=client.get('/shipments').json()
assert listing['total']==2
assert client.get('/shipments',params={'search':'%'}).json()['total']==1
row=client.get('/shipments',params={'search':'Synthetic %'}).json()['items'][0]
assert row['review_flags'] and row['container_no']=='TEST-A; TEST-B'
assert client.post('/shipments',json={'shipper':'Synthetic Three','unexpected':'no'}).status_code==422
assert client.post('/shipments',json={'shipper':' '}).status_code==422
updated=client.patch('/shipments/'+row['id'],json={'version':1,'changes':{'etd':'2026-10-21','remark':'Reviewed'}})
assert updated.status_code==200 and updated.json()['version']==2
assert not updated.json()['review_flags']
assert client.patch('/shipments/'+row['id'],json={'version':1,'changes':{'remark':'Overwrite'}}).status_code==409
saved=client.get('/shipments/'+row['id']).json()
assert saved['remark']=='Reviewed' and saved['shipper']==row['shipper']
created=client.post('/shipments',json={'shipper':'Synthetic Three','pod':'Test port'})
assert created.status_code==201
assert client.get('/shipments/stats').json()['total_shipments']==3
with engine.connect() as conn:
    assert conn.scalar(select(func.count()).select_from(history))==4
# Existing procurement endpoints can still read their independent records.
from app.procurement.request_tables import metadata,requests
with engine.begin() as conn:
    conn.execute(text('CREATE SCHEMA procurement'))
    metadata.create_all(conn)
    conn.execute(requests.insert().values(id='00000000-0000-0000-0000-000000000001',payload={'test':'sentinel'},status='ready'))
assert client.get('/procurement/requests').json()[0]['payload']=={'test':'sentinel'}
assert client.get('/health').status_code==200
print('PASS: PostgreSQL import, exact rerun, changed-import refusal, auth, create, search, edit, conflict, history, procurement coexistence.')
engine.dispose()

if '--ui' in sys.argv:
    import runpy
    runpy.run_path(str(Path(__file__).with_name('check_shipments_ui.py')),run_name='__main__')
