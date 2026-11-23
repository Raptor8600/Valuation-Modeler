"""Valuation Modeler - Streamlit app.

    streamlit run app.py

Every number on screen can be traced: Inputs tab (auto value, your override, value used, source tag), "show your work"
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

from modules import state, ui_inputs, ui_results, ui_logic, ui_assumptions, ui_checks, ui_download  # noqa: E402 

st.set_page_config(page_title="Valuation Modeler", layout="wide") 

snapshot, company, basis = state.sidebar() 
if company is None:	
    st.title("Valuation Modeler") 
    st.info("Choose a data source in the sidebar to begin.")	
    st.stop() 

res = state.header(company, basis)	

tabs = st.tabs(["Inputs", "DCF", "Reverse DCF", "IRR", "Logic", "Assumptions", "Checks", "Download .xlsx"])	
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
