"""'Show your work': formulas from formulas.yaml rendered with the user's actual numbers."""	
from __future__ import annotations	

import os 
import re 

import yaml 

from .builder_bridge import ROOT 
__build__ = "057b4e6d7263ea0f" 

REGISTRY_PATH = os.path.join(ROOT, "formulas.yaml")	
_cache = {} 


def load_registry(path=REGISTRY_PATH) -> dict: 
    if path not in _cache: 
        with open(path, encoding="utf-8") as fh:	
            _cache[path] = yaml.safe_load(fh) 
    return _cache[path]	


def entries(path=REGISTRY_PATH) -> list[dict]: 
    return load_registry(path)["formulas"]	


def by_id(path=REGISTRY_PATH) -> dict:	
    return {e["id"]: e for e in entries(path)}	


FORMATS = { 
    "pct1": lambda x: f"{x:.1%}", "pct2": lambda x: f"{x:.2%}", "pct3": lambda x: f"{x:.3%}", "pct4": lambda x: f"{x:.4%}", 
    "pct6": lambda x: f"{x:.6%}", "pct0": lambda x: f"{x:.0%}", "num2": lambda x: f"{x:,.2f}", "num3": lambda x: f"{x:,.3f}", "num4": lambda x: f"{x:.4f}", 
    "num6": lambda x: f"{x:.6f}", "m1": lambda x: f"${x:,.1f}M", "m3": lambda x: f"${x:,.3f}M", "px": lambda x: f"${x:,.2f}", 
    "x1": lambda x: f"{x:.1f}x", "x2": lambda x: f"{x:.2f}x", "int": lambda x: f"{x:.0f}", "sci": lambda x: f"{x:+.2e}", 
    "raw": lambda x: f"{x}", 
} 
TOKEN = re.compile(r"\{([A-Za-z0-9_]+):([a-z0-9]+)\}")	


def render(template: str, ctx: dict) -> str: 
    def sub(m):	
        key, f = m.group(1), m.group(2)	
        if key not in ctx: 
            raise KeyError(f"show-work template references unknown value {key!r}") 
        val = ctx[key] 
        if val is None:	
            return "n/a"	
        if isinstance(val, str): 
            return val 
        return FORMATS[f](float(val)) 
    return TOKEN.sub(sub, template) 


def applies(entry: dict, settings: dict) -> bool: 
    for k, want in (entry.get("when") or {}).items():	
        have = settings.get(k) 
        if isinstance(want, list): 
            if have not in want: 
                return False	
        elif have != want: 
            return False	
    return True 


