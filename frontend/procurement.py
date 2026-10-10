import json
import re
from datetime import date
from uuid import uuid4
import streamlit as st
from api import procurement_api


def label(value):
    return (value or 'not recorded').replace('_',' ').capitalize()


def render_procurement(_queries=None):
    st.header('New procurement request')
    st.caption('Enter shipment requirements directly. Plans and email drafts are saved in PostgreSQL.')
    with st.form('new_procurement'):
        left,right=st.columns(2)
        pol=left.text_input('POL *',placeholder='Mundra')
        pods_text=right.text_input('POD(s) *',placeholder='One port, or comma-separated ports')
        region=left.text_input('Booking region *',placeholder='Jaipur, Delhi, Mundra')
        equipment=right.selectbox('Container type *',['20DV','40HC','40DV','20RF','40RF','20OT','40OT','20FR','40FR'])
        quantity=left.number_input('Number of containers (0 = not supplied)',min_value=0,step=1)
        commodity=right.text_input('Commodity')
        ready=left.date_input('Cargo-ready date',value=None)
        weight=right.number_input('Gross cargo weight per container, kg (0 = not supplied)',min_value=0.0,step=100.0)
        hazardous=left.selectbox('Hazardous cargo',['unknown','no','yes'])
        free_text=right.text_input('Requested free days (optional)',placeholder='14')
        remarks=st.text_area('Additional requirements / DG details')
        submitted=st.form_submit_button('Save request and prepare plan')

    if submitted:
        pods=list(dict.fromkeys(p.strip() for p in re.split(r'[,;\r\n]+',pods_text) if p.strip()))
        if not pol.strip() or not pods or not region.strip():
            st.error('Enter POL, at least one POD, and booking region.')
        elif free_text.strip() and (not free_text.strip().isdigit() or int(free_text)>365):
            st.error('Free days must be a whole number between 0 and 365.')
        elif ready and ready<date.today():
            st.error('Use the intended cargo-ready date, not a past date.')
        else:
            payload={'pol':pol.strip(),'pods':pods,'booking_region':region.strip(),
                'container_type':equipment,'quantity':quantity or None,'commodity':commodity.strip(),
                'cargo_ready_date':ready.isoformat() if ready else None,
                'gross_weight_kg_per_container':weight or None,'hazardous':hazardous,
                'required_free_days':int(free_text) if free_text.strip() else None,'remarks':remarks.strip()}
            fingerprint=json.dumps(payload,sort_keys=True)
            if st.session_state.get('proc_submission_fingerprint')!=fingerprint:
                st.session_state['proc_submission_id']=str(uuid4())
                st.session_state['proc_submission_fingerprint']=fingerprint
            request_id=st.session_state['proc_submission_id']
            st.session_state['proc_active_request']=request_id
            with st.spinner('Saving and finding lanes and office contacts…'):
                result=procurement_api('POST','/requests',{'request_id':request_id,**payload})
            if result.get('error'):
                st.error(result['error'])
            else:
                st.success('Request saved. See the saved plan below.')

    st.divider()
    st.subheader('Saved requests')
    history=procurement_api('GET','/requests')
    if isinstance(history,dict) and 'error' in history:
        st.error(history['error']); return
    if not history:
        st.info('No saved requests yet.'); return
    options={row['id']:row for row in history}
    chosen=st.selectbox('Open a saved request',list(options),format_func=lambda rid:
        f"{rid[:8]} | {options[rid]['payload']['pol']} → {', '.join(options[rid]['payload']['pods'])} | {label(options[rid]['status'])}")
    if st.button('Open / refresh selected request'):
        st.session_state['proc_active_request']=chosen
    if st.button('Start a separate submission with the same form details'):
        st.session_state.pop('proc_submission_fingerprint',None)
        st.info('The next form submission will create a new request.')
    active=st.session_state.get('proc_active_request')
    if not active:
        return
    saved=procurement_api('GET',f'/requests/{active}')
    if 'id' not in saved and saved.get('error'):
        st.error(saved['error']); return
    st.subheader(f"Request {active[:8]} — {label(saved['status'])}")
    st.caption('Displaying saved requirements. Editing the form above does not change this request.')
    st.json(saved['payload'],expanded=False)
    if saved['status']=='planning':
        st.info('Planning is running. Refresh this request shortly. If the backend was restarted, create a new submission; interrupted jobs do not restart automatically.'); return
    if saved['status']=='failed':
        st.error(saved.get('error') or 'Planning failed.'); return
    st.caption('Carriers are lane candidates, not confirmed services. No email is sent by this application.')
    selection_rows=[]
    for dest in saved['destinations']:
        plan=dest['plan']
        st.subheader(f"{plan['pol']} → {dest['pod']}")
        st.write('Trade lane:', ', '.join(plan['trade_lanes']) or 'Unresolved')
        resolution=plan.get('port_resolution') or {}
        if resolution.get('explanation'):
            st.info(resolution['explanation'])
        if not plan['candidates']:
            st.warning(plan.get('next_action','Destination needs review.')); continue
        for candidate in plan['candidates']:
            routing=candidate.get('routing') or {}
            with st.expander(f"{candidate['shipping_line']} — {label(candidate['coverage_status'])}"):
                st.write('Rate instructions:',candidate.get('rate_getting_system') or 'Missing')
                st.write('Equipment:',label(candidate.get('equipment_status')))
                if candidate.get('remarks'):
                    st.write('Workbook remarks:',candidate['remarks'])
                st.info(candidate.get('next_action') or label(routing.get('status')))
                if candidate['coverage_status']!='destination_listed':
                    st.warning('Ask the carrier to confirm service to this POD.')
                blocked=(routing.get('channel')!='office'
                    or routing.get('status') in {'agency_conflict','carrier_identity_review'}
                    or candidate.get('equipment_status')=='conflicts_with_20ft_only_note')
                contacts=[('Preferred',c) for c in routing.get('contact_candidates',[])]+[
                    ('Documented fallback',c) for c in routing.get('fallback_contact_candidates',[])]
                seen=set()
                for kind,contact in contacts:
                    if contact['id'] in seen: continue
                    seen.add(contact['id'])
                    st.write(f"{kind} | {contact.get('office_location') or ''} | {contact.get('contact_person') or ''}")
                    st.write('Email:',contact.get('email_address') or 'Missing')
                    if contact.get('contact_number'): st.write('Phone:',contact['contact_number'])
                    disabled=blocked or not contact.get('email_address')
                    chosen_contact=st.checkbox('Use this contact for a draft',disabled=disabled,
                        key=f"draft_{active}_{dest['id']}_{candidate['entry_id']}_{contact['id']}")
                    if chosen_contact and not disabled:
                        selection_rows.append({'destination_id':dest['id'],'entry_id':candidate['entry_id'],'contact_id':contact['id']})
                if not contacts:
                    st.caption('Portal enquiry or contact follow-up required.')
    if st.button('Prepare selected email drafts',disabled=not selection_rows):
        for selection in selection_rows:
            result=procurement_api('POST',f'/requests/{active}/drafts',selection)
            if result.get('error'):
                st.error(result['error'])
            else:
                st.success(f"Draft saved for {result['carrier']}.")
        saved=procurement_api('GET',f'/requests/{active}')
        if 'id' not in saved and saved.get('error'): st.error(saved['error']); return
    if saved['drafts']:
        st.subheader('Saved email drafts')
        st.caption('Review recipients, cargo details and your signature before sending from Outlook. Downloads do not send email.')
    for draft in saved['drafts']:
        payload=draft['payload']
        with st.expander(payload['subject']):
            st.write('To:',', '.join(payload['to']))
            st.text(payload['body'])
            st.download_button('Download text',payload['body'],file_name=f"rate-request-{draft['id']}.txt",
                mime='text/plain',key=f"txt_{draft['id']}")
            # Generate RFC822 locally from the already saved, backend-validated draft.
            from email.message import EmailMessage
            from email.policy import SMTP
            message=EmailMessage(policy=SMTP)
            message['To']=', '.join(payload['to']); message['Subject']=payload['subject']; message['X-Unsent']='1'
            message.set_content(payload['body'])
            st.download_button('Download email (.eml)',message.as_bytes(),file_name=f"rate-request-{draft['id']}.eml",
                mime='message/rfc822',key=f"eml_{draft['id']}")
