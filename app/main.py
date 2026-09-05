from typing import Generator
from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session
from app.database import Base, SessionLocal, engine
from app import crud
from app.schemas import QueryResponse, QueryCreate, QueryUpdate, ShipmentStatusUpdate
from app.schemas import DashboardStats
from typing import List
from langchain_core.messages import HumanMessage
from app.ai.agent import agent
from app.schemas import ChatRequest, ChatResponse
from langchain_core.messages import HumanMessage, AIMessage
from app.procurement import models as procurement_models  # noqa: F401
from dotenv import load_dotenv
load_dotenv()

# Create all database tables 
Base.metadata.create_all(bind=engine)

app = FastAPI()
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/")
def root():
    return {"message": "AI Freight Management System is running!"}
@app.get("/queries", response_model=List[QueryResponse])
def get_queries(db: Session = Depends(get_db)):
    return crud.get_queries(db)


@app.get(
    "/queries/pending-followups",
    response_model=List[QueryResponse]
)
def pending_followups(
    db: Session = Depends(get_db)
):
    return crud.get_pending_followups(db)


@app.get("/queries/{query_id}", response_model=QueryResponse)
def get_query(
    query_id: int,
    db: Session = Depends(get_db)
):
    query = crud.get_query(db, query_id)

    if query is None:
        raise HTTPException(
            status_code=404, # type: ignore
            detail="Query not found" # type: ignore
        )

    return query

@app.post("/queries", response_model=QueryResponse)
def create_query(
    query: QueryCreate,
    db: Session = Depends(get_db)
):
    return crud.create_query(db, query)

@app.patch("/queries/{query_id}",response_model=QueryResponse)
def update_query(
    query_id: int,
    query: QueryUpdate,
    db: Session = Depends(get_db)
):
    updated_query = crud.update_query(db, query_id, query)
    
    if updated_query is None:
            raise HTTPException(
                status_code=404, # type: ignore
                detail="Query not found" # type: ignore
            )
    
    return updated_query

@app.patch(
    "/queries/{query_id}/share-quote",
    response_model=QueryResponse
)
def share_quote(
    query_id: int,
    db: Session = Depends(get_db)
):
    updated_query = crud.share_quote(db, query_id)

    if updated_query is None:
        raise HTTPException(
            status_code=404, # type: ignore
            detail="Query not found" # type: ignore
        )

    return updated_query

@app.patch(
    "/queries/{query_id}/shipment-status",
    response_model=QueryResponse
)
def update_shipment_status(
    query_id: int,
    shipment: ShipmentStatusUpdate,
    db: Session = Depends(get_db)
):
    updated_query = crud.update_shipment_status(
        db,
        query_id,
        shipment.shipment_status
    )

    if updated_query is None:
        raise HTTPException(
            status_code=404, # type: ignore
            detail="Query not found" # type: ignore
        )

    return updated_query

@app.get(
    "/dashboard/stats",
    response_model=DashboardStats
)
def dashboard_stats(
    db: Session = Depends(get_db)
):
    return crud.get_dashboard_stats(db)


def extract_text(content) -> str:
    """Extract plain text from LangChain AIMessage content."""

    if isinstance(content, str):
        return content

    text_parts = []

    for part in content:
        if isinstance(part, str):
            text_parts.append(part)
        elif isinstance(part, dict):
            if part.get("type") == "text":
                text_parts.append(part.get("text", ""))
                
    return "".join(text_parts)

from pprint import pprint
@app.post("/ai/chat", response_model=ChatResponse)
def ai_chat(request: ChatRequest):

    try:
        result = agent.invoke(
            {
                "messages": [
                    HumanMessage(content=request.message)
                ]
            }
        )
        print("=" * 80)
        print("RAW AGENT RESULT")
        print(result)
        print("=" * 80)

        final_message = result["messages"][-1]

        if not isinstance(final_message, AIMessage):
            raise HTTPException(
                status_code=500,
                detail="Agent did not return a final AI message."
            )

        return ChatResponse(
            response=extract_text(final_message.content)
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )