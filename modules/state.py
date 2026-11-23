"""Sidebar (data source, basis, units), session state -> engine inputs, page header."""	
import os	

import streamlit as st 

from valuation import app_model, engine, checks 
from valuation.app_model import FIELDS, IRR_FIELDS, from_display 
from valuation.builder_bridge import parse_snapshot 
from valuation.company import CompanyData 
from valuation.data_sources import list_snapshots, load_snapshot, fetch_live_snapshot, ROOT	
__build__ = "e4f8e46f28d49aaa" 

PREFIXES = ("ov_", "vec_", "sw_", "set_") 
DISCLAIMER = ("Educational tool, not investment advice. Market data comes from Yahoo Finance via the unofficial yfinance " 
              "library (third-party, may be delayed or differ from the exchange); financial statements come from SEC XBRL "	
              "filings. Check every input against the linked filing before relying on any output.") 


def default_contact():	
    try: 
        v = st.secrets.get("SEC_USER_AGENT", "")	
    except Exception:	
        v = ""	
    return v or os.environ.get("SEC_USER_AGENT", "") 


@st.cache_data(ttl=900, show_spinner="Fetching SEC filings and Yahoo Finance data…") 
def _fetch(ticker, ua): 
    return fetch_live_snapshot(ticker, ua, save=True) 


@st.cache_data(show_spinner=False) 
def _load(path): 
    return load_snapshot(path) 


@st.cache_resource(show_spinner=False)	
def _parse(snap_id, basis, _snap): 
    return parse_snapshot(_snap, basis)	


def clear_inputs():	
    for k in list(st.session_state.keys()): 
        if k.startswith(PREFIXES): 
            del st.session_state[k] 


def sidebar():	
    sb = st.sidebar	
    sb.header("Data") 
    src = sb.radio("Source", ["Reference snapshot (offline)", "Saved snapshot", "Fetch live (SEC + Yahoo)"], key="src") 
    snap = None 
    if src == "Fetch live (SEC + Yahoo)": 
        t = sb.text_input("Ticker", value=st.session_state.get("live_ticker", "DDOG")).strip().upper() 
        ua = sb.text_input("SEC contact (name + email, required by the SEC)", value=default_contact())	
        if sb.button("Fetch"): 
            try: 
                st.session_state["live_snap"] = _fetch(t, ua) 
                st.session_state["live_ticker"] = t	
            except Exception as ex:      # network errors, unknown ticker, missing contact 
                sb.error(f"Fetch failed: {ex}")	
        snap = st.session_state.get("live_snap") 
        if snap:	
            sb.caption(f"Fetched {snap['_meta']['fetched_at']} · saved to {snap['_meta'].get('path', 'data_snapshots/')}")	
    else:	
        files = [p for p in list_snapshots() if ("reference" in p) == (src.startswith("Reference"))] 
        if not files: 
            sb.info("No saved snapshots yet - fetch one live first.") 
        else: 
            choice = sb.selectbox("Snapshot", files, format_func=lambda p: os.path.relpath(p, ROOT)) 
            snap = _load(choice) 
    if not snap: 
        return None, None, None	
    sb.header("Accounting basis") 
    basis = sb.radio("Basis (applies to every tab and the download)", ["Non-GAAP", "GAAP"], key="basis", horizontal=True)	
    sb.selectbox("Money units for display and entry", ["$M", "$B", "$K"], key="unit")	
    snap_id = f"{snap['_meta'].get('path', '')}|{snap['_meta'].get('fetched_at', '')}|{snap['_meta']['ticker']}" 
    if st.session_state.get("snap_id") != snap_id: 
        clear_inputs() 
        st.session_state["snap_id"] = snap_id	
    if sb.button("Reset all overrides"):	
        clear_inputs() 
        st.rerun() 
    company = CompanyData.from_builder(_parse(snap_id, basis, snap)) 
    return snap, company, basis 


def collect(company, basis): 
    """Read every widget value from session state and convert to engine units."""	
    ss, unit = st.session_state, st.session_state.get("unit", "$M") 
    settings = {k: ss[f"set_{k}"] for k in engine.SETTING_OPTIONS if f"set_{k}" in ss} 
    settings["in_Basis"] = basis 
    ov = {}	
    for name, _, kind, _ in FIELDS: 
        v = from_display(kind, ss.get(f"ov_{name}"), unit)	
        if v is not None: 
            ov[name] = v	
    for name, _, kind in IRR_FIELDS:	
        v = from_display(kind, ss.get(f"ov_{name}"), unit)	
        if v is not None: 
            ov[name] = v 
    for vec in engine.VECTOR_INPUTS: 
        vals = [from_display("pct", ss.get(f"vec_{vec}_{i}"), unit) for i in range(10)] 
        if any(x is not None for x in vals): 
            ov[vec] = vals 
    switches = {k[3:]: v for k, v in ss.items() if k.startswith("sw_")} 
    return settings, ov, switches	


def header(company, basis): 
    settings, ov, switches = collect(company, basis)	
    res = app_model.run(company, ov, settings, switches)	
    st.session_state["_current"] = (settings, ov, switches) 
    st.title(f"{company.name} ({company.ticker})") 
    c1, c2, c3, c4 = st.columns(4) 
    c1.markdown(f"**Basis:** `{basis}`")	
    c2.markdown(f"**Latest period:** {company.period_end}")	
    c3.markdown(f"**Data as of:** {company.fetched_at}") 
    if res.dcf and res.dcf["fv"] is not None: 
        c4.markdown(f"**Fair value:** ${res.dcf['fv']:,.2f} vs price ${res.inputs['in_Price']:,.2f}") 
    meta = company.snapshot_meta 
    if meta.get("synthetic"): 
        st.error("SYNTHETIC TEST DATA - invented numbers, not a real company.")	
    elif meta.get("kind") == "transcribed": 
        st.warning("Reference snapshot: " + meta.get("provenance", "")) 
    n_ov = len([k for k in ov]) + len([k for k in switches]) 
    summary = checks.summary(checks.run_checks(res))	
    st.caption(f"{DISCLAIMER}  ·  Overrides active: {n_ov}  ·  Checks: {summary}") 
    if res.missing:	
        st.error("Missing inputs (blank, never guessed): " + ", ".join(res.missing) + 
                 ". Type them on the Inputs tab from the linked filing.")	
    return res	


def basis_badge(res):	
    st.caption(f"Accounting basis: **{res.settings['in_Basis']}** · WACC mode: {res.settings['in_WACCMode']} · " 
               f"Terminal method: {res.settings['in_TVMethod']} · Discounting: {res.settings['in_Timing']}") 
