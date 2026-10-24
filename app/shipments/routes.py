import logging
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, create_model
from sqlalchemy.exc import SQLAlchemyError
from app.procurement.routes import require_token
from app.shipments.fields import FIELDS
from app.shipments import service

class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid',str_strip_whitespace=True)

ShipmentValues = create_model('ShipmentValues',__base__=StrictModel,
    **{k:(str | None,Field(default=None,max_length=20000)) for k in FIELDS})

class EditShipment(StrictModel):
    version: int = Field(ge=1)
    changes: ShipmentValues

router=APIRouter(prefix='/shipments',tags=['Shipments'],dependencies=[Depends(require_token)])

def run(fn,*args):
    try:
        return fn(*args)
    except service.Conflict as exc:
        raise HTTPException(409,str(exc)) from exc
    except service.NotFound as exc:
        raise HTTPException(404,str(exc)) from exc
    except SQLAlchemyError as exc:
        logging.getLogger(__name__).error('Shipment database failure: %s',type(exc).__name__)
        raise HTTPException(503,'Shipment database is unavailable. Check initialization and connection settings.') from exc

@router.get('/stats')
def stats():
    return run(service.stats)

@router.get('')
def listing(search: str=Query(default='',max_length=200),offset:int=Query(default=0,ge=0),limit:int=Query(default=100,ge=1,le=500)):
    return run(service.list_shipments,search,offset,limit)

@router.get('/{shipment_id}')
def detail(shipment_id: UUID):
    return run(service.get_shipment,str(shipment_id))

@router.post('',status_code=201)
def create(values: ShipmentValues):
    data=values.model_dump()
    if not data.get('shipper'):
        raise HTTPException(422,'Enter a shipper to create a shipment.')
    return run(service.create_shipment,data)

@router.patch('/{shipment_id}')
def edit(shipment_id: UUID,edit: EditShipment):
    data=edit.changes.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(422,'No changes submitted.')
    return run(service.update_shipment,str(shipment_id),edit.version,data)
