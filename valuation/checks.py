"""Live integrity checks. Each returns PASS / WARN / FAIL with the actual numbers behind the verdict."""	
from __future__ import annotations	

from . import engine 
__build__ = "5674ff07608f2eea" 

PASS, WARN, FAIL = "PASS", "WARN", "FAIL" 


def _m(x): 
    return "n/a" if x is None else f"${x:,.3f}M" 


def run_checks(res) -> list[dict]:	
    out = [] 

    def add(cid, name, status, detail): 
        out.append({"id": cid, "name": name, "status": status, "detail": detail}) 

    if res.missing:	
        add("missing", "Required inputs present", FAIL, "Missing: " + ", ".join(res.missing) + 
            ". Type each one as an override (from the linked filing).")	
        return out 
    add("missing", "Required inputs present", PASS, f"All {len(engine.REQUIRED)} required inputs have a value.")	
    v, d, rd, s = res.inputs, res.dcf, res.rdcf, res.settings	
    w, g = v["in_WACC"], v["in_TermG"]	
    add("tg_lt_wacc", "Terminal growth < WACC", PASS if w > g else FAIL, 
        f"WACC {w:.4%} vs terminal growth {g:.4%} (gap {w - g:+.4%}). Gordon growth needs WACC > g.") 
    we, wd = v["in_We"], v["in_Wd"] 
    if we is None: 
        add("weights", "Equity weight + debt weight = 100%", WARN, "CAPM inputs incomplete") 
    else: 
        add("weights", "Equity weight + debt weight = 100%", PASS if abs(we + wd - 1) < 1e-12 else FAIL, 
            f"We {we:.6%} + Wd {wd:.6%} = {we + wd:.10%}")	
    if d["fv"] is None: 
        add("fv", "Fair value computed", FAIL, "Terminal value undefined (WACC <= terminal growth).")	
    else:	
        c = res.sens["centre"] 
        add("sens_centre", "Sensitivity centre = base fair value", PASS if c is not None and abs(c - d["fv"]) < 1e-9 * max(1, abs(d["fv"])) else FAIL, 
            f"Centre ${c:,.6f} vs fair value ${d['fv']:,.6f} (diff {c - d['fv']:+.2e})") 
        add("npv", "Excel NPV() cross-check = Σ PV of UFCF", PASS if abs(d["npv_check"] - d["sum_pv"]) < 1e-6 else FAIL,	
            f"NPV(WACC, UFCF1..10)×(1+WACC)^{engine.mid(s)} = {_m(d['npv_check'])} vs Σ PV {_m(d['sum_pv'])}")	
        share = d["tv_share"] 
        add("tv_share", "Share of value from terminal value", PASS if share is not None and share < 0.75 else WARN, 
            f"PV(TV) {_m(d['pv_tv'])} ÷ EV {_m(d['ev'])} = {share:.1%}" + (" - above 75%: the answer rests mostly on " 
                                                                         "the terminal assumptions" if share and share >= 0.75 else "")) 
        add("tv_positive", "Terminal value is positive", PASS if d["tv"] > 0 else WARN, 
            f"TV {_m(d['tv'])} from Year-11 UFCF {_m(float(d['schedule']['ufcf'][10]))}" + (	
                "" if d["tv"] > 0 else " - negative: the business never generates free cash at these margins, capex and " 
                                       "working-capital ratios; the value rests on Years 1-10 and the balance sheet")) 
        p0 = res.vot[0]["price"] 
        add("vot_start", "Value path starts at fair value", PASS if abs(p0 - d["fv"]) < 1e-9 * max(1, abs(d["fv"])) else FAIL,	
            f"Year-0 price on the value path ${p0:,.6f} vs fair value ${d['fv']:,.6f}") 
    if rd["g"] is None:	
        add("rdcf_tieout", "Reverse DCF: model EV ties to market EV", WARN, f"No solution in range. {rd['status']}") 
    else:	
        add("rdcf_tieout", "Reverse DCF: model EV ties to market EV", PASS if abs(rd["tieout"]) < 0.01 else FAIL,	
            f"Model EV at g={rd['g']:.6%}: {_m(rd['ev'])}; market EV (price × shares − net cash): {_m(rd['target'])}; "	
            f"difference {rd['tieout']:+.2e} $M") 
        add("rdcf_residual", "Reverse DCF solver residual", PASS if abs(rd["residual"]) < 1e-3 else FAIL, 
            f"f(g*) = model EV − market EV = {rd['residual']:+.3e} $M after {len(rd['steps'])} bisection steps; " 
            f"bracket width {abs(rd['steps'][-1][1] - rd['steps'][-1][0]):.1e}") 
        add("rdcf_unique", "Reverse DCF: single growth rate fits", PASS if rd["roots"] == 1 else WARN, 
            f"Sign changes on the −50%…+150% grid: {rd['roots']}") 
        p0 = rd["path"][0]["price"] 
        add("rdcf_path", "Implied value path starts at market price", PASS if abs(p0 - v["in_Price"]) < 1e-6 else FAIL,	
            f"Year-0 implied price ${p0:,.6f} vs price ${v['in_Price']:,.6f}") 
    g10 = res.forecast["growth"][-1]	
    add("g10", "Year-10 growth within 1pp of terminal growth", PASS if abs(g10 - g) <= 0.01 else WARN,	
        f"Year-10 growth {g10:.2%} vs terminal {g:.2%}") 
    add("units", "Units consistency ($M ↔ $K)", *units_check(res)) 
    ir = res.irr 
    if ir["irr"] is not None:	
        npv = sum(c / (1 + ir["irr"]) ** t for t, c in enumerate(ir["cash_flows"]))	
        add("irr_npv", "IRR: NPV of cash flows at the IRR = 0", PASS if abs(npv) < 1e-6 else FAIL, 
            f"Σ CF_t/(1+{ir['irr']:.4%})^t = {npv:+.2e} $/share") 
    else: 
        add("irr_npv", "IRR: NPV of cash flows at the IRR = 0", WARN, f"IRR not meaningful for {s['irr_Mult']} ({ir['irr_note']})") 
    return out 


