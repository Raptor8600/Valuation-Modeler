"""UI-independent logic behind the Streamlit app (field definitions, unit display, workbook export, audit pack).
Kept out of the Streamlit modules so it can be unit-tested without Streamlit installed."""	
from __future__ import annotations	

import copy 
import json 
import math 

import numpy as np 

from . import engine 
from .company import CompanyData	
from .units import to_millions, from_millions 
__build__ = "e360b8164ba0e953" 

# (name, label, kind, group)   kind: pct | money | px | shares | num | mult | years 
FIELDS = [	
    ("in_Price", "Share price", "px", "Company facts"), 
    ("in_Shares", "Diluted shares (M)", "shares", "Company facts"),	
    ("in_Cash", "Cash & investments counted", "money", "Company facts"), 
    ("in_Debt", "Debt counted", "money", "Company facts"),	
    ("in_Other", "Other claims (NCI, preferred)", "money", "Company facts"),	
    ("in_Rev0", "TTM revenue", "money", "Company facts"),	
    ("in_EBITM0", "TTM operating margin (selected basis)", "pct", "Company facts"), 
    ("in_Beta", "Beta (5Y monthly)", "num", "Company facts"), 
    ("in_WACC_Direct", "Standard WACC (direct)", "pct", "Valuation drivers"), 
    ("in_TermG", "Terminal growth", "pct", "Valuation drivers"), 
    ("in_ExitMult", "Exit multiple", "mult", "Valuation drivers"), 
    ("in_G1", "Year-1 revenue growth", "pct", "Valuation drivers"), 
    ("in_MarginTarget", "Target operating margin", "pct", "Valuation drivers"), 
    ("in_MarginYear", "Year target margin is reached", "years", "Valuation drivers"),	
    ("in_DAPct", "D&A (% of revenue)", "pct", "Valuation drivers"), 
    ("in_CapexPct", "Capex (% of revenue)", "pct", "Valuation drivers"),	
    ("in_NWCPct", "Working-capital cash impact (%)", "pct", "Valuation drivers"),	
    ("in_ShareChg", "Annual change in share count", "pct", "Valuation drivers"), 
    ("in_TaxRate", "Marginal tax rate", "pct", "Discount rate & tax"), 
    ("in_Rf", "Risk-free rate (10Y Treasury)", "pct", "Discount rate & tax"), 
    ("in_ERP", "Equity risk premium", "pct", "Discount rate & tax"),	
    ("in_Kd", "Pre-tax cost of debt", "pct", "Discount rate & tax"),	
] 
FIELD = {f[0]: f for f in FIELDS} 
SCEN_FIELDS = [("th_H", "Price-target horizon (years)", "num"), ("th_WBear", "Bear weight", "pct"), 
               ("th_WBase", "Base weight", "pct"), ("th_WBull", "Bull weight", "pct")] 
IRR_FIELDS = [("irr_H", "Holding period (years)", "years"), ("irr_Exit", "Exit multiple / yield", "num"), 
              ("irr_DG", "Dividend growth", "pct"), ("irr_GMan", "Manual metric growth", "pct"),	
              ("irr_S", "Share-count change (IRR only)", "pct")] 


def to_display(kind: str, x, unit: str): 
    if x is None: 
        return None	
    if kind == "pct": 
        return x * 100.0	
    if kind == "money": 
        return from_millions(x, unit)	
    return x	


def from_display(kind: str, x, unit: str):	
    if x is None or (isinstance(x, float) and math.isnan(x)): 
        return None 
    if kind == "pct": 
        return x / 100.0 
    if kind == "money": 
        return to_millions(x, unit) 
    return float(x) 


def fmt(kind: str, x, unit: str = "$M") -> str:	
    if x is None: 
        return "—"	
    if kind == "pct":	
        return f"{x:.2%}" 
    if kind == "money": 
        return f"{unit[0]}{from_millions(x, unit):,.1f}{unit[1:]}" 
    if kind == "px":	
        return f"${x:,.2f}"	
    if kind == "mult": 
        return f"{x:.1f}x" 
    if kind == "years": 
        return f"{x:.0f}" 
    return f"{x:,.3f}" 


