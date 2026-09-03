from sqlalchemy.orm import Session
from sqlalchemy import func , or_
from datetime import date
from app.models import Query
from app.schemas import QueryCreate , QueryUpdate
from app import models

VALID_STATUSES = {
    "Pending",
    "Booked",
    "In Transit",
    "Delivered",
}

def get_queries(db: Session):
    return db.query(Query).all()


def get_query(db: Session, query_id: int):
    return (
        db.query(Query)
        .filter(Query.id == query_id)
        .first()
    )

def create_query(db: Session, query: QueryCreate):
    db_query = Query(
        **query.model_dump(),
        query_received=True,
        validation_status="Valid"
    )

    db.add(db_query)
    db.commit()
    db.refresh(db_query)
    return db_query


def update_query(
    db: Session,
    query_id: int,
    query: QueryUpdate
):
    db_query = get_query(db, query_id)
    if db_query is None:
        return None
    update_data = query.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        setattr(db_query,key, value)
        
    db.commit()
    db.refresh(db_query)    
    
    return db_query
def share_quote(
    db: Session,
    query_id: int
):
    db_query = get_query(db, query_id)

    if db_query is None:
        return None

    db_query.quote_shared = True # type: ignore

    db.commit()
    db.refresh(db_query)

    return db_query

def update_shipment_status(
    db: Session,
    query_id: int,
    shipment_status: str
):
    if shipment_status not in VALID_STATUSES:
        raise ValueError(f"Invalid shipment status: {shipment_status}")
        
    db_query = get_query(db, query_id)

    if db_query is None:
        return None

    db_query.shipment_status = shipment_status # type: ignore

    db.commit()
    db.refresh(db_query)

    return db_query

def get_dashboard_stats(db: Session):
    total_queries = db.query(Query).count()

    quotes_shared = db.query(Query).filter(
        Query.quote_shared == True
    ).count()

    pending_quotes = db.query(Query).filter(
        Query.quote_shared == False
    ).count()

    booked_shipments = db.query(Query).filter(
        Query.shipment_status == "Booked"
    ).count()

    delivered_shipments = db.query(Query).filter(
        Query.shipment_status == "Delivered"
    ).count()

    overdue_followups = (
    db.query(Query)
    .filter(
        Query.next_action_date < date.today(),
        or_(
            Query.shipment_status != "Delivered",
            Query.shipment_status.is_(None)
        )
    )
    .count()
)
    return {
        "total_queries": total_queries,
        "quotes_shared": quotes_shared,
        "pending_quotes": pending_quotes,
        "booked_shipments": booked_shipments,
        "delivered_shipments": delivered_shipments,
        "overdue_followups": overdue_followups
    }
    
def get_pending_followups(db: Session):
    pending_queries = (
        db.query(Query)
        .filter(
            Query.next_action_date <= date.today(),
            or_(
                Query.shipment_status != "Delivered",
                Query.shipment_status.is_(None)
            )
        )        
        .all()
    )
    return pending_queries    

def search_company(db: Session, company_name: str):
    return (
        db.query(Query)
        .filter(
            models.Query.company_name.ilike(f"%{company_name}%")
        )
        .all()
    )