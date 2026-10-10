import copy
import re
from datetime import date
from email.message import EmailMessage
from email.policy import SMTP
from email.utils import getaddresses
from uuid import uuid4

from sqlalchemy import select, update, func
from sqlalchemy.dialects.postgresql import insert
from app.procurement.pg_database import get_engine
from app.procurement.request_tables import requests, destinations, drafts
from app.procurement.lookup import lookup
from app.procurement.routing import add_routing

class RequestNotFound(ValueError):
    pass

class RequestConflict(ValueError):
    pass


def get_request(request_id):
    with get_engine().connect() as db:
        row=db.execute(select(requests).where(requests.c.id==str(request_id))).mappings().first()
        if row is None:
            raise RequestNotFound('Procurement request not found.')
        result=dict(row)
        result['destinations']=[dict(r) for r in db.execute(select(destinations).where(
            destinations.c.request_id==str(request_id)).order_by(destinations.c.position)).mappings()]
        result['drafts']=[dict(r) for r in db.execute(select(drafts).where(
            drafts.c.request_id==str(request_id)).order_by(drafts.c.created_at)).mappings()]
    return result


def list_requests():
    with get_engine().connect() as db:
        return [dict(r) for r in db.execute(select(requests).order_by(
            requests.c.created_at.desc()).limit(50)).mappings()]


def create_request(data):
    request_id=str(data.request_id)
    payload=data.model_dump(mode='json',exclude={'request_id'})
    with get_engine().begin() as db:
        claimed=db.execute(insert(requests).values(id=request_id,payload=payload,status='planning')
            .on_conflict_do_nothing(index_elements=['id']).returning(requests.c.id)).scalar_one_or_none()
        if claimed is None:
            old=db.execute(select(requests).where(requests.c.id==request_id)).mappings().one()
            if old['payload'] != payload:
                raise RequestConflict('This submission ID belongs to different inputs. Start a new request.')
    if claimed is None:
        return get_request(request_id)
    try:
        plans=[]
        # External calls run outside database transactions.
        for pod in data.pods:
            plan=lookup(data.pol,pod,resolve_missing=True)
            plan=add_routing(plan,data.booking_region,data.container_type)
            plans.append(plan)
        status='ready' if all(p['candidates'] for p in plans) else 'needs_review'
        with get_engine().begin() as db:
            for position,plan in enumerate(plans):
                db.execute(destinations.insert().values(request_id=request_id,position=position,
                    pod=data.pods[position],plan=plan))
            db.execute(update(requests).where(requests.c.id==request_id).values(
                status=status,updated_at=func.now()))
    except Exception:
        with get_engine().begin() as db:
            db.execute(update(requests).where(requests.c.id==request_id).values(
                status='failed',error='Planning failed. Check backend configuration and start a new request.',
                updated_at=func.now()))
        raise
    return get_request(request_id)


def recipient_addresses(raw):
    if not raw or '\r' in raw or '\n' in raw:
        raise ValueError('Contact email is missing or has line breaks. Correct the contact first.')
    addresses=[]
    for _,address in getaddresses([raw.replace(';',',')]):
        if not re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+",address):
            raise ValueError('Contact email format needs correction before making a draft.')
        if address.casefold() not in {a.casefold() for a in addresses}:
            addresses.append(address)
    if not addresses:
        raise ValueError('No usable email address in this contact.')
    return addresses


