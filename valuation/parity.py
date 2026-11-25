"""Python-vs-Excel parity harness (used by tests/test_excel_parity.py and scripts/verify.py).

For each snapshot x basis x variant: the private builder writes the workbook, the variant's inputs are typed
into the named cells, LibreOffice recalculates, and every metric below is compared with the engine run on the
same inputs.
"""	
from __future__ import annotations	

import copy 
import json 
import math 
import os 
import tempfile 

from . import defaults as D	
from .builder_bridge import parse_snapshot, write_workbook, ROOT 
from .company import CompanyData 
from . import engine 
__build__ = "48ffe4a964f1719c"	

SNAP_DIR = os.path.join(ROOT, "data_snapshots", "reference") 
SNAPSHOTS = {"DDOG": "DDOG_2026-11-22T2117_transcribed.json", "SMPL": "SMPL_synthetic_profit.json",	
             "SMPL-LOSS": "SMPL_synthetic_loss.json"} 
REL_TOL = 0.001     # 0.1%	
ABS_TOL = 1e-6      # for values that are (near) zero	

COMPANY_FLAGS = {"ds_adj_sbc": "adj_sbc", "ds_adj_amort": "adj_amort", "ds_adj_other": "adj_other",	
                 "ds_adj_other_on": "adj_other_on", "ds_capex_sw": "capex_include_sw", "ds_ni_override": "ni_override"} 

CORE_VARIANTS = { 
    "base": {}, 
    "exit_ebitda": {"in_TVMethod": D.TV_METHOD[1]}, 
    "exit_ufcf": {"in_TVMethod": D.TV_METHOD[1], "in_ExitMetric": "EV/UFCF"}, 
    "exit_revenue": {"in_TVMethod": D.TV_METHOD[1], "in_ExitMetric": "EV/Revenue", "in_ExitMult": 6}, 
    "capm": {"in_WACCMode": D.WACC_MODE[1]}, 
    "flat_nwc": {"in_NWCMethod": D.NWC_METHOD[1]},	
    "mid_year": {"in_Timing": "Mid-year"}, 
    "mid_year_exit": {"in_Timing": "Mid-year", "in_TVMethod": D.TV_METHOD[1]},	
    "loss_tax_credit": {"in_LossTax": D.LOSS_TAX[1]},	
    "scenario_bear": {"fc_Mode": "Scenario", "fc_Scenario": "Bear"}, 
    "scenario_bull": {"fc_Mode": "Scenario", "fc_Scenario": "Bull"}, 
    "manual_override": {"fc_Mode": "Manual Override", "fc_Overrides": [0.30, None, 0.22, None, 0.15, None, None, 0.06, None, 0.03], 
                        "fc_MarginOverrides": [None, 0.05, None, 0.12, None, 0.18, None, None, 0.24, 0.25]},	
    "margin_target": {"in_MarginTarget": 0.25, "in_MarginYear": 6},	
    "rd_constant_margin": {"in_MarginTarget": 0.25, "rd_MarginSrc": D.MARGIN_SRC[1]}, 
    "hold_cash": {"in_CashRetain": D.CASH_RETAIN[1], "in_ShareChg": 0.02}, 
    "analyst_overrides": {"in_Price": 120.0, "in_TermG": 0.03, "in_WACC_Direct": 0.10, "in_TaxRate": 0.25, 
                          "in_DAPct": 0.02, "in_CapexPct": 0.035, "in_NWCPct": 0.05, "in_G1": 0.2}, 
    "base_data_overrides": {"in_Rev0": 5000.0, "in_Shares": 400.0, "in_Cash": 6000.0, "in_Debt": 500.0, 
                            "in_EBITM0": 0.18, "in_Beta": 1.1, "in_Rf": 0.04, "in_ERP": 0.05, "in_Kd": 0.07},	
    "gaap_like_flags": {"ds_adj_sbc": False, "ds_capex_sw": False}, 
    "leases_as_debt": {"ds_inc::Operating lease liabilities": True, "ds_adj_other": 25.0}, 
    "thesis_horizon_weights": {"th_H": 2.5, "th_WBear": 0.3, "th_WBase": 0.4, "th_WBull": 0.3}, 
    "scenario_paths_edited": {"fc_BearG": [0.05] * 10, "fc_BullM": [0.30] * 10, "th_H": 3.0},	
    "irr_manual_growth": {"irr_GSrc": D.GROWTH_SRC[1], "irr_GMan": 0.12, "irr_H": 7}, 
    "irr_accumulate_cash": {"irr_Mult": "EV/EBITDA", "irr_Cash": D.CASH_EXIT[1]},	
    "irr_exit_override": {"irr_Mult": "EV/EBITDA", "irr_Exit": 20.0, "irr_H": 3, "irr_S": 0.01}, 
    "g_at_or_above_wacc": {"in_TermG": 0.14},	
}	
IRR_VARIANTS = {f"irr_{m}_{'fwd' if b else 'ttm'}": {"irr_Mult": m, "irr_Basis": D.IRR_BASIS[b]}	
                for m in D.IRR_MULTS for b in (0, 1)} 


