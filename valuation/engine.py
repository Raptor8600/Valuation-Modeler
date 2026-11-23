"""Valuation engine - the single source of truth for the app.

Implements, line for line, the calculations of the Excel workbooks (Start Here & Guide, Forecast Builder,
DCF Model, Reverse DCF, IRR Analysis). Every function lists the formulas.yaml ids it implements; the registry test
checks that each id points at a real function here and at a real test.

Units: money in $ millions, shares in millions, per-share values in $, rates as decimals (0.025 = 2.5%).
Inputs are passed as {workbook defined name: value}; a missing key means "use the workbook's default formula".
"""	
from __future__ import annotations	

import math 
from dataclasses import dataclass, field 

import numpy as np 

from . import defaults as D 
from .company import CompanyData 
from .provenance import Source, FETCHED, DERIVED, ASSUMPTION, OVERRIDE, MISSING	
__build__ = "bc26cd7bb6615b60" 

YEARS = D.YEARS 


class MissingInputs(Exception): 
    def __init__(self, fields):	
        self.fields = list(fields) 
        super().__init__("missing inputs: " + ", ".join(self.fields))	


def excel_round(x: float, n: int) -> float: 
    """Excel ROUND: half away from zero (Python's round() is half-to-even)."""	
    q = 10 ** n	
    return math.copysign(math.floor(abs(x) * q + 0.5) / q, x)	


def lossf(x, settings): 
    """Taxable amount: max(x,0) under 'No tax benefit on losses', else x.   [dcf.tax]""" 
    if settings["in_LossTax"] == D.LOSS_TAX[0]: 
        return np.maximum(x, 0) if isinstance(x, np.ndarray) else max(x, 0.0) 
    return x 


DEFAULT_SETTINGS = { 
    "in_Basis": "Non-GAAP", "in_TVMethod": D.TV_METHOD[0], "in_WACCMode": D.WACC_MODE[0], 
    "in_NWCMethod": D.NWC_METHOD[0], "in_Timing": D.TIMING[0], "in_CashRetain": D.CASH_RETAIN[0],	
    "in_ExitMetric": D.EXIT_METRIC[0], "in_LossTax": D.LOSS_TAX[0], "fc_Mode": D.FC_MODE[0], "fc_Scenario": "Base", 
    "rd_MarginSrc": D.MARGIN_SRC[0], "irr_Mult": "P/E", "irr_Basis": D.IRR_BASIS[0], "irr_GSrc": D.GROWTH_SRC[0],	
    "irr_Cash": D.CASH_EXIT[0],	
} 
SETTING_OPTIONS = { 
    "in_Basis": D.BASIS, "in_TVMethod": D.TV_METHOD, "in_WACCMode": D.WACC_MODE, "in_NWCMethod": D.NWC_METHOD, 
    "in_Timing": D.TIMING, "in_CashRetain": D.CASH_RETAIN, "in_ExitMetric": D.EXIT_METRIC, "in_LossTax": D.LOSS_TAX,	
    "fc_Mode": D.FC_MODE, "fc_Scenario": D.SCEN, "rd_MarginSrc": D.MARGIN_SRC, "irr_Mult": D.IRR_MULTS,	
    "irr_Basis": D.IRR_BASIS, "irr_GSrc": D.GROWTH_SRC, "irr_Cash": D.CASH_EXIT, 
} 
VECTOR_INPUTS = ("fc_Overrides", "fc_MarginOverrides", "fc_BaseG", "fc_BaseM", "fc_BearG", "fc_BearM", "fc_BullG", "fc_BullM") 


# ===================================================================================================================== 
# 1. INPUT RESOLUTION (defaults + overrides + provenance) 
# =====================================================================================================================	
class Resolver: 
    def __init__(self, overrides): 
        self.ov = {k: v for k, v in (overrides or {}).items() if v is not None} 
        self.val, self.src = {}, {}	

    def take(self, name, default, source: Source): 
        if name in self.ov and name not in VECTOR_INPUTS:	
            self.val[name] = float(self.ov[name]) 
            self.src[name] = Source(OVERRIDE, auto_value=default, note="auto: " + source.tag(), formula=source.formula,	
                                    url=source.url)	
        else:	
            self.val[name] = default 
            self.src[name] = source if default is not None else Source( 
                MISSING, formula=source.formula, url=source.url, field=source.field, provider=source.provider, 
                note=source.note or "required figure not available - type it as an override") 
        return self.val[name] 


