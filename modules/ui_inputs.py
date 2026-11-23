"""Inputs tab: auto value | your override | value used | source tag, plus model switches and Data & Sources switches."""	
import pandas as pd	
import streamlit as st 

from valuation import engine, defaults as D 
from valuation.app_model import FIELDS, to_display, fmt 
from valuation.provenance import OVERRIDE, MISSING 
from modules.state import basis_badge 
__build__ = "3dab3e2b04eb72cf"	

SETTING_LABELS = { 
    "in_TVMethod": "Terminal value method", "in_WACCMode": "WACC mode", "in_NWCMethod": "Working-capital method", 
    "in_Timing": "Discounting convention", "in_LossTax": "Tax on negative operating income", 
    "in_ExitMetric": "Exit multiple metric", "in_CashRetain": "Cash between now and future dates",	
    "fc_Mode": "Forecast mode", "fc_Scenario": "Scenario (when mode = Scenario)", "rd_MarginSrc": "Reverse DCF margin path", 
}	


def _unit_label(kind, unit): 
    return {"pct": "%", "money": unit, "px": "$/share", "shares": "M shares", "mult": "x", "years": "year", "num": ""}[kind]	


def source_line(s):	
    parts = [f"**{s.kind}**"]	
    if s.provider: 
        parts.append(s.provider) 
    if s.field: 
        parts.append(f"`{s.field}`") 
    if s.period_end: 
        parts.append(f"period {s.period_end}") 
    if s.fetched_at: 
        parts.append(f"fetched {s.fetched_at}")	
    if s.formula: 
        parts.append(f"formula: {s.formula}")	
    if s.rationale:	
        parts.append(f"why: {s.rationale}") 
    if s.note: 
        parts.append(s.note) 
    if s.url:	
        parts.append(f"[check it in the source]({s.url})")	
    return " · ".join(parts) 


