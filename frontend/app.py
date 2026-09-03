import streamlit as st
from api import (get_dashboard_stats,get_all_queries,chat_with_ai,)
import pandas as pd

st.set_page_config(
    page_title="AI Freight Management System",
    page_icon="🚚",
    layout="wide",
)

st.title("🚚 AI Freight Management System")

st.markdown("---")

tab1, tab2, tab3 = st.tabs(
    [
        "📊 Dashboard",
        "📦 Freight Queries",
        "🤖 AI Assistant",
    ]
)

with tab1:
    st.header("📊 Dashboard")

    stats = get_dashboard_stats()

    if "error" in stats:
        st.error(stats["error"])

    else:
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Total Queries", stats["total_queries"])

        with col2:
            st.metric("Quotes Shared", stats["quotes_shared"])

        with col3:
            st.metric("Pending Quotes", stats["pending_quotes"])

        st.write("")

        col4, col5, col6 = st.columns(3)

        with col4:
            st.metric("Booked Shipments", stats["booked_shipments"])

        with col5:
            st.metric("Delivered Shipments", stats["delivered_shipments"])

        with col6:
            st.metric("Overdue Follow-ups", stats["overdue_followups"])
   

with tab2:

    st.header("📦 Freight Queries")

    queries = get_all_queries()

    if "error" in queries:
        st.error(queries["error"])

    else:

        df = pd.DataFrame(queries)

        columns_to_show = [
            "id",
            "company_name",
            "origin_port",
            "destination_port",
            "container_type",
            "quote_shared",
            "shipment_status",
            "validation_status",
        ]

        st.dataframe(
            df[columns_to_show],
            use_container_width=True,
            hide_index=True,
        )
with tab3:

    col1, col2 = st.columns([8, 2])

    with col1:
        st.header("🤖 AI Freight Assistant")

    with col2:
        if st.button("🗑 Clear"):
            st.session_state.messages = []
            st.rerun()

    # Everything below is OUTSIDE col1 and col2
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Display chat history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Chat input
    prompt = st.chat_input("Ask about shipments, quotes, follow-ups...")

    if prompt:

        st.session_state.messages.append(
            {
                "role": "user",
                "content": prompt,
            }
        )

        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("🤖 AI is analyzing your request..."):

                response = chat_with_ai(prompt)

                if "error" in response:
                    answer = response["error"]
                else:
                    answer = response.get(
                        "response",
                        "No response received."
                    )

                st.markdown(answer)

        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": answer,
            }
        )