import streamlit as st
from procurement import render_procurement
st.set_page_config(page_title='Freight Procurement',page_icon='🚢',layout='wide')
render_procurement()
