"""Password-gated entry point for the hosted procurement application."""
import os
import secrets
import time
import streamlit as st

st.set_page_config(page_title='Freight Procurement', page_icon='🚢', layout='wide')
expected = os.getenv('PROCUREMENT_TEAM_PASSWORD', '')
if len(expected) < 24:
    st.error('Application access is not configured. Contact the administrator.')
    st.stop()

if not st.session_state.get('team_authenticated', False):
    st.title('Freight Procurement')
    st.caption('Company team access')
    with st.form('team_login'):
        supplied = st.text_input('Team password', type='password')
        submitted = st.form_submit_button('Sign in')
    if submitted:
        if secrets.compare_digest(supplied.encode(), expected.encode()):
            st.session_state.clear()
            st.session_state['team_authenticated'] = True
            st.session_state['team_authenticated_at'] = time.time()
            st.rerun()
        else:
            st.error('Incorrect password.')
    st.stop()

if time.time() - st.session_state.get('team_authenticated_at', 0) > 8 * 3600:
    st.session_state.clear()
    st.rerun()

with st.sidebar:
    st.caption('Company procurement workspace')
    if st.button('Sign out'):
        st.session_state.clear()
        st.rerun()

# Import only after authentication: no procurement data loaded for anonymous users.
from procurement import render_procurement
render_procurement()