def resolve_inputs(c: CompanyData, overrides: dict, s: dict): 
    """Implements: defaults.* and wacc.* registry entries (Start Here & Guide B17:B39, DCF Model CAPM panel).""" 
    r = Resolver(overrides)	
    v = r.take 
    tax = v("in_TaxRate", D.TAX_RATE, Source(ASSUMPTION, rationale="21% US federal statutory rate (add state tax if appropriate)"))	
    if tax is None:	
        tax = D.TAX_RATE 
    der = c.derive(s["in_Basis"], tax) 
    dv = {k: x[0] for k, x in der.items()} 
    price = v("in_Price", c.market.get("price"), c.market_source("price"))	
    shares = v("in_Shares", c.shares_dil, c.shares_source())	
    cash = v("in_Cash", dv["d_Cash"], der["d_Cash"][1]) 
    debt = v("in_Debt", dv["d_Debt"], der["d_Debt"][1]) 
    other = v("in_Other", dv["d_Other"], der["d_Other"][1]) 
    beta = v("in_Beta", c.market.get("beta"), c.market_source("beta")) 
    rev0 = v("in_Rev0", c.flows["revenue"], c.flow_source("revenue")) 
    m0 = v("in_EBITM0", dv["d_EBITMargin"], der["d_EBITMargin"][1])	
    rf = v("in_Rf", c.market.get("rf"), c.market_source("rf")) 
    erp = v("in_ERP", D.ERP, Source(ASSUMPTION, rationale="equity risk premium; published estimates ~4-6% (Damodaran implied ERP)", 
                                     url="https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/implpr.html")) 
    # pre-tax cost of debt default	
    interest = c.flows["interest"] 
    kd_def = None	
    if rf is not None: 
        if interest is not None and debt is not None and debt > 0 and interest / debt > rf:	
            kd_def, kd_f = interest / debt, "reported interest expense ÷ debt (above Rf)"	
        else:	
            kd_def, kd_f = rf + D.KD_SPREAD, "Rf + 1.5% (reported interest ÷ debt not above Rf or unavailable)" 
    else: 
        kd_f = "needs Rf" 
    kd = v("in_Kd", kd_def, Source(DERIVED, formula=kd_f, inputs=["d_interest", "in_Debt", "in_Rf"])) 
    W = compute_wacc(price, shares, debt, rf, beta, erp, kd, tax) 
    wacc_direct_def = None if W["in_WACC_CAPM"] is None else excel_round(W["in_WACC_CAPM"], D.WACC_DIRECT_DECIMALS) 
    wd = v("in_WACC_Direct", wacc_direct_def, Source(DERIVED, formula="ROUND(CAPM WACC, 3)", inputs=["in_WACC_CAPM"])) 
    W["in_WACC"] = wd if s["in_WACCMode"] == D.WACC_MODE[0] else W["in_WACC_CAPM"]	
    tg = v("in_TermG", D.TERM_G, Source(ASSUMPTION, rationale="long-run nominal growth; should not exceed long-run GDP growth (2-3% typical)")) 
    v("in_ExitMult", D.EXIT_MULT, Source(ASSUMPTION, rationale="mature-company exit multiple (applied to the Year-10 metric)"))	
    cons = c.market.get("growth_1y")	
    if cons is not None: 
        v("in_G1", cons, c.market_source("growth_1y")) 
    else: 
        v("in_G1", dv["d_RevGrowth"], Source(DERIVED, formula="TTM revenue growth (no consensus available)", inputs=["d_RevGrowth"]))	
    v("in_MarginTarget", m0, Source(DERIVED, formula="= TTM operating margin (no operating leverage assumed)", inputs=["in_EBITM0"]))	
    v("in_MarginYear", float(D.MARGIN_YEAR), Source(ASSUMPTION, rationale="target margin reached in Year 10")) 
    rev_ttm = c.flows["revenue"]          # workbook divides by the reported d_revenue, not the (overridable) in_Rev0 
    v("in_DAPct", _ratio(dv["d_DA_UFCF"], rev_ttm), Source(DERIVED, formula="D&A used ÷ TTM revenue", inputs=["d_DA_UFCF", "d_revenue"])) 
    v("in_CapexPct", _ratio(dv["d_Capex"], rev_ttm), Source(DERIVED, formula="capex used ÷ TTM revenue", inputs=["d_Capex", "d_revenue"])) 
    if s["in_NWCMethod"] == D.NWC_METHOD[1]: 
        nwc = _ratio(dv["d_NWCResid"], c.flows["revenue"])	
        v("in_NWCPct", nwc, Source(DERIVED, formula="working-capital residual ÷ TTM revenue (flat method)", inputs=["d_NWCResid", "d_revenue"])) 
    else: 
        nwc = _ratio(dv["d_NWCResid"], dv["d_dRev"]) 
        v("in_NWCPct", nwc, Source(DERIVED, formula="working-capital residual ÷ change in revenue (incremental method)",	
                                   inputs=["d_NWCResid", "d_dRev"])) 
    if dv["d_ShareChg"] is not None:	
        v("in_ShareChg", dv["d_ShareChg"], der["d_ShareChg"][1]) 
    else:	
        v("in_ShareChg", 0.0, Source(ASSUMPTION, rationale="no prior-year diluted share count reported: assume no dilution"))	
    v("irr_H", float(D.IRR_H), Source(ASSUMPTION, rationale="5-year holding period"))	
    vals = dict(r.val) 
    vals.update(W) 
    vals["in_NetCash"] = None if None in (cash, debt, other) else cash - debt - other 
    vals["in_NetCashPS"] = _ratio(vals["in_NetCash"], shares) 
    r.src["in_NetCash"] = Source(DERIVED, formula="cash − debt − other claims", inputs=["in_Cash", "in_Debt", "in_Other"]) 
    for k in ("in_Ke", "in_KdAT", "in_We", "in_Wd", "in_WACC_CAPM", "in_WACC"): 
        r.src[k] = Source(DERIVED, formula=WACC_FORMULAS[k]) 
    return vals, r, dv, der	


