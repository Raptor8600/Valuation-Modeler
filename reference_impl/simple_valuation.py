"""Deliberately simple REFERENCE implementation - the independent check on valuation/engine.py.

Rules this file follows on purpose:
  * no imports from the `valuation` package and no numpy - plain Python floats and for-loops;
  * every year is built one at a time, the way you would on paper;
  * the reverse DCF rebuilds the full 10-year schedule for every trial growth rate (the engine uses a closed form);
  * IRR is found by plain bisection (the engine uses Newton's method first).
tests/test_reference_agreement.py checks both implementations agree on many random inputs.

Input: `raw` is a plain dict of reported figures ($M, shares in M); see tests/conftest.py::raw_dict.
"""	
__build__ = "09c0fa6236a4fcb5"	

TV_PERP, TV_EXIT = "Perpetuity (Gordon Growth)", "Exit Multiple" 
NWC_INCR, NWC_FLAT = "Incremental Mode (% of ΔRev)", "Flat Intensity (% of Revenue)" 


def xround(x, n): 
    """Round half away from zero, like Excel.""" 
    scaled = abs(x) * (10 ** n) + 0.5 
    whole = int(scaled)	
    r = whole / (10 ** n) 
    return r if x >= 0 else -r 


def nz(x): 
    return 0.0 if x is None else x	


def resolve(raw, ov, st): 
    """Defaults exactly as the workbook's yellow cells define them."""	
    def pick(name, default): 
        return ov[name] if ov.get(name) is not None else default	

    ng = st["in_Basis"] == "Non-GAAP"	
    tax = pick("in_TaxRate", 0.21)	
    adj = 0.0 
    if ng: 
        if raw["adj_sbc"]: 
            adj += nz(raw["sbc"]) 
        if raw["adj_amort"]: 
            adj += nz(raw["amort"]) 
        if raw["adj_other_on"]: 
            adj += raw["adj_other"]	
    x = {} 
    x["tax"] = tax	
    x["price"] = pick("in_Price", raw["price"])	
    x["shares"] = pick("in_Shares", raw["shares_dil"]) 
    x["cash"] = pick("in_Cash", raw["cash_counted"]) 
    x["debt"] = pick("in_Debt", raw["debt_counted"]) 
    x["other"] = pick("in_Other", raw["other_counted"])	
    x["net_cash"] = x["cash"] - x["debt"] - x["other"]	
    x["beta"] = pick("in_Beta", raw["beta"]) 
    x["rev0"] = pick("in_Rev0", raw["revenue"]) 
    x["m0"] = pick("in_EBITM0", (raw["ebit"] + adj) / raw["revenue"]) 
    x["rf"] = pick("in_Rf", raw["rf"]) 
    x["erp"] = pick("in_ERP", 0.055) 
    interest, debt = raw["interest"], x["debt"]	
    if interest is not None and debt > 0 and interest / debt > x["rf"]: 
        kd = interest / debt 
    else: 
        kd = x["rf"] + 0.015	
    x["kd"] = pick("in_Kd", kd) 
    x["ke"] = x["rf"] + x["beta"] * x["erp"]	
    equity_mv = x["price"] * x["shares"] 
    x["we"] = equity_mv / (equity_mv + x["debt"])	
    x["wd"] = 1 - x["we"]	
    x["wacc_capm"] = x["we"] * x["ke"] + x["wd"] * x["kd"] * (1 - tax)	
    x["wacc_direct"] = pick("in_WACC_Direct", xround(x["wacc_capm"], 3)) 
    x["wacc"] = x["wacc_direct"] if st["in_WACCMode"] == "Standard (Direct Input)" else x["wacc_capm"] 
    x["tg"] = pick("in_TermG", 0.025) 
    x["mult"] = pick("in_ExitMult", 15.0) 
    if raw["cons_1y"] is not None: 
        g1 = raw["cons_1y"] 
    else: 
        g1 = raw["revenue"] / raw["revenue_prior"] - 1	
    x["g1"] = pick("in_G1", g1) 
    x["mt"] = pick("in_MarginTarget", x["m0"])	
    x["my"] = pick("in_MarginYear", 10.0)	
    da_used = raw["da"] - (nz(raw["amort"]) if (ng and raw["adj_amort"]) else 0.0) 
    capex_used = raw["capex_ppe"] + (nz(raw["capex_sw"]) if raw["capex_include_sw"] else 0.0) 
    resid = raw["ocf"] - raw["net_income"] - raw["da"] - nz(raw["sbc"]) 
    x["da_pct"] = pick("in_DAPct", da_used / raw["revenue"])	
    x["capex_pct"] = pick("in_CapexPct", capex_used / raw["revenue"])	
    if st["in_NWCMethod"] == NWC_FLAT: 
        nwc = resid / raw["revenue"] 
    else: 
        drev = raw["revenue"] - raw["revenue_prior"] 
        nwc = resid / drev if drev != 0 else 0.0 
    x["nwc_pct"] = pick("in_NWCPct", nwc)	
    if raw["shares_dil_prior"]: 
        sc = raw["shares_dil"] / raw["shares_dil_prior"] - 1 
    else: 
        sc = 0.0	
    x["share_chg"] = pick("in_ShareChg", sc) 
    if ng and raw["ni_override"] is not None:	
        x["ni_basis"] = raw["ni_override"] 
    else:	
        x["ni_basis"] = raw["net_income"] + adj * (1 - tax)	
    x["gp"] = raw["gross_profit"] if raw["gross_profit"] is not None else raw["revenue"] - raw["cost_of_revenue"]	
    x["equity_book"] = raw["equity_book"] 
    x["dps"] = nz(raw["dps"]) 
    x["rev_prior"] = raw["revenue_prior"] 
    x["H"] = int(pick("irr_H", 5)) 
    return x 


