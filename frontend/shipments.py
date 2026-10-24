"""Shipment Sheet editing; source values are shown as stored, with explicit Save."""
import os
import requests
import streamlit as st
from app.shipments.fields import FIELDS, DATE_FIELDS

BASE_URL=os.getenv('API_BASE_URL','http://127.0.0.1:8000').rstrip('/')

def api(method,path='',payload=None,params=None):
    try:
        response=requests.request(method,BASE_URL+'/shipments'+path,json=payload,params=params,
            headers={'X-Procurement-Token':os.getenv('PROCUREMENT_API_TOKEN','')},timeout=(10,45))
        data=response.json()
        if not response.ok:
            return {'error':str(data.get('detail','Request failed.'))}
        return data
    except requests.Timeout:
        return {'error':'Request timed out. Reload records before retrying a save; it may have completed.'}
    except (requests.RequestException,ValueError):
        return {'error':'Cannot reach the shipment service. Reload before retrying a save.'}

def fields_form(values,prefix):
    result={}
    cols=st.columns(3)
    for index,(name,label) in enumerate(FIELDS.items()):
        with cols[index%3]:
            help_text='Use YYYY-MM-DD for confirmed dates. Existing text remains until you correct it.' if name in DATE_FIELDS else None
            if name in {'remark','next_action','liner_payment_status'}:
                result[name]=st.text_area(label,value=values.get(name) or '',key=f'{prefix}_{name}',max_chars=20000)
            else:
                result[name]=st.text_input(label,value=values.get(name) or '',key=f'{prefix}_{name}',help=help_text,max_chars=20000)
    return result

def render_dashboard():
    result=api('GET','/stats')
    if 'error' in result:
        st.error(result['error'])
        return
    st.metric('Shipment records',result['total_shipments'])
    st.caption('Operational records from Shipment Sheet. Status text is preserved; completed/booked totals are not inferred from remarks.')

def render_shipments():
    st.header('Shipments')
    if 'shipment_notice' in st.session_state:
        st.success(st.session_state.pop('shipment_notice'))
    st.caption('Search, add and update Shipment Sheet records. Save changes explicitly; dates needing review remain visible.')
    mode=st.radio('Action',['Find and edit','Add shipment'],horizontal=True)
    if mode=='Add shipment':
        with st.form('create_shipment'):
            values=fields_form({},f"new_{st.session_state.get('shipment_new_generation',0)}")
            submitted=st.form_submit_button('Create shipment')
        if submitted:
            data=api('POST',payload={k:v or None for k,v in values.items()})
            if 'error' in data:
                st.error(data['error'])
            else:
                st.session_state['shipment_new_generation']=st.session_state.get('shipment_new_generation',0)+1
                st.session_state['shipment_notice']='Shipment saved. Use Find and edit to open it.'
                st.rerun()
        return
    search=st.text_input('Search shipper, booking, container, port or any shipment field',max_chars=200)
    page=st.number_input('Page',min_value=1,value=1,step=1)
    result=api('GET',params={'search':search,'offset':(page-1)*100,'limit':100})
    if 'error' in result:
        st.error(result['error'])
        return
    rows=result['items']
    st.caption(f"{result['total']} matching records. Showing up to 100 on this page.")
    if not rows:
        st.info('No shipments on this page. Try page 1 or change the search.')
        return
    st.dataframe([{FIELDS[k]:r.get(k) for k in FIELDS} for r in rows],hide_index=True)
    by_id={r['id']:r for r in rows}
    selected=st.selectbox('Shipment to edit',list(by_id),format_func=lambda i:
        f"{by_id[i].get('source_serial') or 'New'} | {by_id[i].get('shipper') or 'Unnamed'} | {by_id[i].get('booking_no') or 'No booking'} | {i[:8]}")
    if st.session_state.get('editing_shipment_id')!=selected:
        st.session_state['editing_shipment_id']=selected
        st.session_state.pop('shipment_snapshot',None)
    if st.button('Reload selected shipment'):
        st.session_state.pop('shipment_snapshot',None)
        for key in list(st.session_state):
            if key.startswith('edit_ship_'):
                del st.session_state[key]
        st.rerun()
    if 'shipment_snapshot' not in st.session_state:
        snapshot=api('GET','/'+selected)
        if 'error' in snapshot:
            st.error(snapshot['error'])
            return
        st.session_state['shipment_snapshot']=snapshot
    snapshot=st.session_state['shipment_snapshot']
    for flag in snapshot.get('review_flags',[]):
        st.warning(flag)
    st.caption('Reload discards unsaved edits. Saves reject a stale version if a colleague has already changed this record.')
    with st.form('edit_shipment'):
        values=fields_form(snapshot,f"edit_ship_{selected}_{snapshot['version']}")
        submitted=st.form_submit_button('Save changes')
    if submitted:
        # Only send changed fields; preserve original whitespace and nulls in all others.
        changes={k:(v or None) for k,v in values.items() if v!=(snapshot.get(k) or '')}
        if not changes:
            st.info('No changes to save.')
        else:
            data=api('PATCH','/'+selected,{'version':snapshot['version'],'changes':changes})
            if 'error' in data:
                st.error(data['error'])
            else:
                st.session_state['shipment_snapshot']=data
                st.session_state['shipment_notice']='Changes saved.'
                st.rerun()

def render_operations():
    from procurement import render_procurement
    st.title('Freight Operations')
    dashboard,shipments,procurement=st.tabs(['Dashboard','Shipments','Procurement'])
    with dashboard:
        render_dashboard()
    with shipments:
        render_shipments()
    with procurement:
        render_procurement()