WACC_FORMULAS = {"in_Ke": "Rf + Beta × ERP", "in_KdAT": "Kd × (1 − tax)", "in_We": "E ÷ (E + D), E = price × shares", 
                 "in_Wd": "1 − We", "in_WACC_CAPM": "We × Ke + Wd × Kd(1 − t)",	
                 "in_WACC": "Standard: direct WACC input; Advanced: CAPM build-up"}	


def _ratio(a, b): 
    if a is None or b is None: 
        return None 
    if b == 0:	
        return 0.0          # workbook IFERROR(...,0): a zero denominator gives 0	
    return a / b 


def compute_wacc(price, shares, debt, rf, beta, erp, kd, tax): 
    """wacc.ke, wacc.kd_after_tax, wacc.we, wacc.wd, wacc.capm""" 
    out = dict.fromkeys(["in_Ke", "in_KdAT", "in_We", "in_Wd", "in_WACC_CAPM"]) 
    if None in (rf, beta, erp): 
        return out	
    ke = rf + beta * erp 
    out["in_Ke"] = ke 
    if kd is None: 
        return out	
    kd_at = kd * (1 - tax) 
    try:	
        we = price * shares / (price * shares + debt) 
    except (TypeError, ZeroDivisionError):	
        we = 1.0	
    out.update(in_KdAT=kd_at, in_We=we, in_Wd=1 - we, in_WACC_CAPM=we * ke + (1 - we) * kd_at)	
    return out 


# ===================================================================================================================== 
# 2. FORECAST BUILDER 
# ===================================================================================================================== 
def _vec(ov, name): 
    x = ov.get(name) 
    return [None] * YEARS if x is None else list(x) + [None] * (YEARS - len(x)) 


def forecast(v, ov, s):	
    """fc.auto_growth, fc.auto_margin, fc.override, fc.scenario, fc.select""" 
    t = np.arange(1, YEARS + 1)	
    g1, tg, m0, mt, my = v["in_G1"], v["in_TermG"], v["in_EBITM0"], v["in_MarginTarget"], v["in_MarginYear"]	
    auto_g = g1 + (tg - g1) * (t - 1) / D.FADE_YEARS 
    phase = np.minimum(t / max(my, 1), 1) 
    auto_m = m0 + (mt - m0) * phase 
    pick = lambda base, over: np.array([o if o is not None else b for b, o in zip(base, over)], dtype=float)	
    man_g, man_m = pick(auto_g, _vec(ov, "fc_Overrides")), pick(auto_m, _vec(ov, "fc_MarginOverrides"))	
    scen = {} 
    for nm, (dg, dm) in D.SCENARIO_DELTA.items(): 
        g = auto_g + dg * (10 - t) / D.FADE_YEARS 
        m = auto_m + dm * phase 
        scen[nm] = (pick(g, _vec(ov, f"fc_{nm}G")), pick(m, _vec(ov, f"fc_{nm}M"))) 
    mode = s["fc_Mode"]	
    if mode == D.FC_MODE[0]: 
        sel_g, sel_m = auto_g, auto_m 
    elif mode == D.FC_MODE[1]: 
        sel_g, sel_m = man_g, man_m	
    else: 
        sel_g, sel_m = scen[s["fc_Scenario"] if s["fc_Scenario"] in scen else "Base"]	
    return {"auto_g": auto_g, "auto_m": auto_m, "manual_g": man_g, "manual_m": man_m, "scenarios": scen, 
            "growth": np.asarray(sel_g, float), "margin": np.asarray(sel_m, float)}	


# =====================================================================================================================	
# 3. DCF	
# ===================================================================================================================== 
def schedule(rev0, growth11, margin11, v, s): 
    """dcf.revenue .. dcf.ufcf for Years 1-11 (Year 11 = terminal). Arrays of length 11.""" 
    rev = rev0 * np.cumprod(1 + growth11) 
    prev = np.concatenate([[rev0], rev[:-1]]) 
    ebit = rev * margin11 
    tax = -lossf(ebit, s) * v["in_TaxRate"] 
    nopat = ebit + tax	
    da = rev * v["in_DAPct"] 
    capex = -rev * v["in_CapexPct"]	
    nwc = v["in_NWCPct"] * rev if s["in_NWCMethod"] == D.NWC_METHOD[1] else v["in_NWCPct"] * (rev - prev)	
    ufcf = nopat + da + capex + nwc 
    return {"rev": rev, "ebit": ebit, "margin": margin11, "growth": growth11, "tax": tax, "nopat": nopat, "da": da, 
            "ebitda": ebit + da, "capex": capex, "nwc": nwc, "ufcf": ufcf} 


