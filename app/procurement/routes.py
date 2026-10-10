import logging
import os
import secrets
from uuid import UUID
from fastapi import APIRouter, Depends, Header, HTTPException, Response
from sqlalchemy.exc import SQLAlchemyError
from app.procurement.request_schemas import NewRequest, DraftSelection
from app.procurement import request_service as service

logger=logging.getLogger(__name__)

def require_token(x_procurement_token: str | None = Header(default=None)):
    expected=os.getenv('PROCUREMENT_API_TOKEN','').strip()
    if expected and not secrets.compare_digest(x_procurement_token or '',expected):
        raise HTTPException(401,'Procurement access denied.')

router=APIRouter(prefix='/procurement',tags=['Procurement'],dependencies=[Depends(require_token)])

def run(operation,*args):
    try:
        return operation(*args)
    except service.RequestNotFound as exc:
        raise HTTPException(404,str(exc)) from exc
    except service.RequestConflict as exc:
        raise HTTPException(409,str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from exc
    except (SQLAlchemyError,RuntimeError) as exc:
        logger.error('Procurement operation failed: %s',type(exc).__name__)
        raise HTTPException(503,'Procurement database unavailable or not migrated. Check backend configuration.') from exc
    except Exception as exc:
        logger.error('Procurement operation failed: %s',type(exc).__name__)
        raise HTTPException(500,'Procurement operation failed. Check backend terminal.') from exc

@router.post('/requests')
def create_request(data: NewRequest):
    return run(service.create_request,data)

@router.get('/requests')
def list_requests():
    return run(service.list_requests)

@router.get('/requests/{request_id}')
def get_request(request_id: UUID):
    return run(service.get_request,str(request_id))

@router.post('/requests/{request_id}/drafts')
def create_draft(request_id: UUID,selection: DraftSelection):
    return run(service.create_draft,str(request_id),selection)

@router.get('/requests/{request_id}/drafts/{draft_id}/eml')
def download_draft(request_id: UUID,draft_id: UUID):
    saved=run(service.get_draft,str(request_id),str(draft_id))
    return Response(service.email_bytes(saved['payload']),media_type='message/rfc822',
        headers={'Content-Disposition':f'attachment; filename="rate-request-{draft_id}.eml"'})
