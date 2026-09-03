from langchain.agents import create_agent

from app.ai.llm import llm
from app.ai.prompts import SYSTEM_PROMPT
from app.ai.tools import dashboard_stats, pending_followups, search_company, get_query_details, share_quote, update_shipment_status

agent = create_agent(
    model=llm,
    tools=[
        dashboard_stats,
        pending_followups,
        search_company,
        get_query_details,
        share_quote,
        update_shipment_status,
    ],
    system_prompt=SYSTEM_PROMPT,
)