def mid(s):	
    return 0.5 if s["in_Timing"] == "Mid-year" else 0.0	


def terminal_value(sch, w, v, s): 
    """dcf.tv_perpetuity / dcf.tv_exit / dcf.tv_period""" 
    perp = s["in_TVMethod"] == D.TV_METHOD[0] 
    if perp: 
        tv = sch["ufcf"][10] / (w - v["in_TermG"]) if w > v["in_TermG"] else None 
        per = 10 - mid(s)	
    else: 
        metric = {"EV/EBITDA": sch["ebitda"][9], "EV/UFCF": sch["ufcf"][9], "EV/Revenue": sch["rev"][9]}[s["in_ExitMetric"]] 
        tv = v["in_ExitMult"] * metric 
        per = 10.0	
    return tv, per 


def dcf(v, fc, s):	
    """dcf.* : schedule, PV, terminal value, EV-to-equity bridge, per-share value, cross-checks.""" 
    w = v["in_WACC"]	
    g11 = np.append(fc["growth"], v["in_TermG"])	
    m11 = np.append(fc["margin"], fc["margin"][-1])	
    sch = schedule(v["in_Rev0"], g11, m11, v, s) 
    per = np.arange(1, 11) - mid(s) 
    pv = sch["ufcf"][:10] / (1 + w) ** per 
    sum_pv = float(pv.sum()) 
    tv, tv_per = terminal_value(sch, w, v, s) 
    out = {"schedule": sch, "per": per, "pv": pv, "cum_pv": np.cumsum(pv), "sum_pv": sum_pv, "tv": tv, "tv_per": tv_per, 
           "npv_check": float(np.sum(sch["ufcf"][:10] / (1 + w) ** np.arange(1, 11)) * (1 + w) ** mid(s))} 
    if tv is None:	
        out.update(pv_tv=None, ev=None, equity=None, fv=None, upside=None, tv_share=None, imp_mult=None, imp_g=None) 
    else:	
        pv_tv = tv / (1 + w) ** tv_per	
        ev = sum_pv + pv_tv 
        eq = ev + v["in_NetCash"] 
        fv = eq / v["in_Shares"] 
        u10, e10 = sch["ufcf"][9], sch["ebitda"][9]	
        out.update(pv_tv=pv_tv, ev=ev, equity=eq, fv=fv, upside=fv / v["in_Price"] - 1, tv_share=pv_tv / ev if ev else None,	
                   imp_mult=tv / e10 if e10 else None, 
                   imp_g=(tv * w - u10) / (tv + u10) if (tv + u10) else None) 
    # base-year (TTM) memo used by the IRR metric paths 
    rev0, m0 = v["in_Rev0"], v["in_EBITM0"] 
    ebit0 = rev0 * m0 
    nopat0 = ebit0 - lossf(ebit0, s) * v["in_TaxRate"]	
    rp = v.get("d_revenue_prior") 
    if s["in_NWCMethod"] == D.NWC_METHOD[1]: 
        nwc0 = v["in_NWCPct"] * rev0 
    else:	
        nwc0 = None if rp is None else v["in_NWCPct"] * (rev0 - rp) 
    out["base"] = {"rev": rev0, "ebit": ebit0, "ebitda": ebit0 + rev0 * v["in_DAPct"], "nopat": nopat0,	
                   "ufcf": None if nwc0 is None else nopat0 + rev0 * (v["in_DAPct"] - v["in_CapexPct"]) + nwc0} 
    out["guard"] = guardrail(fc["growth"][-1], v["in_TermG"], w)	
    return out	


def guardrail(g10, tg, w):	
    if w <= tg: 
        return "FAIL: WACC <= g" 
    if abs(g10 - tg) > D.GUARD_G_GAP: 
        return f"WARN: Year-10 growth {g10:.1%} differs from g {tg:.1%} by >1pp" 
    return "OK: WACC > g and Year-10 growth aligned" 


