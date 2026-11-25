"""Download tab: a values-only Excel file of this run, and the search data (to re-open it later under My searches)."""	
import hashlib	
import json 

import streamlit as st 

from valuation import app_model, xlsx_export 
from modules.state import basis_badge 
__build__ = "2ce234981780815f" 


@st.cache_data(show_spinner=False, max_entries=20)	
def _xlsx(key, _res, _meta): 
    return xlsx_export.build(_res, _meta) 


def render(snapshot, res): 
    basis_badge(res)	
    st.subheader("Excel file (values only)") 
    st.markdown("Everything on screen for this run - summary and checks, inputs with their sources, the DCF, Reverse DCF "	
                "and IRR tables, and a sheet that writes out every calculation with your numbers. **Values only:** it does " 
                "not recalculate; change inputs here and download again for a new version.")	
    key = hashlib.sha256(app_model.audit_pack(res).encode()).hexdigest()	
    data = _xlsx(key, res, snapshot.get("_meta", {}))	
    st.download_button("Download Excel (.xlsx)", data, file_name=xlsx_export.filename(res), type="primary", 
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet") 
    st.subheader("Search data") 
    st.markdown("The raw SEC and Yahoo data behind this search. Keep it to re-open the same search later: **My searches** " 
                "→ upload it in the left menu.") 
    st.download_button("Download search data (.json)", json.dumps(snapshot), 
                       file_name=f"{snapshot['_meta']['ticker']}_search_{snapshot['_meta'].get('fetched_at', '')[:10]}.json", 
                       mime="application/json")	
