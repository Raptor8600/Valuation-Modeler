"""Sidebar (data source, basis, units), session state -> engine inputs, page header."""	
import json	
import os 
import re 

import streamlit as st 

from valuation import app_model, engine, checks 
from valuation.app_model import FIELDS, IRR_FIELDS, SCEN_FIELDS, from_display 
from valuation.builder_bridge import parse_snapshot	
from valuation.company import CompanyData 
from valuation.data_sources import load_snapshot, fetch_live_snapshot, ROOT 
__build__ = "e4f8e46f28d49aaa" 

PREFIXES = ("ov_", "vec_", "sw_", "set_")	
DISCLAIMER = ("Educational tool, not investment advice. Market data comes from Yahoo Finance via the unofficial yfinance " 
              "library (third-party, may be delayed or differ from the exchange); financial statements come from SEC XBRL "	
              "filings. Check every input against the linked filing before relying on any output.") 


@st.cache_data(ttl=900, show_spinner="Fetching SEC filings and Yahoo Finance data…")	
def _fetch(ticker, _ua):  # leading underscore: the contact is not part of the cache key, so it is not kept	
    # not written to the server's disk: on a hosted app that disk is shared by every visitor and wiped on restart.	
    # Each search lives in the visitor's own session (My searches) and can be downloaded from the Download tab. 
    return fetch_live_snapshot(ticker, _ua, save=False) 


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


PAGES = ["Start here (guide)", "Live search", "My searches", "Examples"] 
EXAMPLES = { 
    "DDOG - Datadog (real data, Non-GAAP & GAAP)": "DDOG_2026-11-22T2117_transcribed.json",	
    "SMPL - profitable company (made-up numbers)": "SMPL_synthetic_profit.json",	
    "SMPL - loss-making company (made-up numbers)": "SMPL_synthetic_loss.json", 
} 


def go(page): 
    """Button callback: switch page (runs before widgets are drawn, so it may set the radio's value).""" 
    st.session_state["page"] = page 


def remember(snap):	
    """Keep a live search in this browser session only (other visitors never see it).""" 
    mine = st.session_state.setdefault("my_snaps", {}) 
    key = f"{snap['_meta']['ticker']} - fetched {snap['_meta']['fetched_at']}" 
    mine[key] = snap	
    st.session_state["current_search"] = key 


def sidebar():	
    """Navigation + the data for the chosen page. Returns (page, snapshot or None, company or None, basis or None).""" 
    sb = st.sidebar	
    sb.title("Valuation Modeler")	
    page = sb.radio("Go to", PAGES, key="page")	
    snap = None 
    if page == "Live search": 
        snap = live_search_panel() 
    elif page == "My searches": 
        mine = st.session_state.get("my_snaps", {}) 
        up = sb.file_uploader("Re-open a downloaded search (.json)", type=["json"]) 
        if up is not None: 
            try:	
                remember(json.loads(up.getvalue().decode("utf-8"))) 
            except Exception as ex:	
                sb.error(f"Not a valid search file: {ex}")	
        mine = st.session_state.get("my_snaps", {}) 
        if mine: 
            keys = list(mine) 
            cur = st.session_state.get("current_search")	
            choice = sb.selectbox("Your searches this session", keys, index=keys.index(cur) if cur in keys else 0)	
            snap = mine[choice] 
    elif page == "Examples": 
        ex = sb.radio("Example", list(EXAMPLES), key="example") 
        snap = _load(os.path.join(ROOT, "data_snapshots", "reference", EXAMPLES[ex])) 
    if not snap: 
        return page, None, None, None	
    sb.divider() 
    sb.subheader("Accounting basis") 
    basis = sb.radio("Applies to every tab", ["Non-GAAP", "GAAP"], key="basis", horizontal=True, 
                     help="Non-GAAP adds back stock-based compensation and acquired-intangible amortization; "	
                          "GAAP uses operating income as reported.") 
    sb.selectbox("Money units", ["$M", "$B", "$K"], key="unit")	
    snap_id = f"{snap['_meta'].get('path', '')}|{snap['_meta'].get('fetched_at', '')}|{snap['_meta']['ticker']}" 
    if st.session_state.get("snap_id") != snap_id:	
        clear_inputs()	
        st.session_state["snap_id"] = snap_id	
    if sb.button("Reset all overrides"): 
        clear_inputs() 
        st.rerun() 
    company = CompanyData.from_builder(_parse(snap_id, basis, snap)) 
    return page, snap, company, basis 


