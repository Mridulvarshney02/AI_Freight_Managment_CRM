"""Run through check_shipments.py --ui, on its disposable test database."""
import os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'frontend'))
os.environ['PROCUREMENT_TEAM_PASSWORD']='synthetic-password-for-test-only'
import requests
from fastapi.testclient import TestClient
from app.operations_api import app
client=TestClient(app,headers={'X-Procurement-Token':'test-token-only'})
from streamlit.testing.v1 import AppTest
calls=[]
class Reply:
    def __init__(self,response):
        self._response=response
        self.ok=response.status_code<400
    def json(self):return self._response.json()
def request(method,url,json=None,params=None,**kwargs):
    calls.append(url)
    path=url.split(':8000')[-1]
    if path.startswith('/procurement'):
        class Empty:
            ok=True
            def json(self): return []
        return Empty()
    return Reply(client.request(method,path,json=json,params=params))
requests.request=request
at=AppTest.from_file(str(ROOT/'frontend/procurement_hosted.py'),default_timeout=20).run()
assert not at.exception
assert not calls, 'Login gate leaked data requests'
at.text_input[0].set_value(os.environ['PROCUREMENT_TEAM_PASSWORD'])
at.button[0].click().run()
assert not at.exception,at.exception
assert [t.label for t in at.tabs]==['Dashboard','Shipments','Procurement']
# Edit a shipment through the actual frontend -> API -> PG path.
remark=next(w for w in at.text_area if w.label=='REMARK')
remark.set_value('Saved through UI')
next(w for w in at.button if w.label=='Save changes').click().run()
assert not at.exception,at.exception
assert any('Changes saved' in s.value for s in at.success)
# A colleague writes after the editor's snapshot. Stale user save must fail.
snapshot=at.session_state['shipment_snapshot']
client.patch('/shipments/'+snapshot['id'],json={'version':snapshot['version'],'changes':{'remark':'Colleague change'}})
next(w for w in at.text_area if w.label=='REMARK').set_value('Stale UI value')
next(w for w in at.button if w.label=='Save changes').click().run()
assert not at.exception,at.exception
assert any('changed since' in e.value for e in at.error)
assert client.get('/shipments/'+snapshot['id']).json()['remark']=='Colleague change'
# Creation screen uses all 33 fields and saves.
at.radio[0].set_value('Add shipment').run()
next(w for w in at.text_input if w.label=='SHIPPER').set_value('UI Synthetic')
next(w for w in at.button if w.label=='Create shipment').click().run()
assert not at.exception,at.exception
assert any('Shipment saved' in s.value for s in at.success)
assert client.get('/shipments',params={'search':'UI Synthetic'}).json()['total']==1
print('PASS: hosted login gate, three tabs, frontend edit, stale-edit protection, frontend create.')
