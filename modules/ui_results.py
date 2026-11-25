"""DCF, Reverse DCF and IRR tabs. Every headline number has a 'show your work' panel under it."""	
import pandas as pd	
import streamlit as st 

from valuation import showwork, defaults as D 
from valuation.app_model import IRR_FIELDS, fmt 
from modules.state import basis_badge 
__build__ = "92a48774624fe8de" 


def show_work(res, chain_name, expanded=False):	
    with st.expander(f"Show your work: {chain_name}", expanded=expanded): 
        for e, txt in showwork.chain(chain_name, res): 
            st.markdown(f"**{e['name']}** · `{e['id']}`  \n" 
                        f"Formula: {e['formula']}  \n"	
                        f"With your numbers: `{txt}`  \n" 
                        f"<small>{e['explain']} Excel: {e['excel'].get('sheet')} "	
                        f"{e['excel'].get('name') or e['excel'].get('label')}. Python: `{e['python']}`. " 
                        f"Verified by: {', '.join(e['tests'])}</small>", unsafe_allow_html=True)	


def _pct(x):	
    return "n/a" if x is None else f"{x:.2%}"	


def _px(x): 
    return "n/a" if x is None else f"${x:,.2f}" 


def _m(x): 
    return "n/a" if x is None else f"{x:,.1f}" 


def scenario_table(res, extra=None): 
    """Bear / Base / Bull / weighted / current price. extra: 'cagr' (Reverse DCF) or 'ret' (IRR).""" 
    sc, px = res.scen, res.inputs["in_Price"] 
    if sc is None:	
        return 
    H = sc["H"]	
    rows = []	
    for name in ("Bear", "Base", "Bull"): 
        c = sc["cases"][name] 
        r = {"Case": name, "Weight": f"{c['weight']:.0%}", "Value today (DCF)": _px(c["v0"]), 
             "vs price": "n/a" if c["v0"] is None else f"{c['v0'] / px - 1:+.1%}", f"Price target @ {H:g} yrs": _px(c["pt"])}	
        if extra == "cagr":	
            r["10-yr revenue CAGR"] = _pct(c["cagr"]) 
        if extra == "ret": 
            r["Return to target /yr"] = "n/a" if c["pt"] is None or c["pt"] <= 0 else f"{(c['pt'] / px) ** (1 / H) - 1:.1%}" 
        rows.append(r) 
    w = {"Case": "Probability-weighted", "Weight": f"{sc['weight_sum']:.0%}", "Value today (DCF)": _px(sc["v0"]), 
         "vs price": "n/a" if sc["v0"] is None else f"{sc['v0'] / px - 1:+.1%}", f"Price target @ {H:g} yrs": _px(sc["pt"])}	
    p = {"Case": "Current share price", "Weight": "", "Value today (DCF)": _px(px), "vs price": "", 
         f"Price target @ {H:g} yrs": _px(px)} 
    if extra == "cagr": 
        w["10-yr revenue CAGR"] = ""	
        p["Case"] = "Current price / market-implied" 
        p["10-yr revenue CAGR"] = res.rdcf["solution_text"] or _pct(res.rdcf["g"])	
    if extra == "ret": 
        w["Return to target /yr"] = "n/a" if sc["pt"] is None or sc["pt"] <= 0 else f"{(sc['pt'] / px) ** (1 / H) - 1:.1%}"	
        p["Return to target /yr"] = ""	
    st.subheader("Bear / Base / Bull vs today's price")	
    st.dataframe(pd.DataFrame(rows + [w, p]).set_index("Case"), use_container_width=True) 
    if abs(sc["weight_sum"] - 1) > 1e-9: 
        st.warning(f"Scenario weights add up to {sc['weight_sum']:.0%}, not 100%.") 
    if extra is None: 
        with st.expander("Scenario weights and price-target horizon"): 
            cc = st.columns(4) 
            cc[0].number_input("Horizon (years, 0-10)", value=None, min_value=0.0, max_value=10.0, key="ov_th_H", 
                               placeholder=f"{D.THESIS_H:g}")	
            for col, name in zip(cc[1:], ("Bear", "Base", "Bull")): 
                col.number_input(f"{name} weight (%)", value=None, key=f"ov_th_W{name}",	
                                 placeholder=f"{D.SCEN_WEIGHTS[name] * 100:g}")	
            st.caption("Shape the Bear and Bull paths on Inputs → Forecast Builder overrides (Bear / Bull rows). " 
                       "The price target is each case's DCF value rolled forward to the horizon.") 
        show_work(res, "Scenarios (Bear / Base / Bull)") 