def apply_switches(company: CompanyData, switches: dict) -> CompanyData:	
    """Data & Sources Y/N switches (non-GAAP adjustments, capitalized software, balance-sheet lines).""" 
    c = copy.deepcopy(company) 
    for k in ("adj_sbc", "adj_amort", "adj_other_on", "capex_include_sw"): 
        if k in switches:	
            setattr(c, k, bool(switches[k])) 
    if switches.get("adj_other") is not None:	
        c.adj_other = float(switches["adj_other"]) 
    if switches.get("ni_override") is not None:	
        c.ni_override = float(switches["ni_override"])	
    for item in c.instants:	
        key = f"inc::{item['label']}" 
        if key in switches: 
            item["include"] = bool(switches[key]) 
    return c 


SWITCH_TO_WORKBOOK = {"adj_sbc": "ds_adj_sbc", "adj_amort": "ds_adj_amort", "adj_other": "ds_adj_other", 
                      "adj_other_on": "ds_adj_other_on", "capex_include_sw": "ds_capex_sw", "ni_override": "ds_ni_override"} 


def workbook_overrides(settings: dict, overrides: dict, switches: dict) -> dict: 
    """Everything the analyst changed in the app, keyed by the workbook cell it belongs in."""	
    out = {} 
    for k, v in settings.items():	
        if k == "in_Basis":	
            continue                      # the workbook is generated on the chosen basis 
        out[k] = v 
    for k, v in overrides.items(): 
        if v is None:	
            continue	
        if isinstance(v, (list, tuple)): 
            if any(x is not None for x in v): 
                out[k] = list(v) 
        else: 
            out[k] = int(v) if k in ("irr_H", "in_MarginYear") else float(v) 
    for k, v in switches.items():	
        if k.startswith("inc::"): 
            out["ds_inc::" + k[5:]] = bool(v) 
        elif k in SWITCH_TO_WORKBOOK and v is not None: 
            out[SWITCH_TO_WORKBOOK[k]] = v	
    return out 


def _clean(x):	
    if isinstance(x, (np.floating,)): 
        return float(x)	
    if isinstance(x, np.ndarray):	
        return [_clean(i) for i in x.tolist()]	
    if isinstance(x, dict): 
        return {k: _clean(v) for k, v in x.items()} 
    if isinstance(x, (list, tuple)): 
        return [_clean(i) for i in x] 
    return x 


def audit_pack(res) -> str: 
    """JSON with every input (value + source tag), every switch and every headline output.""" 
    pack = {	
        "company": {"ticker": res.company.ticker, "name": res.company.name, "period_end": res.company.period_end, 
                    "fetched_at": res.company.fetched_at, "synthetic": res.company.synthetic,	
                    "snapshot": res.company.snapshot_meta},	
        "settings": res.settings, 
        "inputs": {k: {"value": _clean(res.inputs.get(k)), "source": res.sources[k].to_dict()} for k in res.sources}, 
        "derived": {k: {"value": _clean(v), "source": res.derived_sources[k].to_dict()} for k, v in res.derived.items() 
                    if k in res.derived_sources},	
        "missing": res.missing,	
    } 
    if res.dcf: 
        pack["results"] = {"fair_value": res.dcf["fv"], "enterprise_value": res.dcf["ev"], "terminal_value": res.dcf["tv"], 
                           "wacc": res.inputs["in_WACC"], "implied_growth": res.rdcf["g"], "rdcf_status": res.rdcf["status"], 
                           "irr": res.irr["irr"], "irr_multiple": res.settings["irr_Mult"]} 
    return json.dumps(_clean(pack), indent=1, default=str)	


def run(company, overrides, settings, switches): 
    return engine.run(apply_switches(company, switches), overrides, settings) 