def context(res) -> dict:	
    """Every number a show-work template can reference (names match formulas.yaml)."""	
    c = {}	
    c.update({k: v for k, v in res.inputs.items() if not isinstance(v, (list, tuple))}) 
    c.update(res.derived) 
    for k, v in res.company.flows.items(): 
        c[f"d_{k}"] = v 
    c["mid"] = 0.5 if res.settings["in_Timing"] == "Mid-year" else 0.0 
    c.update({k: v for k, v in res.settings.items()}) 
    if res.dcf is None: 
        return c	
    d, sch = res.dcf, res.dcf["schedule"] 
    for t in range(1, 12):	
        for k in ("rev", "ebit", "margin", "growth", "tax", "nopat", "da", "ebitda", "capex", "nwc", "ufcf"):	
            c[f"y{t}_{k}"] = float(sch[k][t - 1]) 
        c[f"y{t}_capex_abs"] = -float(sch["capex"][t - 1]) 
        c[f"y{t}_tax_abs"] = -float(sch["tax"][t - 1]) 
        c[f"y{t}_taxable"] = c[f"y{t}_tax_abs"] / res.inputs["in_TaxRate"] if res.inputs["in_TaxRate"] else 0.0	
        if t <= 10:	
            c[f"y{t}_per"] = float(d["per"][t - 1]) 
            c[f"y{t}_pv"] = float(d["pv"][t - 1]) 
            c[f"y{t}_df"] = float(1 / (1 + res.inputs["in_WACC"]) ** d["per"][t - 1]) 
    c["y0_rev"] = res.inputs["in_Rev0"] 
    for k, v in {"dcf_SumPV": d["sum_pv"], "dcf_TV": d["tv"], "dcf_TVPer": d["tv_per"], "dcf_PVTV": d["pv_tv"], 
                 "dcf_EV": d["ev"], "dcf_Equity": d["equity"], "dcf_FV": d["fv"], "dcf_Upside": d["upside"],	
                 "dcf_TVShare": d["tv_share"], "dcf_ImpMult": d["imp_mult"], "dcf_ImpG": d["imp_g"], 
                 "dcf_NPVCheck": d["npv_check"], "dcf_SensCentre": None if res.sens is None else res.sens["centre"]}.items(): 
        c[k] = None if v is None else float(v) 
    c["exit_metric_value"] = {"EV/EBITDA": c["y10_ebitda"], "EV/UFCF": c["y10_ufcf"], "EV/Revenue": c["y10_rev"]}[res.settings["in_ExitMetric"]]	
    c["wacc_minus_g"] = res.inputs["in_WACC"] - res.inputs["in_TermG"] 
    c["tv_df"] = 1 / (1 + res.inputs["in_WACC"]) ** d["tv_per"]	
    for t in (0, 1, 5, 10): 
        x = res.vot[t] if res.vot else None	
        for k in ("ev", "net_cash", "equity", "shares", "price", "ann_return"):	
            c[f"vot{t}_{k}"] = None if x is None else x[k]	
    rd = res.rdcf 
    c.update({"rd_G": rd["g"], "rd_Target": rd["target"], "rd_EV": rd["ev"], "rd_TieOut": rd["tieout"], 
              "rd_Roots": float(rd["roots"]), "rd_Residual": rd["residual"], "rd_Gap": rd["gap"], 
              "rd_FcCAGR": rd["forecast_cagr"], "rd_a1": float(rd["coef_a"][0]), "rd_a10": float(rd["coef_a"][9]), 
              "rd_a11": float(rd["coef_a"][10]), "rd_b": float(rd["coef_b"]), "rd_m1": float(rd["margins"][0]), 
              "rd_Status": rd["status"], "rd_Solution": rd["solution_text"] or (f"{rd['g']:.4%}" if rd["g"] is not None else "")}) 
    if rd["first"]: 
        c["rd_lo0"], c["rd_hi0"] = rd["grid"][rd["first"] - 1], rd["grid"][rd["first"]]	
        c["rd_flo0"], c["rd_fhi0"] = rd["f"][rd["first"] - 1], rd["f"][rd["first"]] 
        c["rd_width"] = abs(rd["steps"][-1][1] - rd["steps"][-1][0])	
    else:	
        c["rd_lo0"] = c["rd_hi0"] = c["rd_flo0"] = c["rd_fhi0"] = c["rd_width"] = None 
    if rd["proof"]: 
        p = rd["proof"] 
        c.update({"rd_SumPV": p["sum_pv"], "rd_TV": float(p["tv"]), "rd_PVTV": float(p["pv_tv"]),	
                  "rd_y1_rev": float(p["schedule"]["rev"][0]), "rd_y10_rev": float(p["schedule"]["rev"][9]),	
                  "rd_y1_ufcf": float(p["schedule"]["ufcf"][0]), "rd_y11_ufcf": float(p["schedule"]["ufcf"][10])}) 
    else: 
        for k in ("rd_SumPV", "rd_TV", "rd_PVTV", "rd_y1_rev", "rd_y10_rev", "rd_y1_ufcf", "rd_y11_ufcf"): 
            c[k] = None 
    ir = res.irr 
    H = ir["H"]	
    rh = ir["rows"][H] 
    c.update({"irr_IRR": ir["irr"], "irr_Entry": ir["entry"], "irr_Exit": ir["exit"], "irr_EntryPS": ir["entry_ps"], 
              "irr_ExitPx": ir["exit_price"], "irr_H": float(H), "irr_MetricH_PS": rh["metric_ps"], "irr_NCPS_H": rh["nc_ps"], 
              "irr_CumDiv": rh["cum_div"], "irr_PxCAGR": ir["price_cagr"], "irr_SimpleRet": ir["simple_return"],	
              "irr_DG": ir["dg"], "irr_S": ir["share_chg"], "irr_SharesH": rh["shares"], "irr_MetricH": rh["metric_total"], 
              "irr_Metric0": ir["rows"][0]["metric_total"], "irr_SensCentre": ir["sens"]["centre"],	
              "irr_Mult": res.settings["irr_Mult"], "irr_Kind": ir["kind"], "irr_DPS0": ir["dps0"], 
              "irr_TotalMult": ir["total_multiple"], "irr_note": ir["irr_note"] or ""})	
    sc = res.scen	
    if sc is not None:	
        c["th_H"], c["th_V0"], c["th_PT"], c["th_WSum"] = sc["H"], sc["v0"], sc["pt"], sc["weight_sum"] 
        for name, cs in sc["cases"].items(): 
            c[f"th_V0{name}"], c[f"th_PT{name}"], c[f"th_W{name}"], c[f"th_CAGR{name}"] = cs["v0"], cs["pt"], cs["weight"], cs["cagr"] 
            c[f"th_G1{name}"], c[f"th_M10{name}"] = float(cs["schedule"]["growth"][0]), float(cs["schedule"]["margin"][9]) 
    c["irr_CF"] = ", ".join("n/m" if x is None else f"{x:,.2f}" for x in ir["cash_flows"][:H + 1]) 
    return c 


def chain(name: str, res, path=REGISTRY_PATH): 
    """[(entry, rendered string)] for one output's chain of formulas, filtered to the active settings."""	
    reg = load_registry(path) 
    ids = reg["chains"][name]	
    idx = by_id(path)	
    ctx = context(res) 
    out = [] 
    for i in ids: 
        e = idx[i]	
        if not applies(e, res.settings):	
            continue 
        out.append((e, render(e["show"], ctx) if e.get("show") else "")) 
    return out 