def growth_and_margin(x, ov, st): 
    gs, ms = [], [] 
    for t in range(1, 11):	
        g_auto = x["g1"] + (x["tg"] - x["g1"]) * (t - 1) / 9 
        share = t / max(x["my"], 1)	
        if share > 1:	
            share = 1 
        m_auto = x["m0"] + (x["mt"] - x["m0"]) * share 
        mode = st["fc_Mode"] 
        if mode == "Automatic Fade":	
            g, m = g_auto, m_auto	
        elif mode == "Manual Override": 
            go = (ov.get("fc_Overrides") or [None] * 10)[t - 1] 
            mo = (ov.get("fc_MarginOverrides") or [None] * 10)[t - 1] 
            g = g_auto if go is None else go 
            m = m_auto if mo is None else mo 
        else:	
            sc = st["fc_Scenario"] 
            dg = {"Bear": -0.05, "Base": 0.0, "Bull": 0.05}[sc] 
            dm = {"Bear": -0.03, "Base": 0.0, "Bull": 0.03}[sc] 
            g = g_auto + dg * (10 - t) / 9	
            m = m_auto + dm * share 
            go = (ov.get(f"fc_{sc}G") or [None] * 10)[t - 1]	
            mo = (ov.get(f"fc_{sc}M") or [None] * 10)[t - 1] 
            g = g if go is None else go	
            m = m if mo is None else mo	
        gs.append(g)	
        ms.append(m) 
    return gs, ms 


def one_year(rev, prev_rev, margin, x, st): 
    ebit = rev * margin 
    taxable = ebit if st["in_LossTax"] == "Tax credit on losses" else max(ebit, 0.0) 
    nopat = ebit - taxable * x["tax"] 
    da = rev * x["da_pct"] 
    capex = rev * x["capex_pct"]	
    if st["in_NWCMethod"] == NWC_FLAT: 
        nwc = x["nwc_pct"] * rev	
    else:	
        nwc = x["nwc_pct"] * (rev - prev_rev) 
    ufcf = nopat + da - capex + nwc 
    return {"rev": rev, "ebit": ebit, "nopat": nopat, "da": da, "ebitda": ebit + da, "ufcf": ufcf} 