def render_dcf(res):	
    basis_badge(res)	
    if res.dcf is None: 
        st.error("Cannot compute: missing " + ", ".join(res.missing)) 
        return 
    d, v = res.dcf, res.inputs 
    c = st.columns(5) 
    c[0].metric("Fair value / share", _px(d["fv"]), None if d["upside"] is None else f"{d['upside']:+.1%} vs price")	
    c[1].metric("Enterprise value ($M)", _m(d["ev"])) 
    c[2].metric("Active WACC", _pct(v["in_WACC"])) 
    c[3].metric("Terminal value share of EV", _pct(d["tv_share"])) 
    c[4].metric("Guardrail", d["guard"].split(":")[0], d["guard"].split(":", 1)[1].strip() if ":" in d["guard"] else None,	
                delta_color="off") 
    scenario_table(res)	
    show_work(res, "Fair value per share", expanded=True) 
    show_work(res, "WACC")	
    show_work(res, "Terminal value")	
    sch = d["schedule"]	
    cols = [f"Year {t}" for t in range(1, 11)] + ["Terminal (Yr 11)"] 
    lines = [("Revenue growth", sch["growth"], "pct"), ("Revenue", sch["rev"], "m"), ("EBIT", sch["ebit"], "m"), 
             ("Operating margin", sch["margin"], "pct"), ("Taxes on EBIT", sch["tax"], "m"), ("NOPAT", sch["nopat"], "m"), 
             ("D&A", sch["da"], "m"), ("Capex", sch["capex"], "m"), ("Change in NWC", sch["nwc"], "m"), 
             ("Unlevered FCF", sch["ufcf"], "m"), ("Memo: EBITDA", sch["ebitda"], "m")] 
    tab = {lab: [(f"{x:.2%}" if k == "pct" else f"{x:,.1f}") for x in arr] for lab, arr, k in lines} 
    tab["Discount period"] = [f"{x:.1f}" for x in d["per"]] + ["-"] 
    tab["PV of UFCF"] = [f"{x:,.1f}" for x in d["pv"]] + ["-"]	
    st.subheader("Free cash flow build ($M)") 
    st.dataframe(pd.DataFrame(tab, index=cols).T, use_container_width=True)	
    st.subheader("Enterprise-to-equity bridge ($M)")	
    br = [("Σ PV of UFCF, Years 1-10", d["sum_pv"]), ("Terminal value", d["tv"]), ("TV discount period (years)", d["tv_per"]), 
          ("PV of terminal value", d["pv_tv"]), ("Enterprise value", d["ev"]), ("+ Cash & investments", v["in_Cash"]), 
          ("− Debt", v["in_Debt"]), ("− Other claims", v["in_Other"]), ("Equity value", d["equity"]), 
          ("÷ Diluted shares (M)", v["in_Shares"]), ("Fair value per share ($)", d["fv"]),	
          ("Cross-check: implied exit EV/EBITDA", d["imp_mult"]), ("Cross-check: implied perpetual growth", d["imp_g"])]	
    st.table(pd.DataFrame([(a, "n/a" if b is None else (f"{b:.2%}" if "growth" in a else f"{b:,.3f}")) for a, b in br], 
                          columns=["Line", "Value"])) 
    st.subheader("Value over time - price at the end of each year if the forecast is delivered") 
    show_work(res, "Value over time") 
    if res.vot[0] is not None: 
        vt = pd.DataFrame([{"Year": x["t"], "EV ($M)": f"{x['ev']:,.1f}", "Net cash ($M)": f"{x['net_cash']:,.1f}",	
                            "Equity ($M)": f"{x['equity']:,.1f}", "Shares (M)": f"{x['shares']:,.2f}", 
                            "Implied price ($)": f"${x['price']:,.2f}", 
                            "Annualized return from today": "-" if x["ann_return"] is None else f"{x['ann_return']:.1%}"} 
                           for x in res.vot]).set_index("Year")	
        st.dataframe(vt, use_container_width=True) 
    st.subheader("Sensitivity: fair value per share")	
    show_work(res, "Sensitivity") 
    s = res.sens	
    colnames = [(f"{x:.1%}" if s["perp"] else f"{x:.1f}x") for x in s["cols"]]	
    grid = pd.DataFrame([[None if x is None else round(x, 2) for x in line] for line in s["grid"]],	
                        index=[f"WACC {w:.1%}" for w in s["rows"]], columns=colnames) 
    st.dataframe(grid, use_container_width=True) 
    st.caption(f"Columns: {'terminal growth' if s['perp'] else 'exit multiple'}. Centre = base case " 
               f"({_px(s['centre'])}; fair value {_px(d['fv'])}).") 


