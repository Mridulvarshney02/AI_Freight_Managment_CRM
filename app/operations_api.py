"""Internal operations API: current shipments and the existing procurement module."""
from fastapi import FastAPI
from app.procurement.routes import router as procurement_router
from app.shipments.routes import router as shipment_router
app=FastAPI(title='Freight Operations')
app.include_router(shipment_router)
app.include_router(procurement_router)
@app.get('/health')
def health():
    return {'status':'ok'}