def dcf_sensitivity(v, d, s): 
    """dcf.sensitivity: 7x7 fair value per share, WACC rows x (terminal g | exit multiple) columns.""" 
    sch, w0 = d["schedule"], v["in_WACC"]	
    perp = s["in_TVMethod"] == D.TV_METHOD[0] 
    cols = [(v["in_TermG"] + o * D.SENS_G_STEP) if perp else (v["in_ExitMult"] + o * D.SENS_MULT_STEP) for o in D.SENS_OFFSETS]	
    rows = [w0 + o * D.SENS_WACC_STEP for o in D.SENS_OFFSETS]	
    rev10, m10 = sch["rev"][9], sch["margin"][9] 
    metric = {"EV/EBITDA": sch["ebitda"][9], "EV/UFCF": sch["ufcf"][9], "EV/Revenue": rev10}[s["in_ExitMetric"]] 
    grid = [] 
    for w in rows:	
        pv = float(np.sum(sch["ufcf"][:10] * (1 + w) ** (-d["per"])))	
        line = [] 
        for p in cols: 
            if perp: 
                rev11 = rev10 * (1 + p) 
                e11 = rev11 * m10 
                nwc11 = v["in_NWCPct"] * rev11 if s["in_NWCMethod"] == D.NWC_METHOD[1] else v["in_NWCPct"] * rev10 * p	
                u11 = e11 - lossf(e11, s) * v["in_TaxRate"] + rev11 * (v["in_DAPct"] - v["in_CapexPct"]) + nwc11 
                tvp = (u11 / (w - p)) / (1 + w) ** (10 - mid(s)) if w > p else None 
            else: 
                tvp = p * metric / (1 + w) ** 10	
            line.append(None if tvp is None else (pv + tvp + v["in_NetCash"]) / v["in_Shares"]) 
        grid.append(line)	
    return {"rows": rows, "cols": cols, "grid": grid, "centre": grid[3][3], "perp": perp} 


def value_over_time(ufcf10, per, tv, tv_per, v, s):	
    """dcf.value_over_time: EV, net cash, equity, shares and price at the end of each year t = 0..10."""	
    w, out = v["in_WACC"], []	
    k = np.arange(1, 11) 
    for t in range(0, 11): 
        if tv is None: 
            out.append(None) 
            continue 
        ev = float(np.sum(np.where(k > t, ufcf10 * (1 + w) ** (-(per - t)), 0.0))) + tv * (1 + w) ** (-(tv_per - t)) 
        nc = v["in_NetCash"] + (float(np.sum(ufcf10[:t])) if s["in_CashRetain"] == D.CASH_RETAIN[0] else 0.0) 
        sh = v["in_Shares"] * (1 + v["in_ShareChg"]) ** t	
        px = (ev + nc) / sh 
        ret = None if t == 0 else ((px / v["in_Price"]) ** (1 / t) - 1 if px > 0 else None)	
        out.append({"t": t, "ev": ev, "net_cash": nc, "equity": ev + nc, "shares": sh, "price": px, "ann_return": ret})	
    return out 


# ===================================================================================================================== 
# 4. REVERSE DCF 
# =====================================================================================================================	
def rdcf_coefficients(v, fc, s):	
    """rdcf.coef_a / rdcf.coef_b: cash-flow coefficients per $1 of revenue (Years 1-11).""" 
    m = np.array(fc["margin"] if s["rd_MarginSrc"] == D.MARGIN_SRC[0] else [v["in_EBITM0"]] * 10, float) 
    m11 = np.append(m, m[-1]) 
    flat = s["in_NWCMethod"] == D.NWC_METHOD[1] 
    a = m11 - lossf(m11, s) * v["in_TaxRate"] + v["in_DAPct"] - v["in_CapexPct"] + (v["in_NWCPct"] if flat else 0.0) 
    b = 0.0 if flat else v["in_NWCPct"]	
    return m11, a, b 


def rdcf_ev(g, v, s, a, b, m11, tv_per): 
    """rdcf.ev_of_g: closed-form model EV for a constant growth g (None when Excel would return an error).""" 
    w, tg = v["in_WACC"], v["in_TermG"]	
    t = np.arange(1, 11) 
    P = t - mid(s)	
    if s["in_TVMethod"] == D.TV_METHOD[0] and w == tg: 
        return None                           # Excel: #DIV/0! -> NA in the scan	
    try:	
        pv = v["in_Rev0"] * float(np.sum((1 + g) ** t * (a[:10] + b * g / (1 + g)) * (1 + w) ** (-P)))	
        if s["in_TVMethod"] == D.TV_METHOD[0]: 
            tv = v["in_Rev0"] * (1 + g) ** 10 * (1 + tg) * (a[10] + b * tg / (1 + tg)) / (w - tg) 
        else: 
            met = {"EV/EBITDA": m11[9] + v["in_DAPct"], "EV/UFCF": a[9] + b * g / (1 + g), "EV/Revenue": 1.0}[s["in_ExitMetric"]] 
            tv = v["in_Rev0"] * (1 + g) ** 10 * v["in_ExitMult"] * met 
        return float(pv + tv * (1 + w) ** (-tv_per)) 
    except ZeroDivisionError: 
        return None	


def _sign(x): 
    return int(x > 0) - int(x < 0)	


