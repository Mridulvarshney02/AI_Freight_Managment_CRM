from langchain_core.tools import tool
from app.database import SessionLocal
from app import crud
from contextlib import contextmanager
from app.database import SessionLocal
import json
from app.ai.guardrails import ToolGuard
guard = ToolGuard()


@contextmanager
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@tool
def dashboard_stats():
    """Get overall freight dashboard statistics."""
    print("=" * 60)
    print("TOOL CALLED: dashboard_stats")

    with get_db() as db:
        stats = crud.get_dashboard_stats(db)
        print(stats)
        return json.dumps(stats, default=str,indent=2)

@tool
def pending_followups():
    
    """Returns all freight queries whose next_action_date is due or overdue.

    Use this tool when the user asks about:
    - pending follow-ups
    - overdue follow-ups
    - shipments requiring follow-up
    - customers to contact
    - pending shipments requiring action"""
    
    with get_db() as db:

        data = crud.get_pending_followups(db)

        print("Rows returned:", len(data))

        result = [
            {
                "query_id": q.id,
                "company": q.company_name,
                "shipment_status": q.shipment_status,
                "next_action": q.next_action,
                "next_action_date": (
                    q.next_action_date.isoformat()
                    if q.next_action_date is not None
                    else None
                ),
            }
            for q in data
        ]

        print("Tool result:", result)

        return json.dumps(result, indent=2)


@tool
def search_company(company_name: str):
    """
    Search freight queries by company name.
    """

    with get_db() as db:

        queries = crud.search_company(db, company_name)

        result = [
            {
                "query_id": q.id,
                "company": q.company_name,
                "origin": q.origin_port,
                "destination": q.destination_port,
                "shipment_status": q.shipment_status,
                "quote_shared": q.quote_shared,
                "next_action": q.next_action,
            }
            for q in queries
        ]
        return json.dumps(result, indent=2)


@tool
def get_query_details(query_id: int):
    """
    Get complete details of a freight query using its ID.
    """

    with get_db() as db:

        query = crud.get_query(db, query_id)

        if not query:
            return json.dumps(
                {
                    "success": False,
                    "message": f"No freight query found with ID {query_id}.",
                }
            )

        result = {
            "success": True,
            "query": {
                "query_id": query.id,
                "company": query.company_name,
                "origin": query.origin_port,
                "destination": query.destination_port,
                "shipment_status": query.shipment_status,
                "quote_shared": query.quote_shared,
                "next_action": query.next_action,
                "next_action_date": (
                    query.next_action_date.isoformat()
                    if query.next_action_date is not None
                    else None
                ),
                "created_at": (
                    query.created_at.isoformat()
                    if query.created_at is not None
                    else None
                ),
                "updated_at": (
                    query.updated_at.isoformat()
                    if query.updated_at is not None
                    else None
                ),
            },
        }

        return json.dumps(result, indent=2)


@tool
def share_quote(query_id: int):
    """
    Use the available tools whenever appropriate.

Before calling a tool, verify that all required information is available.

If required parameters are missing, ask the user for clarification instead of guessing.

Never fabricate tool arguments.
    """
    ## GuardRails Validation 
    result = guard.validate(
        user_message="",      # Will be used later for intent validation
        tool_name="share_quote",
        tool_args={
            "query_id": query_id,
        },
    )

    if not result.allowed:
        return json.dumps(
            {
                "success": False,
                "message": result.message,
            },
            indent=2,
        )

    with get_db() as db:

        query = crud.share_quote(db, query_id)

        if query is None:
            return json.dumps(
                {
                    "success": False,
                    "message": f"No freight query found with ID {query_id}.",
                }
            )

        result = {
            "success": True,
            "message": f"Quotation shared successfully for query {query_id}.",
            "query_id": query.id,
            "quote_shared": query.quote_shared,
            "shipment_status": query.shipment_status,
        }
        return json.dumps(result, indent=2)


@tool
def update_shipment_status(
    query_id: int,
    shipment_status: str,
):
    """
    Update the shipment status of a freight query.
    """
    ## GuardRail Validation
    result = guard.validate(
        user_message="",      # Will be used later for intent validation
        tool_name="update_shipment_status",
        tool_args={
            "query_id": query_id,
            "shipment_status": shipment_status,
        },
    )

    if not result.allowed:
        return json.dumps(
            {
                "success": False,
                "message": result.message,
            },
            indent=2,
        )

    with get_db() as db:

        try:
            query = crud.update_shipment_status(
                db,
                query_id,
                shipment_status,
            )
        except ValueError as e:
            return json.dumps(
                {
                    "success": False,
                    "message": str(e),
                }
            )

        if query is None:
            return json.dumps(
                {
                    "success": False,
                    "message": f"No freight query found with ID {query_id}.",
                }
            )

        
        result = {
            "success": True,
            "query_id": query.id,
            "company": query.company_name,
            "shipment_status": query.shipment_status,
        }

        return json.dumps(result, indent=2)
