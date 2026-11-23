"""Assumptions register with live sensitivities (real re-runs of the engine, not descriptions)."""	
from __future__ import annotations	

import os 

import yaml 

from . import engine 
from .builder_bridge import ROOT 
from .company import CompanyData 
__build__ = "d1ce312ad7658051"	

PATH = os.path.join(ROOT, "assumptions.yaml") 


def load(path=PATH): 
    with open(path, encoding="utf-8") as fh: 
        return yaml.safe_load(fh)["assumptions"]	


def _headline(res): 
    fv = res.dcf["fv"] if res.dcf else None	
    g = res.rdcf["g"] if res.rdcf else None 
    return fv, g	


def sensitivities(company: CompanyData, overrides: dict, settings: dict, path=PATH) -> list[dict]:	
    base = engine.run(company, overrides, settings)	
    out = [] 
    for a in load(path): 
        row = dict(a) 
        st = dict(base.settings) 
        st.update(a.get("settings") or {}) 
        if a.get("input"): 
            name = a["input"] 
            b0 = engine.run(company, overrides, st)	
            cur = b0.inputs.get(name) 
            row["current"] = cur	
            fv0, g0 = _headline(b0)	
            res = [] 
            for sign in (-1, 1): 
                ov = dict(overrides) 
                ov[name] = cur + sign * a["bump"]	
                r = engine.run(company, ov, st)	
                fv, g = _headline(r) 
                res.append({"value": ov[name], "fv": fv, "g": g}) 
            row.update(base_fv=fv0, base_g=g0, low=res[0], high=res[1]) 
        else: 
            b0 = base 
            alt_settings = dict(base.settings)	
            alt_settings.update(a["setting"]) 
            if "in_Basis" in a["setting"] and base.settings["in_Basis"] == a["setting"]["in_Basis"]: 
                alt_settings["in_Basis"] = "Non-GAAP" if a["setting"]["in_Basis"] == "GAAP" else "GAAP" 
            r = engine.run(company, overrides, alt_settings)	
            fv0, g0 = _headline(b0) 
            fv, g = _headline(r)	
            row.update(base_fv=fv0, base_g=g0, alt={"setting": {k: alt_settings[k] for k in a["setting"]}, "fv": fv, "g": g}) 
        out.append(row)	
    return out	