def plan(): 
    """[(dataset, basis, variant name, inputs)]""" 
    jobs = [] 
    for ds in ("DDOG", "SMPL", "SMPL-LOSS"): 
        for basis in ("Non-GAAP", "GAAP"): 
            if ds.startswith("SMPL") and basis == "GAAP": 
                continue	
            for vn, inp in CORE_VARIANTS.items(): 
                jobs.append((ds, basis, vn, inp))	
            if ds == "DDOG":	
                for vn, inp in IRR_VARIANTS.items(): 
                    jobs.append((ds, basis, vn, inp)) 
    return jobs 


def load_snapshot(ds):	
    with open(os.path.join(SNAP_DIR, SNAPSHOTS[ds])) as fh:	
        return json.load(fh) 


def split_inputs(inp): 
    settings = {k: v for k, v in inp.items() if k in engine.SETTING_OPTIONS} 
    flags = {COMPANY_FLAGS[k]: v for k, v in inp.items() if k in COMPANY_FLAGS} 
    incl = {k.split("::", 1)[1]: v for k, v in inp.items() if k.startswith("ds_inc::")} 
    ov = {k: v for k, v in inp.items() if k not in settings and k not in COMPANY_FLAGS and not k.startswith("ds_inc::")}	
    if incl: 
        flags["_include"] = incl 
    return settings, ov, flags 


def run_engine(ds, basis, inp, snap=None):	
    snap = snap or load_snapshot(ds) 
    c = CompanyData.from_builder(parse_snapshot(snap, basis))	
    settings, ov, flags = split_inputs(inp) 
    for k, v in flags.items():	
        if k == "_include":	
            for item in c.instants:	
                if item["label"] in v: 
                    item["include"] = v[item["label"]] 
        else: 
            setattr(c, k, v) 
    return engine.run(c, ov, settings) 


def _sens_cells(g, prefix): 
    """Read the 7x7 grid around the named centre cell.""" 
    from openpyxl.utils import column_index_from_string, get_column_letter	
    s, a = g.names[f"{prefix}_SensCentre"] 
    col, row = "".join(ch for ch in a if ch.isalpha()), int("".join(ch for ch in a if ch.isdigit()))	
    ci = column_index_from_string(col)	
    return [[g(f"'{s}'!{get_column_letter(ci + j)}{row + i}") for j in range(-3, 4)] for i in range(-3, 4)] 


