"""Standalone local procurement backend; does not import the CRM or its agent."""
from fastapi import FastAPI
from app.procurement.routes import router
app=FastAPI(title='Freight Procurement')
app.include_router(router)
@app.get('/health')
def health():
    return {'status':'ok'}