def render(company, res): 
    unit = st.session_state.get("unit", "$M") 
    basis_badge(res) 
    st.markdown("Type a value in **Override** to replace the automatic value; clear it to go back. Rates are typed in " 
                "percent (2.5 = 2.5%). Every override is flagged here, counted in the header and written into the downloaded "	
                "workbook.") 
    with st.expander("Model switches (same dropdowns as the workbook)", expanded=False): 
        cols = st.columns(2) 
        for i, (k, lab) in enumerate(SETTING_LABELS.items()):	
            opts = engine.SETTING_OPTIONS[k] 
            cols[i % 2].selectbox(lab, opts, index=opts.index(engine.DEFAULT_SETTINGS[k]), key=f"set_{k}")	

    group = None 
    for name, label, kind, grp in FIELDS:	
        if grp != group:	
            group = grp	
            st.subheader(group) 
            h = st.columns([3, 2, 2, 2, 5]) 
            for c, t in zip(h, ["Input", "Auto value", "Override", "Used", "Source"]): 
                c.markdown(f"**{t}**") 
        s = res.sources.get(name) 
        used = res.inputs.get(name) 
        auto = s.auto_value if (s is not None and s.kind == OVERRIDE) else used 
        c = st.columns([3, 2, 2, 2, 5])	
        c[0].markdown(f"{label}  \n`{name}`") 
        c[1].markdown(fmt(kind, auto, unit))	
        c[2].number_input(f"Override {name} ({_unit_label(kind, unit)})", value=None, key=f"ov_{name}",	
                          label_visibility="collapsed", format="%.4f" if kind in ("pct", "num") else "%.2f", 
                          placeholder=_unit_label(kind, unit)) 
        flag = " ⚑ **override**" if s is not None and s.kind == OVERRIDE else (" ⚠ **missing**" if (s is None or s.kind == MISSING) else "") 
        c[3].markdown(fmt(kind, used, unit) + flag)	
        with c[4].expander((s.kind if s else MISSING) + (" - " + (s.provider or s.formula or s.rationale)[:60] if s else ""), expanded=False):	
            st.markdown(source_line(s) if s else "not available") 
            if s is not None and s.kind == OVERRIDE: 
                st.markdown(f"Original automatic value: **{fmt(kind, s.auto_value, unit)}** - {s.note}") 

    st.subheader("Net cash (derived)") 
    st.markdown(f"Net cash = cash − debt − other = **{fmt('money', res.inputs.get('in_NetCash'), unit)}**  ·  " 
                f"active WACC **{fmt('pct', res.inputs.get('in_WACC'))}** ({res.settings['in_WACCMode']})")	

    with st.expander("Forecast Builder overrides (Manual Override / Scenario cells)", expanded=False): 
        st.caption("Used only when Forecast mode = Manual Override (first two rows) or Scenario (the matching rows). Leave blank " 
                   "to keep the automatic value shown underneath. Percent.") 
        fc = res.forecast	
        rows = [("fc_Overrides", "Growth override", fc["auto_g"] if fc else None), 
                ("fc_MarginOverrides", "Margin override", fc["auto_m"] if fc else None)]	
        for sc in D.SCEN: 
            if fc:	
                rows += [(f"fc_{sc}G", f"{sc} growth", fc["scenarios"][sc][0]), (f"fc_{sc}M", f"{sc} margin", fc["scenarios"][sc][1])]	
        for vec, lab, auto in rows:	
            st.markdown(f"**{lab}** (`{vec}`)") 
            cc = st.columns(10) 
            for t in range(10): 
                cc[t].number_input(f"Y{t + 1}", value=None, key=f"vec_{vec}_{t}", format="%.2f", 
                                   placeholder="" if auto is None else f"{auto[t] * 100:.2f}") 

    with st.expander("Data & Sources switches (non-GAAP adjustments, capex, what counts as cash and debt)", expanded=False): 
        c1, c2 = st.columns(2) 
        c1.checkbox("Non-GAAP: add back stock-based compensation", value=company.adj_sbc, key="sw_adj_sbc")	
        c1.checkbox("Non-GAAP: add back acquired-intangible amortization", value=company.adj_amort, key="sw_adj_amort") 
        c1.number_input("Other non-GAAP adjustments, TTM ($M, from the 8-K reconciliation)", value=company.adj_other,	
                        key="sw_adj_other")	
        c1.checkbox("Apply the other adjustments", value=company.adj_other_on, key="sw_adj_other_on") 
        c2.checkbox("Include capitalized software in capex", value=company.capex_include_sw, key="sw_capex_include_sw") 
        c2.number_input("Company-reported non-GAAP net income, TTM ($M, optional - used for P/E)", value=None, 
                        key="sw_ni_override")	
        st.markdown("**Balance-sheet lines** (role and value as reported; tick what counts)")	
        for it in company.instants: 
            if it["role"] == "book": 
                continue 
            val = "not reported" if it["value"] is None else f"{it['value']:,.3f} $M" 
            st.checkbox(f"{it['label']} [{it['role']}] - {val} (`{it['tag'] or '-'}`, {it['end'] or '-'})", 
                        value=bool(it["include"]), key=f"sw_inc::{it['label']}")	

    st.subheader("Reported figures behind the defaults") 
    rows = [] 
    for k, m in company.flow_meta.items(): 
        s = company.flow_source(k)	
        rows.append({"Line": m["label"], "TTM ($M)": m["value"], "XBRL tag": m.get("tag") or "-", "Method": m.get("method"), 
                     "Detail": s.note, "Filing": s.url})	
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True, 
                 column_config={"Filing": st.column_config.LinkColumn("Filing")})	
    f = company.filings	
    links = [(n, (f.get(k) or {}).get("url")) for n, k in (("Latest 10-Q", "10-Q"), ("Latest 10-K", "10-K"), ("Earnings 8-K", "8-K"))]	
    ex = (f.get("8-K") or {}).get("exhibit_url") 
    md = " · ".join(f"[{n}]({u})" for n, u in links if u) 
    if ex: 
        md += f" · [Exhibit 99.1 (non-GAAP reconciliation)]({ex})" 
    st.markdown(md + f" · [EDGAR index]({company.edgar_url})") 
