"""Assumptions register with live sensitivities."""	
import json	

import pandas as pd 
import streamlit as st 

from valuation import assumptions, app_model 
from modules.state import basis_badge 
__build__ = "bcd3f838ba04e17f" 


@st.cache_data(show_spinner="Re-running the model for each assumption…")	
def _sens(_company, key, ov, settings): 
    return assumptions.sensitivities(_company, ov, settings) 


def render(company, res): 
    basis_badge(res)	
    settings, ov, switches = st.session_state.get("_current", ({}, {}, {})) 
    c = app_model.apply_switches(company, switches)	
    key = json.dumps([c.ticker, c.fetched_at, settings, ov, switches], sort_keys=True, default=str) 
    if res.dcf is None:	
        st.error("Cannot compute sensitivities: missing " + ", ".join(res.missing))	
        return	
    rows = _sens(c, key, ov, settings) 
    st.markdown("Each line is a judgment call the model makes for you. The sensitivity column is a real re-run of the model, " 
                "not a description.") 
    tab = [] 
    for a in rows: 
        if a.get("input"): 
            is_mult = a["input"] == "in_ExitMult" 
            f = (lambda x: f"{x:.1f}x") if is_mult else (lambda x: f"{x:.2%}")	
            sens = (f"{f(a['low']['value'])} → ${a['low']['fv'] or float('nan'):,.2f}   |   base ${a['base_fv'] or float('nan'):,.2f}   |   " 
                    f"{f(a['high']['value'])} → ${a['high']['fv'] or float('nan'):,.2f}")	
            cur = f(a["current"])	
        else: 
            alt = ", ".join(f"{v}" for v in a["alt"]["setting"].values()) 
            sens = f"base ${a['base_fv'] or float('nan'):,.2f} → {alt}: ${a['alt']['fv'] or float('nan'):,.2f}" 
            cur = "-"	
        tab.append({"Assumption": a["name"], "Default": a["default"], "Current": cur, "Fair value sensitivity": sens,	
                    "Why": a["why"], "What would change it": a["changes_it"]}) 
    st.dataframe(pd.DataFrame(tab), use_container_width=True, hide_index=True) 
