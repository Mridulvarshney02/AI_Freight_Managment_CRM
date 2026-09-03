from pydantic import BaseModel,ConfigDict
from typing import Optional
from datetime import date,datetime

class QueryBase(BaseModel):
    company_name: Optional[str] = None
    origin_port: Optional[str] = None
    destination_port: Optional[str] = None
    container_type: Optional[str] = None
    next_action: Optional[str] = None
    next_action_date: Optional[date] = None
    remarks: Optional[str] = None

class QueryCreate(QueryBase):
    pass

class QueryUpdate(QueryBase):
    pass



class QueryResponse(QueryBase):
    id: int
    query_received: bool
    quote_shared: bool
    shipment_status: Optional[str]= None
    validation_status: str
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)    
    
class ShipmentStatusUpdate(BaseModel):
    shipment_status: str    
    
class DashboardStats(BaseModel):
    total_queries: int
    quotes_shared: int
    pending_quotes: int
    booked_shipments: int
    delivered_shipments: int
    overdue_followups: int    
    
class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    response: str    