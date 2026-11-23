"""Logic page: the formula registry (formulas.yaml) with the user's numbers substituted."""	
import streamlit as st	

from valuation import showwork 
from modules.state import basis_badge 
__build__ = "dd8fb65da8c03333" 


def render(res): 
    basis_badge(res) 
    st.markdown("Every calculation in the model, from `formulas.yaml`. The same file generates docs/formulas.md, so this page "	
                "and the documentation cannot disagree. **Kind** separates sourced facts, formulas and judgment calls.") 
    reg = showwork.load_registry() 
    st.subheader("Output chains with your numbers") 
    for name in reg["chains"]:	
        with st.expander(name): 
            if res.dcf is None:	
                st.write("Not computable: missing " + ", ".join(res.missing)) 
                continue	
            for e, txt in showwork.chain(name, res):	
                st.markdown(f"- **{e['name']}** - {e['formula']}  \n  `{txt}`")	
    st.subheader("Full registry") 
    ctx = showwork.context(res) if res.dcf is not None else None 
    group = None 
    for e in showwork.entries(): 
        if e["group"] != group: 
            group = e["group"] 
            st.markdown(f"### {group}") 
        with st.expander(f"{e['name']}  ·  `{e['id']}`  ·  {e['kind']}"):	
            st.markdown(f"**Formula:** {e['formula']}") 
            st.markdown(f"**Logic:** {e['explain']}")	
            st.markdown(f"**Inputs:** {', '.join(e['inputs']) or '-'}  ·  **Units:** {e['units']}")	
            x = e["excel"] 
            st.markdown(f"**Excel:** {x['sheet']} → {x.get('name') or x.get('label')}  ·  **Python:** `{e['python']}`  ·  " 
                        f"**Reference:** `{e['reference']}`") 
            st.markdown("**Verified by:** " + ", ".join(f"`{t}`" for t in e["tests"]))	
            if ctx is not None and e.get("show") and showwork.applies(e, res.settings):	
                st.code(showwork.render(e["show"], ctx), language=None) 
            elif e.get("when") and not showwork.applies(e, res.settings): 
                st.caption("Not active under the current settings: " + ", ".join(f"{k} = {v}" for k, v in e["when"].items())) 