def render_rdcf(res): 
    basis_badge(res) 
    if res.rdcf is None: 
        st.error("Cannot compute: missing " + ", ".join(res.missing))	
        return 
    rd, v = res.rdcf, res.inputs	
    c = st.columns(4)	
    c[0].metric("Implied 10-year revenue growth", rd["solution_text"] or _pct(rd["g"])) 
    c[1].metric("Market EV ($M)", _m(rd["target"])) 
    c[2].metric("Gap vs your forecast CAGR", _pct(rd["gap"]), help="Positive = market expects more growth than your forecast") 
    c[3].metric("Consensus next-FY growth", _pct(v.get("d_Cons1y")))	
    (st.success if rd["status"].startswith("OK") else st.warning)(rd["status"])	
    scenario_table(res, extra="cagr") 
    show_work(res, "Implied growth (Reverse DCF)", expanded=True) 
    if rd["proof"]: 
        p = rd["proof"]["schedule"] 
        st.subheader("Proof schedule at the implied growth ($M)") 
        tab = {"Revenue": p["rev"], "Operating margin": p["margin"], "NOPAT": p["nopat"], "UFCF": p["ufcf"]}	
        df = pd.DataFrame({k: [f"{x:.2%}" if k == "Operating margin" else f"{x:,.1f}" for x in val] for k, val in tab.items()}, 
                          index=[f"Year {t}" for t in range(1, 11)] + ["Terminal (Yr 11)"]).T 
        st.dataframe(df, use_container_width=True) 
        st.markdown(f"Σ PV {rd['proof']['sum_pv']:,.3f} + PV(TV) {rd['proof']['pv_tv']:,.3f} = **{rd['ev']:,.3f}** vs market EV "	
                    f"**{rd['target']:,.3f}** → tie-out {rd['tieout']:+.2e} $M") 
        st.subheader("Implied share price over time (if the market's growth is delivered)")	
        st.dataframe(pd.DataFrame([{"Year": x["t"], "Implied price ($)": round(x["price"], 2), 
                                    "Annualized return": None if x["ann_return"] is None else f"{x['ann_return']:.1%}"}	
                                   for x in rd["path"]]).set_index("Year").T, use_container_width=True)	
    with st.expander("Solver detail: grid scan and bisection steps"):	
        st.dataframe(pd.DataFrame({"growth": rd["grid"], "model EV − market EV ($M)": rd["f"], "sign change": rd["flags"]}), 
                     use_container_width=True, height=240) 
        if rd["steps"]: 
            st.dataframe(pd.DataFrame(rd["steps"], columns=["low", "high", "f(low)", "midpoint", "f(mid)"]), 
                         use_container_width=True, height=240) 


def render_irr(res): 
    basis_badge(res) 
    if res.irr is None:	
        st.error("Cannot compute: missing " + ", ".join(res.missing)) 
        return	
    c = st.columns(4)	
    c[0].selectbox("Valuation multiple", D.IRR_MULTS, key="set_irr_Mult", index=D.IRR_MULTS.index(res.settings["irr_Mult"])) 
    c[1].selectbox("Timing basis", D.IRR_BASIS, key="set_irr_Basis", index=D.IRR_BASIS.index(res.settings["irr_Basis"])) 
    c[2].selectbox("Metric growth source", D.GROWTH_SRC, key="set_irr_GSrc", index=D.GROWTH_SRC.index(res.settings["irr_GSrc"])) 
    c[3].selectbox("Net cash at exit (EV multiples)", D.CASH_EXIT, key="set_irr_Cash", index=D.CASH_EXIT.index(res.settings["irr_Cash"]))	
    cc = st.columns(len(IRR_FIELDS))	
    for col, (name, label, kind) in zip(cc, IRR_FIELDS): 
        col.number_input(label + (" (%)" if kind == "pct" else ""), value=None, key=f"ov_{name}", placeholder="auto") 
    ir = res.irr 
    k = st.columns(4) 
    k[0].metric(f"IRR ({ir['H']} years, incl. dividends)", ir["irr_note"] or _pct(ir["irr"])) 
    k[1].metric("Exit share price", _px(ir["exit_price"]))	
    k[2].metric("Entry → exit multiple", f"{fmt('num', ir['entry'])} → {fmt('num', ir['exit'])}") 
    k[3].metric("Total return multiple", "n/m" if ir["total_multiple"] is None else f"{ir['total_multiple']:.2f}x") 
    show_work(res, "IRR", expanded=True) 
    scenario_table(res, extra="ret")	
    st.subheader("Projections (per share)") 
    st.dataframe(pd.DataFrame([{"Year": r["t"], "Metric total ($M)": r["metric_total"], "Shares (M)": r["shares"],	
                                "Metric / share": r["metric_ps"], "DPS": r["dps"], "Cumulative dividends": r["cum_div"], 
                                "Net cash / share": r["nc_ps"], "Price if sold": r["exit_price"], "Cash flow for IRR": r["cash_flow"]}	
                               for r in ir["rows"]]).set_index("Year"), use_container_width=True)	
    st.subheader("Sensitivity: entry multiple (rows) × exit multiple (columns), annualized return")	
    s = ir["sens"] 
    st.dataframe(pd.DataFrame([[None if x is None else f"{x:.1%}" for x in line] for line in s["grid"]], 
                              index=[fmt("num", x) for x in s["rows"]], columns=[fmt("num", x) for x in s["cols"]]), 
                 use_container_width=True) 
    with st.expander("Multiples repository (11 multiples × trailing / forward)"): 
        st.dataframe(pd.DataFrame([{"Multiple": r["key"], "Today": r["multiple"], "Metric / share": r["metric_ps"], 
                                    f"Metric CAGR ({ir['H']}y)": r["growth"]} for r in ir["repo"]]), 
                     use_container_width=True, hide_index=True)	