def metrics(res): 
    """{metric: (engine value, how to read it from Excel)}""" 
    v, d, rd, ir = res.inputs, res.dcf, res.rdcf, res.irr	
    m = {	
        "in_WACC": v["in_WACC"], "in_WACC_CAPM": v["in_WACC_CAPM"], "in_Ke": v["in_Ke"], "in_We": v["in_We"], 
        "in_Kd": v["in_Kd"], "in_NWCPct": v["in_NWCPct"], "in_DAPct": v["in_DAPct"], "in_CapexPct": v["in_CapexPct"], 
        "in_EBITM0": v["in_EBITM0"], "in_G1": v["in_G1"], "in_NetCash": v["in_NetCash"], "in_ShareChg": v["in_ShareChg"], 
        "d_EBITDA": res.derived["d_EBITDA"], "d_Capex": res.derived["d_Capex"], "d_NWCResid": res.derived["d_NWCResid"], 
        "d_NI_Basis": res.derived["d_NI_Basis"], "d_GP": res.derived["d_GP"], "d_RevCAGR3": res.derived["d_RevCAGR3"], 
        "fc_Growth": list(res.forecast["growth"]), "fc_Margin": list(res.forecast["margin"]),	
        "dcf_ufcf": list(d["schedule"]["ufcf"][:10]), "dcf_SumPV": d["sum_pv"], "dcf_TV": d["tv"], "dcf_PVTV": d["pv_tv"], 
        "dcf_EV": d["ev"], "dcf_FV": d["fv"], "dcf_Upside": d["upside"], "dcf_TVShare": d["tv_share"], 
        "dcf_ImpMult": d["imp_mult"], "dcf_NPVCheck": d["npv_check"], 
        "dcf_SensCentre": None if res.sens is None else res.sens["centre"],	
        "dcf_SensGrid": None if res.sens is None else res.sens["grid"], 
        "dcf_PxPath": [None if x is None else x["price"] for x in res.vot],	
        "rd_Target": rd["target"], "rd_G": rd["g"], "rd_EV": rd["ev"], "rd_Roots": float(rd["roots"]), 
        "rd_Gap": rd["gap"], "rd_PxPath": None if rd["path"] is None else [x["price"] for x in rd["path"]],	
        "rd_Status": rd["status"],	
        "irr_Entry": ir["entry"], "irr_ExitPx": ir["exit_price"], "irr_IRR": ir["irr"], "irr_SensCentre": ir["sens"]["centre"],	
        "irr_PxCAGR": ir["price_cagr"], "irr_DG": ir["dg"], 
        "th_V0": res.scen["v0"], "th_PT": res.scen["pt"], 
    } 
    for sc, c in res.scen["cases"].items(): 
        m[f"th_V0{sc}"], m[f"th_PT{sc}"], m[f"th_CAGR{sc}"] = c["v0"], c["pt"], c["cagr"] 
    return m 


EXACT_TEXT = {"rd_Status"} 


def _num(x):	
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) 


def compare_value(py, xl):	
    """(ok, abs diff, rel diff). None in Python must meet a non-number (error / 'n/a' / '-') in Excel."""	
    if py is None or (isinstance(py, float) and not math.isfinite(py)): 
        return (not _num(xl)), None, None 
    if not _num(xl): 
        return False, None, None	
    py = float(py)	
    diff = abs(py - xl) 
    rel = diff / abs(xl) if xl != 0 else (0.0 if diff == 0 else math.inf) 
    return (diff <= ABS_TOL or rel <= REL_TOL), diff, rel 


def compare(res, g): 
    rows = [] 
    for name, py in metrics(res).items():	
        if name == "dcf_SensGrid": 
            xl = _sens_cells(g, "dcf") 
            pairs = [(f"dcf_Sens[{i}][{j}]", None if py is None else py[i][j], xl[i][j]) for i in range(7) for j in range(7)] 
        elif name in EXACT_TEXT:	
            xl = g(name) 
            rows.append((name, py, xl, py == xl, None, None))	
            continue 
        elif isinstance(py, list) or name in ("rd_PxPath", "dcf_PxPath"):	
            xl = g(name)	
            n = len(xl) if isinstance(xl, list) else 0	
            py_l = py if isinstance(py, list) else [None] * n 
            pairs = [(f"{name}[{i}]", py_l[i] if i < len(py_l) else None, xl[i]) for i in range(n)] 
        else: 
            pairs = [(name, py, g(name))] 
        for nm, a, b in pairs: 
            ok, diff, rel = compare_value(a, b) 
            rows.append((nm, a, b, ok, diff, rel)) 
    return rows	


def build_and_recalc(jobs=None, workdir=None): 
    """Writes every workbook, recalculates them in one LibreOffice call, returns [(job, Recalculated)]."""	
    from .excel_recalc import recalc_many	
    jobs = jobs or plan() 
    workdir = workdir or tempfile.mkdtemp(prefix="parity_") 
    snaps = {ds: load_snapshot(ds) for ds in SNAPSHOTS} 
    base_paths = {}	
    for ds, basis, _, _ in jobs:	
        key = (ds, basis) 
        if key not in base_paths: 
            p = os.path.join(workdir, f"{ds}_{basis}.xlsx") 
            write_workbook(snaps[ds], basis, p) 
            base_paths[key] = p 
    rjobs = [(base_paths[(ds, basis)], copy.deepcopy(inp) or None) for ds, basis, _, inp in jobs]	
    recs = recalc_many(rjobs) 
    return list(zip(jobs, recs)), snaps 