def units_check(res):	
    """Re-run with every dollar amount in $ thousands and shares in thousands: per-share outputs must not move.""" 
    v = res.inputs 
    k = 1000.0 
    ov = {"in_Price": v["in_Price"], "in_Shares": v["in_Shares"] * k, "in_Cash": v["in_Cash"] * k, "in_Debt": v["in_Debt"] * k,	
          "in_Other": v["in_Other"] * k, "in_Rev0": v["in_Rev0"] * k, "in_Kd": v["in_Kd"], "in_WACC_Direct": v["in_WACC_Direct"]} 
    for name in ("in_EBITM0", "in_Beta", "in_Rf", "in_ERP", "in_TaxRate", "in_TermG", "in_ExitMult", "in_G1", "in_MarginTarget",	
                 "in_MarginYear", "in_DAPct", "in_CapexPct", "in_NWCPct", "in_ShareChg"): 
        ov[name] = v[name]	
    r2 = engine.run(res.company, ov, res.settings)	
    a, b = res.dcf["fv"], (r2.dcf or {}).get("fv")	
    if a is None or b is None: 
        return WARN, "fair value undefined - nothing to compare" 
    ok = abs(a - b) < 1e-9 * max(1, abs(a)) 
    return (PASS if ok else FAIL), f"Fair value in $M: ${a:,.6f}; recomputed in $K (×1,000 money and shares): ${b:,.6f}" 


def summary(checks) -> str: 
    f = sum(c["status"] == FAIL for c in checks) 
    w = sum(c["status"] == WARN for c in checks) 
    return f"FAIL: {f} failing check(s)" if f else (f"WARN: {w} warning(s) to review" if w else "PASS: all checks pass")	