def build_years(x, growths, margins, st):	
    years = []	
    rev = x["rev0"] 
    for t in range(10): 
        prev = rev 
        rev = rev * (1 + growths[t]) 
        years.append(one_year(rev, prev, margins[t], x, st)) 
    prev = rev	
    rev11 = rev * (1 + x["tg"]) 
    years.append(one_year(rev11, prev, margins[9], x, st)) 
    return years 


def enterprise_value(x, years, st):	
    half = 0.5 if st["in_Timing"] == "Mid-year" else 0.0 
    w = x["wacc"]	
    pv_sum = 0.0 
    for t in range(1, 11):	
        pv_sum += years[t - 1]["ufcf"] / (1 + w) ** (t - half)	
    if st["in_TVMethod"] == TV_PERP:	
        if w <= x["tg"]: 
            return pv_sum, None, None, None 
        tv = years[10]["ufcf"] / (w - x["tg"]) 
        n = 10 - half 
    else: 
        metric = {"EV/EBITDA": "ebitda", "EV/UFCF": "ufcf", "EV/Revenue": "rev"}[st["in_ExitMetric"]] 
        tv = x["mult"] * years[9][metric] 
        n = 10	
    pv_tv = tv / (1 + w) ** n 
    return pv_sum, tv, n, pv_sum + pv_tv	


def dcf(raw, ov, st):	
    x = resolve(raw, ov, st) 
    gs, ms = growth_and_margin(x, ov, st) 
    years = build_years(x, gs, ms, st) 
    pv_sum, tv, n, ev = enterprise_value(x, years, st)	
    out = {"x": x, "growths": gs, "margins": ms, "years": years, "sum_pv": pv_sum, "tv": tv, "ev": ev}	
    out["fv"] = None if ev is None else (ev + x["net_cash"]) / x["shares"] 
    # sensitivity by re-running the model with a changed WACC and terminal parameter 
    grid = [] 
    for i in range(-3, 4): 
        row = [] 
        for j in range(-3, 4):	
            x2 = dict(x) 
            x2["wacc"] = x["wacc"] + i * 0.005 
            if st["in_TVMethod"] == TV_PERP: 
                x2["tg"] = x["tg"] + j * 0.005	
            else: 
                x2["mult"] = x["mult"] + j * 2.5	
            # Years 1-10 keep the base forecast; only the terminal year responds to the new terminal growth 
            y2 = years[:10] + [one_year(years[9]["rev"] * (1 + x2["tg"]), years[9]["rev"], ms[9], x2, st)]	
            _, _, _, ev2 = enterprise_value(x2, y2, st)	
            row.append(None if ev2 is None else (ev2 + x["net_cash"]) / x["shares"])	
        grid.append(row) 
    out["sens"] = grid 
    return out 


def reverse_dcf(raw, ov, st): 
    base = dcf(raw, ov, st) 
    x, ms_fc = base["x"], base["margins"] 
    margins = ms_fc if st["rd_MarginSrc"] == "Forecast margin path" else [x["m0"]] * 10 
    target = x["price"] * x["shares"] - x["net_cash"]	

    def gap(g): 
        years = build_years(x, [g] * 10, margins, st)	
        _, _, _, ev = enterprise_value(x, years, st)	
        return None if ev is None else ev - target 

    lo = None 
    prev_g, prev_f = None, None 
    for i in range(201):	
        g = round(-0.5 + 0.01 * i, 2)	
        fg = gap(g) 
        if prev_f is not None and fg is not None and prev_f * fg <= 0: 
            lo = (prev_g, g, prev_f) 
            break 
        prev_g, prev_f = g, fg 
    if lo is None:	
        return None 
    a, b, fa = lo 
    for _ in range(200): 
        m = (a + b) / 2	
        fm = gap(m) 
        if (fm > 0) == (fa > 0) and fm != 0:	
            a, fa = m, fm 
        else:	
            b = m	
        if b - a < 1e-15:	
            break 
    return (a + b) / 2 