def live_search_panel(): 
    """Ticker box on the main page. A successful search is remembered under My searches.""" 
    st.header("Live search")	
    st.markdown("Type a US-listed ticker. The app pulls the latest 10-K / 10-Q figures from the SEC and the share price, " 
                "beta and Treasury yield from Yahoo Finance, then builds the full model. Takes about 10-20 seconds.")	
    c1, c2 = st.columns([1, 2])	
    t = c1.text_input("Ticker", value=st.session_state.get("live_ticker", ""), placeholder="e.g. MSFT").strip().upper() 
    ua = c2.text_input("Your name and email (required by the SEC)", key="sec_contact", placeholder="Jane Doe jane@example.com") 
    st.caption("Why: the SEC asks every program that downloads its data to identify itself with a name and email. Yours is " 
               "sent only to the SEC, as part of each request to sec.gov - not to this project or anyone else - and is "	
               "not saved: it is forgotten when you close the page.")	
    ok = bool(t) and bool(re.search(r"\S+@\S+\.\S+", ua or "")) and len((ua or "").split()) >= 2 
    if t and not ok: 
        st.info("Enter your name and email (e.g. Jane Doe jane@example.com) to run the search.") 
    if st.button("Run search", type="primary", disabled=not ok): 
        try: 
            remember(_fetch(t, ua.strip()))	
            st.session_state["live_ticker"] = t 
        except Exception as ex:      # network errors, unknown ticker 
            st.error(f"Search failed: {ex}") 
    cur = st.session_state.get("current_search")	
    snap = st.session_state.get("my_snaps", {}).get(cur) 
    if snap and snap["_meta"]["ticker"] == t:	
        st.success(f"Showing {cur}. It is also saved under **My searches** for this session.") 
        return snap	
    return None	


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
    for name, _, kind in IRR_FIELDS + SCEN_FIELDS:	
        v = from_display(kind, ss.get(f"ov_{name}"), unit)	
        if v is not None: 
            ov[name] = v 
    for vec in engine.VECTOR_INPUTS: 
        vals = [from_display("pct", ss.get(f"vec_{vec}_{i}"), unit) for i in range(10)]	
        if any(x is not None for x in vals):	
            ov[vec] = vals 
    switches = {k[3:]: v for k, v in ss.items() if k.startswith("sw_")} 
    return settings, ov, switches 


def count_changed_switches(company, switches): 
    """Only switches the user actually changed from the company defaults count as overrides.""" 
    n = 0	
    for k, v in switches.items(): 
        if k.startswith("inc::"): 
            item = next((i for i in company.instants if i["label"] == k[5:]), None) 
            n += item is not None and bool(v) != bool(item["include"])	
        elif k == "ni_override": 
            n += v is not None	
        elif hasattr(company, k): 
            n += v != getattr(company, k)	
    return n	


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
    scenario_bar(res)	
    meta = company.snapshot_meta 
    if meta.get("synthetic"): 
        st.error("SYNTHETIC TEST DATA - invented numbers, not a real company.") 
    elif meta.get("kind") == "transcribed":	
        st.warning("Reference snapshot: " + meta.get("provenance", ""))	
    n_ov = len(ov) + count_changed_switches(company, switches) 
    summary = checks.summary(checks.run_checks(res)) 
    st.caption(f"{DISCLAIMER}  ·  Overrides active: {n_ov}  ·  Checks: {summary}") 
    if res.missing: 
        st.error("Missing inputs (blank, never guessed): " + ", ".join(res.missing) + 
                 ". Type them on the Inputs tab from the linked filing.")	
    return res 


def scenario_bar(res): 
    """Bear / Base / Bull / weighted value today next to the current price - always at the top.""" 
    if res.dcf is None or res.scen is None:	
        return 
    sc, px = res.scen, res.inputs["in_Price"]	
    cols = st.columns(5) 
    cols[0].metric("Current share price", f"${px:,.2f}")	
    for col, name in zip(cols[1:4], ("Bear", "Base", "Bull")):	
        c = sc["cases"][name]	
        col.metric(f"{name} case - value today ({c['weight']:.0%})", "n/a" if c["v0"] is None else f"${c['v0']:,.2f}", 
                   None if c["v0"] is None else f"{c['v0'] / px - 1:+.1%} vs price") 
    cols[4].metric("Probability-weighted", "n/a" if sc["v0"] is None else f"${sc['v0']:,.2f}", 
                   None if sc["v0"] is None else f"{sc['v0'] / px - 1:+.1%} vs price") 
    st.caption("Each case runs the full DCF on its own path (Bear and Bull shift the automatic fade by ±5pp growth and ±3pp " 
               "margin unless you edit them). Weights, horizon and price targets: DCF tab → Scenarios.") 


def basis_badge(res): 
    st.caption(f"Accounting basis: **{res.settings['in_Basis']}** · WACC mode: {res.settings['in_WACCMode']} · "	
               f"Terminal method: {res.settings['in_TVMethod']} · Discounting: {res.settings['in_Timing']}") 