def reverse_dcf(v, fc, d, s):	
    """rdcf.target_ev, rdcf.grid, rdcf.bisection, rdcf.status, rdcf.proof, rdcf.gap""" 
    m11, a, b = rdcf_coefficients(v, fc, s) 
    target = v["in_Price"] * v["in_Shares"] - v["in_NetCash"] 
    tv_per = d["tv_per"]	
    f = lambda g: (lambda e: None if e is None else e - target)(rdcf_ev(g, v, s, a, b, m11, tv_per))	
    grid = [round(D.RDCF_GRID_LO + D.RDCF_GRID_STEP * i, 2) for i in range(D.RDCF_GRID_N)] 
    fg = [f(g) for g in grid] 
    flags = [1 if (i < len(grid) - 1 and fg[i] is not None and fg[i + 1] is not None and fg[i] * fg[i + 1] <= 0) else 0 
             for i in range(len(grid))] 
    first = flags.index(1) + 1 if 1 in flags else 0 
    roots = sum(flags)	
    steps, g_star = [], None 
    if first: 
        lo, hi, flo = grid[first - 1], grid[first], fg[first - 1] 
        for i in range(D.RDCF_BISECTIONS):	
            mid_ = (lo + hi) / 2 
            fm = f(mid_)	
            steps.append((lo, hi, flo, mid_, fm)) 
            if i == D.RDCF_BISECTIONS - 1:	
                g_star = mid_	
                break	
            if _sign(fm) == _sign(flo): 
                lo, flo = mid_, fm 
            else: 
                hi = mid_ 
    if not v["in_WACC"] > v["in_TermG"]: 
        status = "FAIL: WACC must exceed terminal growth" 
    elif not first: 
        mx = max([x for x in fg if x is not None], default=-1)	
        status = ("WARN: no solution - even +150%/yr growth does not reach market EV (the margin / cash-conversion inputs " 
                  "cannot justify the price)") if mx < 0 else "WARN: no solution - market EV is below model value even at -50%/yr growth"	
    elif roots > 1:	
        status = f"WARN: {roots} growth rates fit; the lowest is shown" 
    else: 
        status = "OK: unique solution between -50% and +150%" 
    out = {"target": target, "grid": grid, "f": fg, "flags": flags, "first": first, "roots": roots, "steps": steps,	
           "g": g_star, "status": status, "coef_a": a, "coef_b": b, "margins": m11,	
           "solution_text": "No solution in range" if g_star is None else None} 
    fc10 = (d["schedule"]["rev"][9] / v["in_Rev0"]) ** (1 / 10) - 1 
    out["forecast_cagr"] = fc10 
    cons = v.get("d_Cons1y") 
    if g_star is None: 
        out.update(proof=None, ev=None, tieout=None, gap=None, gap_cons=None, residual=None, path=None)	
        return out 
    g11 = np.append(np.full(10, g_star), v["in_TermG"]) 
    sch = schedule(v["in_Rev0"], g11, m11, v, s) 
    pvs = sch["ufcf"][:10] * (1 + v["in_WACC"]) ** (-(np.arange(1, 11) - mid(s)))	
    if s["in_TVMethod"] == D.TV_METHOD[0]: 
        tv = sch["ufcf"][10] / (v["in_WACC"] - v["in_TermG"])	
    else: 
        tv = v["in_ExitMult"] * {"EV/EBITDA": sch["ebit"][9] + sch["da"][9], "EV/UFCF": sch["ufcf"][9],	
                                 "EV/Revenue": sch["rev"][9]}[s["in_ExitMetric"]]	
    pv_tv = tv * (1 + v["in_WACC"]) ** (-tv_per)	
    ev = float(pvs.sum()) + pv_tv 
    out.update(proof={"schedule": sch, "pv": pvs, "sum_pv": float(pvs.sum()), "tv": tv, "pv_tv": pv_tv}, 
               ev=ev, tieout=ev - target, residual=f(g_star), gap=g_star - fc10, 
               gap_cons=None if cons is None else g_star - cons, 
               path=value_over_time(sch["ufcf"][:10], np.arange(1, 11) - mid(s), tv, tv_per, v, s)) 
    return out 


# ===================================================================================================================== 
# 5. IRR	
# ===================================================================================================================== 
def excel_irr(cfs, guess=0.1):	
    """irr.irr: root of Σ cf_t/(1+r)^t = 0 (Excel IRR). Newton from 10% like Excel, bisection fallback."""	
    def npv(r): 
        return sum(c / (1 + r) ** i for i, c in enumerate(cfs)) 

    def dnpv(r): 
        return sum(-i * c / (1 + r) ** (i + 1) for i, c in enumerate(cfs))	
    r = guess	
    for _ in range(100): 
        try: 
            f0, f1 = npv(r), dnpv(r) 
        except (ZeroDivisionError, OverflowError): 
            break 
        if f1 == 0:	
            break 
        r_new = r - f0 / f1 
        if r_new <= -1: 
            r_new = (r - 1) / 2	
        if abs(r_new - r) < 1e-12: 
            return r_new	
        r = r_new 
    lo, hi = -0.9999, 10.0	
    flo, fhi = npv(lo), npv(hi)	
    if flo * fhi > 0:	
        return None 
    for _ in range(200): 
        m = (lo + hi) / 2 
        fm = npv(m) 
        if flo * fm <= 0: 
            hi = m 
        else: 
            lo, flo = m, fm	
    return (lo + hi) / 2 