def irr_bisect(cfs): 
    def npv(r): 
        total = 0.0 
        for t, c in enumerate(cfs): 
            total += c / (1 + r) ** t 
        return total	
    lo, hi = -0.99, 10.0 
    if npv(lo) * npv(hi) > 0:	
        return None	
    for _ in range(300): 
        m = (lo + hi) / 2 
        if npv(lo) * npv(m) <= 0: 
            hi = m	
        else:	
            lo = m 
    return (lo + hi) / 2 


def irr(raw, ov, st): 
    """IRR for P/E, EV/EBITDA, EV/Revenue, P/S, EV/FCF, P/FCF (trailing or forward), no manual growth.""" 
    base = dcf(raw, ov, st) 
    x, years = base["x"], base["years"]	
    H = x["H"] 
    fwd = 1 if st["irr_Basis"] == "Forward (NTM / FY+1)" else 0 
    rev0 = x["rev0"] 
    ebit0 = rev0 * x["m0"]	
    taxable0 = ebit0 if st["in_LossTax"] == "Tax credit on losses" else max(ebit0, 0.0) 
    nopat0 = ebit0 - taxable0 * x["tax"]	
    if st["in_NWCMethod"] == NWC_FLAT: 
        nwc0 = x["nwc_pct"] * rev0	
    else:	
        nwc0 = x["nwc_pct"] * (rev0 - x["rev_prior"])	
    base0 = {"rev": rev0, "ebit": ebit0, "ebitda": ebit0 + rev0 * x["da_pct"], "nopat": nopat0, 
             "ufcf": nopat0 + rev0 * (x["da_pct"] - x["capex_pct"]) + nwc0} 
    mult = st["irr_Mult"] 
    kind = {"P/E": "P", "P/S": "P", "P/FCF": "P", "EV/EBITDA": "EV", "EV/Revenue": "EV", "EV/FCF": "EV"}[mult] 
    key = {"P/E": "eps", "P/S": "rev", "P/FCF": "ufcf", "EV/EBITDA": "ebitda", "EV/Revenue": "rev", "EV/FCF": "ufcf"}[mult] 

    def metric(k): 
        def line(name): 
            return base0[name] if k == 0 else years[k - 1][name]	
        if key == "eps": 
            if nopat0 > 0 and line("nopat") > 0:	
                return x["ni_basis"] * line("nopat") / nopat0	
            return x["ni_basis"] * line("rev") / rev0 
        return line(key) 

    s = ov.get("irr_S", x["share_chg"]) 
    shares0 = x["shares"]	
    m0_ps = metric(fwd) / shares0	
    ncps0 = x["net_cash"] / shares0 
    if m0_ps <= 0: 
        return None 
    entry = x["price"] / m0_ps if kind == "P" else (x["price"] - ncps0) / m0_ps 
    exit_mult = ov.get("irr_Exit", entry) 
    # dividend growth default = revenue CAGR over the holding period	
    dg = ov.get("irr_DG", (years[H - 1]["rev"] / rev0) ** (1 / H) - 1) 
    flows = [-x["price"]] 
    for t in range(1, H + 1): 
        dps = x["dps"] * (1 + dg) ** t	
        if t < H: 
            flows.append(dps)	
        else: 
            sh = shares0 * (1 + s) ** H	
            mps = metric(H + fwd) / sh	
            nc_ps = x["net_cash"] / sh	
            px = exit_mult * mps + (nc_ps if kind == "EV" else 0.0) 
            flows.append(dps + px) 
    if flows[-1] <= 0: 
        return None 
    return {"irr": irr_bisect(flows), "exit_price": flows[-1] - x["dps"] * (1 + dg) ** H, "entry": entry} 
