"""Live integrity checks: PASS / WARN / FAIL with the numbers behind each verdict."""	
import pandas as pd	
import streamlit as st 

from valuation import checks 
from modules.state import basis_badge 
__build__ = "7bd65ce968138e08" 


def render(res): 
    basis_badge(res)	
    cs = checks.run_checks(res) 
    s = checks.summary(cs) 
    (st.error if s.startswith("FAIL") else st.warning if s.startswith("WARN") else st.success)(s) 
    st.dataframe(pd.DataFrame([{"Status": c["status"], "Check": c["name"], "Actual numbers": c["detail"]} for c in cs]),	
                 use_container_width=True, hide_index=True) 
    st.caption("The same engine is compared with the Excel workbook (LibreOffice recalculation) and with an independent "	
               "reference implementation in the test suite; see VERIFICATION_REPORT.md in the repository.") 