def _cagr(a, b, n):	
    try:	
        if a == 0 or n == 0: 
            return None 
        x = (b / a) 
        if x < 0:	
            return None	
        return x ** (1 / n) - 1 
    except (TypeError, ZeroDivisionError): 
        return None 


def irr_analysis(v, ov, d, dv, s): 
    """irr.metric_path, irr.entry_multiple, irr.exit_price, irr.cash_flows, irr.irr, irr.sensitivity""" 
    H = int(v["irr_H"])	
    sh, px0, nc, ncps = v["in_Shares"], v["in_Price"], v["in_NetCash"], v["in_NetCashPS"] 
    sch, base = d["schedule"], d["base"] 
    dps = dv.get("d_dps") or 0.0 
    # dividend growth default = forecast revenue CAGR over the holding period	
    dg_def = _cagr(base["rev"], sch["rev"][H - 1], H) 
    dg = ov.get("irr_DG", dg_def if dg_def is not None else 0.0)	
    S = ov.get("irr_S", v["in_ShareChg"]) 

    def line(key, kk):	
        if kk == 0:	
            return base[key]	
        return sch[key][kk - 1] 

    repo = [] 
    for mult in D.IRR_MULTS: 
        kind, key = D.IRR_SPEC[mult] 
        for fwd, basis in enumerate(D.IRR_BASIS): 
            path = [] 
            for t in range(11): 
                kk = t + fwd	
                try: 
                    if key == "eps":	
                        n0, nk = base["nopat"], line("nopat", kk)	
                        scale = nk / n0 if (n0 > 0 and nk > 0) else line("rev", kk) / base["rev"] 
                        val = dv["d_NI_Basis"] * scale 
                    elif key == "gp": 
                        val = dv["d_GP"] * line("rev", kk) / base["rev"]	
                    elif key == "bv":	
                        val = dv["d_Equity"] * line("rev", kk) / base["rev"] 
                    elif key == "dps": 
                        val = dps * (1 + dg) ** kk * sh * (1 + S) ** t 
                    else: 
                        val = line(key, kk) 
                except TypeError:	
                    val = None 
                path.append(None if val is None else float(val)) 
            ps = None if path[0] is None else path[0] / sh 
            if ps is None:	
                em = None 
            elif kind == "P":	
                em = px0 / ps if ps > 0 else None 
            elif kind == "EV":	
                em = (px0 - ncps) / ps if ps > 0 else None	
            else:	
                em = ps / px0 
            gr = _cagr(path[0], path[H], H) if None not in (path[0], path[H]) else None 
            repo.append({"key": f"{mult} - {basis}", "mult": mult, "basis": basis, "kind": kind, "path": path, 
                         "multiple": em, "metric_ps": ps, "growth": gr}) 
    sel = next(r for r in repo if r["key"] == f"{s['irr_Mult']} - {s['irr_Basis']}") 
    kind = sel["kind"] 
    entry = sel["multiple"] 
    exit_ = ov.get("irr_Exit", entry)	
    gman_def = excel_round(sel["growth"], 3) if sel["growth"] is not None else None   # ROUND(path CAGR, 3) 
    gman = ov.get("irr_GMan", gman_def)	
    manual = s["irr_GSrc"] == D.GROWTH_SRC[1]	
    rows = [] 
    cum = 0.0 
    for t in range(11): 
        if t == 0 or not manual:	
            I = sel["path"][t]	
        else: 
            I = None if (sel["path"][0] is None or gman is None) else sel["path"][0] * (1 + gman) ** t 
        E = sh * (1 + S) ** t 
        B = None if I is None else I / E 
        C = 0.0 if t == 0 else dps * (1 + dg) ** t 
        cum += C	
        rows.append({"t": t, "metric_total": I, "shares": E, "metric_ps": B, "dps": C, "cum_div": cum}) 
    for r_ in rows: 
        t = r_["t"] 
        acc = 0.0	
        if s["irr_Cash"] == D.CASH_EXIT[1]: 
            acc = (0.0 if t == 0 else float(np.sum(sch["ufcf"][:max(t, 1)]))) - sum(x["dps"] * x["shares"] for x in rows if x["t"] <= t)	
        r_["nc_ps"] = (nc + acc) / r_["shares"] 
        B = r_["metric_ps"]	
        try:	
            if kind == "Yield":	
                G = B / exit_ if exit_ > 0 else None 
            else: 
                G = exit_ * B + (r_["nc_ps"] if kind == "EV" else 0.0) 
        except TypeError: 
            G = None 
        r_["exit_price"] = G 
    cfs = [] 
    for r_ in rows:	
        t = r_["t"] 
        if t == 0:	
            cf = -px0	
        elif t < H: 
            cf = r_["dps"] 
        elif t == H: 
            cf = None if r_["exit_price"] is None else r_["dps"] + r_["exit_price"]	
        else:	
            cf = 0.0 
        r_["cash_flow"] = cf 
        cfs.append(cf) 
    exit_px = rows[H]["exit_price"] 
    if exit_px is None: 
        irr, irr_note = None, "n/m"	
    elif exit_px <= 0: 
        irr, irr_note = None, "n/m" 
    else: 
        irr = excel_irr(cfs)	
        irr_note = None if irr is not None else "n/a" 
    cumH = rows[H]["cum_div"]	
    out = {"H": H, "repo": repo, "selected": sel, "kind": kind, "entry": entry, "exit": exit_, "rows": rows, 
           "cash_flows": cfs, "exit_price": exit_px, "irr": irr, "irr_note": irr_note, "dg": dg, "share_chg": S,	
           "gman": gman, "entry_ps": rows[0]["metric_ps"], "dps0": dps}	
    out["total_multiple"] = None if exit_px is None else (exit_px + cumH) / px0	
    out["price_cagr"] = _cagr(px0, exit_px, H) if exit_px is not None else None 
    out["simple_return"] = _cagr(px0, exit_px + cumH, H) if exit_px is not None else None 
    out["metric_cagr"] = _cagr(rows[0]["metric_total"], rows[H]["metric_total"], H) if None not in (rows[0]["metric_total"], rows[H]["metric_total"]) else None 
    # sensitivity: entry multiple (rows) x exit multiple (columns) 
    grid = [] 
    BH, FH = rows[H]["metric_ps"], rows[H]["nc_ps"] 
    eps0 = rows[0]["metric_ps"] 
    for mi in D.IRR_SENS_MULTS:	
        line_ = [] 
        for mj in D.IRR_SENS_MULTS:	
            try:	
                A, c = entry * mi, exit_ * mj 
                pe = eps0 / A if kind == "Yield" else A * eps0 + (ncps if kind == "EV" else 0.0) 
                pxx = BH / c if kind == "Yield" else c * BH + (FH if kind == "EV" else 0.0) 
                line_.append(((pxx + cumH) / pe) ** (1 / H) - 1 if (pe > 0 and pxx > 0) else None)	
            except (TypeError, ZeroDivisionError):	
                line_.append(None) 
        grid.append(line_) 
    out["sens"] = {"rows": [None if entry is None else entry * m for m in D.IRR_SENS_MULTS], 
                   "cols": [None if exit_ is None else exit_ * m for m in D.IRR_SENS_MULTS], "grid": grid, 
                   "centre": grid[3][3]} 
    return out	