def create_draft(request_id, selection):
    saved=get_request(request_id)
    if saved['status'] not in {'ready','needs_review'}:
        raise RequestConflict('Wait for planning to finish before preparing a draft.')
    payload=saved['payload']
    missing=[field for field in ('quantity','commodity','cargo_ready_date','gross_weight_kg_per_container')
             if not payload.get(field)]
    if payload.get('hazardous')=='unknown':
        missing.append('hazardous')
    if missing:
        raise ValueError('A complete rate request needs: '+', '.join(missing)+'. Start a new request with these details.')
    if date.fromisoformat(payload['cargo_ready_date']) < date.today():
        raise ValueError('Cargo-ready date is in the past. Start a request with the intended date.')
    destination=next((d for d in saved['destinations'] if d['id']==selection.destination_id),None)
    if destination is None:
        raise ValueError('Destination does not belong to this request.')
    plan=copy.deepcopy(destination['plan'])
    # Recheck contact routing against the current PostgreSQL contacts.
    plan=add_routing(plan,payload['booking_region'],payload['container_type'])
    candidate=next((c for c in plan['candidates'] if c['entry_id']==selection.entry_id),None)
    if candidate is None:
        raise ValueError('Carrier is not a candidate for this destination.')
    routing=candidate['routing']
    if (routing['channel']!='office' or routing['status'] in {'agency_conflict','carrier_identity_review'}
        or candidate['equipment_status']=='conflicts_with_20ft_only_note'):
        raise ValueError('Resolve carrier, channel, or equipment restrictions before drafting.')
    contact=next((c for c in routing['contact_candidates']+routing['fallback_contact_candidates']
                  if c['id']==selection.contact_id),None)
    if contact is None:
        raise ValueError('Selected contact is not authorized by the current office rules.')
    recipients=recipient_addresses(contact['email_address'])
    subject=' '.join((f"Rate enquiry {str(request_id)[:8]} | {payload['pol']} to {destination['pod']} | "
                     f"{payload['quantity']} x {payload['container_type']}").split())
    lines=[
        'Dear Team,', '',
        f"Please confirm service and quote for {payload['pol']} to {destination['pod']}.",
        '',
        f"Shipping line: {candidate['shipping_line']}",
        f"Booking region: {payload['booking_region']}",
        f"Equipment: {payload['quantity']} x {payload['container_type']}",
        f"Commodity: {payload['commodity']}",
        f"Cargo-ready date: {payload['cargo_ready_date']}",
        f"Gross cargo weight per container: {payload['gross_weight_kg_per_container']} kg",
        f"Hazardous cargo: {payload['hazardous']}",
    ]
    if payload.get('hazardous')=='yes':
        lines.append('Please advise DG acceptance and required documentation; DG details will follow.')
    if payload.get('required_free_days') is not None:
        lines.append(f"Requested free days: {payload['required_free_days']} (please specify terms and location).")
    if payload.get('remarks'):
        lines.append('Additional requirements: '+payload['remarks'])
    lines += ['', 'Please confirm equipment and cargo acceptance, routing/transshipment, sailing schedule,',
              'transit time, rate validity, and free-time terms. Please itemize ocean freight,',
              'origin/destination charges, surcharges, taxes, currency and charging basis.',
              'Clearly state any excluded or unconfirmed charges.', '',
              'This is a quotation request only, not a booking instruction.', '', 'Regards,']
    content={'to':recipients,'subject':subject,'body':'\n'.join(lines),
             'carrier':candidate['shipping_line'],'contact':contact,'coverage_status':candidate['coverage_status']}
    with get_engine().begin() as db:
        draft_id=db.execute(insert(drafts).values(id=str(uuid4()),request_id=str(request_id),
            destination_id=selection.destination_id,entry_id=selection.entry_id,contact_id=selection.contact_id,
            payload=content).on_conflict_do_update(
                index_elements=['request_id','destination_id','entry_id','contact_id'],
                set_={'payload':content}).returning(drafts.c.id)).scalar_one()
    return {'id':draft_id,**content}


def get_draft(request_id,draft_id):
    with get_engine().connect() as db:
        row=db.execute(select(drafts).where(drafts.c.id==str(draft_id),
            drafts.c.request_id==str(request_id))).mappings().first()
    if row is None:
        raise RequestNotFound('Draft not found for this request.')
    return dict(row)


def email_bytes(payload):
    message=EmailMessage(policy=SMTP)
    message['To']=', '.join(payload['to'])
    message['Subject']=payload['subject']
    message['X-Unsent']='1'
    message.set_content(payload['body'])
    return message.as_bytes()
