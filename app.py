"""Valuation Modeler - Streamlit app.

    streamlit run app.py

Pages: Start here (guide) · Live search · My searches · Examples. Every number on screen can be traced: Inputs tab (auto value, your override, value used, source tag), "show your work"
panels under each result, the Logic page (formula registry), the Assumptions register and the live Checks.
Educational, not investment advice.
"""	
import os	
import sys 

import streamlit as st 
__build__ = "d2cfbae513527593" 

ROOT = os.path.dirname(os.path.abspath(__file__)) 
if ROOT not in sys.path: 
    sys.path.insert(0, ROOT)	

from modules import state, guide, ui_inputs, ui_results, ui_logic, ui_assumptions, ui_checks, ui_download  # noqa: E402 

st.set_page_config(page_title="Valuation Modeler", layout="wide") 

page, snapshot, company, basis = state.sidebar() 
if page == "Start here (guide)":	
    guide.render() 
    st.stop()	
if company is None: 
    if page == "My searches":	
        st.header("My searches")	
        st.info("No searches yet in this session. Run one on **Live search**, or re-open a downloaded search file with "	
                "the uploader in the left menu.") 
        st.button("Go to Live search →", on_click=state.go, args=("Live search",)) 
    st.stop() 

res = state.header(company, basis) 
if page == "Examples": 
    guide.example_intro(company, res, st.session_state.get("example", "")) 

tabs = st.tabs(["Inputs", "DCF", "Reverse DCF", "IRR", "Logic", "Assumptions", "Checks", "Download"]) 
with tabs[0]:	
    ui_inputs.render(company, res) 
with tabs[1]:	
    ui_results.render_dcf(res)	
with tabs[2]: 
    ui_results.render_rdcf(res) 
with tabs[3]: 
    ui_results.render_irr(res)	
with tabs[4]:	
    ui_logic.render(res) 
with tabs[5]: 
    ui_assumptions.render(company, res) 
with tabs[6]: 
    ui_checks.render(res) 
with tabs[7]:	
    ui_download.render(snapshot, res) 