# ===================================================================================================================== 
# 6. ORCHESTRATION 
# ===================================================================================================================== 
@dataclass	
class Result: 
    company: CompanyData	
    settings: dict 
    inputs: dict	
    sources: dict	
    derived: dict	
    derived_sources: dict 
    missing: list 
    forecast: dict | None = None 
    dcf: dict | None = None 
    sens: dict | None = None 
    vot: list | None = None 
    rdcf: dict | None = None 
    irr: dict | None = None	
    extra: dict = field(default_factory=dict) 


REQUIRED = ["in_Price", "in_Shares", "in_Cash", "in_Debt", "in_Other", "in_Rev0", "in_EBITM0", "in_TaxRate",	
            "in_WACC", "in_TermG", "in_ExitMult", "in_G1", "in_MarginTarget", "in_MarginYear", "in_DAPct",	
            "in_CapexPct", "in_NWCPct", "in_ShareChg"] 


def run(company: CompanyData, overrides: dict | None = None, settings: dict | None = None) -> Result: 
    s = dict(DEFAULT_SETTINGS) 
    s["in_Basis"] = company.basis	
    s.update(settings or {})	
    for k, opts in SETTING_OPTIONS.items(): 
        if s[k] not in opts: 
            raise ValueError(f"{k}: {s[k]!r} is not one of {opts}") 
    ov = dict(overrides or {}) 
    v, r, dv, der = resolve_inputs(company, ov, s) 
    dv = dict(dv)	
    for k in ("revenue", "revenue_prior", "dps"): 
        dv[f"d_{k}"] = company.dps if k == "dps" else company.flows[k] 
    dv["d_Cons1y"] = company.market.get("growth_1y") 
    v["d_revenue_prior"] = company.flows["revenue_prior"]	
    v["d_Cons1y"] = company.market.get("growth_1y") 
    missing = [k for k in REQUIRED if v.get(k) is None]	
    res = Result(company, s, v, r.src, dv, {k: x[1] for k, x in der.items()}, missing) 
    if missing:	
        return res	
    res.forecast = forecast(v, ov, s)	
    res.dcf = dcf(v, res.forecast, s) 
    res.sens = dcf_sensitivity(v, res.dcf, s) 
    res.vot = value_over_time(res.dcf["schedule"]["ufcf"][:10], res.dcf["per"], res.dcf["tv"], res.dcf["tv_per"], v, s) 
    res.rdcf = reverse_dcf(v, res.forecast, res.dcf, s) 
    irr_ov = {k: float(ov[k]) for k in ("irr_Exit", "irr_DG", "irr_GMan", "irr_S") if ov.get(k) is not None} 
    res.irr = irr_analysis(v, irr_ov, res.dcf, dv, s) 
    return res 
