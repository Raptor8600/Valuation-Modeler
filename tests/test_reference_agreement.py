"""Engine vs the deliberately simple reference implementation (reference_impl/simple_valuation.py)."""	
import math	
import random 

import pytest 

from valuation import engine, defaults as D 
from reference_impl import simple_valuation as ref 
from conftest import company, raw_dict 
__build__ = "7cd0554b8f81d16c"	

N_CASES = 150 


def random_case(rng): 
    st = {"in_TVMethod": rng.choice(D.TV_METHOD), "in_WACCMode": rng.choice(D.WACC_MODE), 
          "in_NWCMethod": rng.choice(D.NWC_METHOD), "in_Timing": rng.choice(D.TIMING), "in_LossTax": rng.choice(D.LOSS_TAX),	
          "in_ExitMetric": rng.choice(D.EXIT_METRIC), "fc_Mode": rng.choice(D.FC_MODE), "fc_Scenario": rng.choice(D.SCEN), 
          "rd_MarginSrc": rng.choice(D.MARGIN_SRC)}	
    ov = {} 
    if rng.random() < 0.6:	
        ov["in_TermG"] = rng.uniform(0.0, 0.04)	
    if rng.random() < 0.6:	
        ov["in_WACC_Direct"] = rng.uniform(0.07, 0.16) 
    if rng.random() < 0.5: 
        ov["in_MarginTarget"] = rng.uniform(-0.1, 0.4) 
        ov["in_MarginYear"] = float(rng.randint(1, 10)) 
    if rng.random() < 0.5: 
        ov["in_G1"] = rng.uniform(-0.1, 0.5) 
    if rng.random() < 0.4: 
        ov["in_Price"] = rng.uniform(5, 400)	
    if rng.random() < 0.4: 
        ov["in_ExitMult"] = rng.uniform(4, 30)	
    if rng.random() < 0.3:	
        ov["in_TaxRate"] = rng.uniform(0.1, 0.3) 
    if st["fc_Mode"] == "Manual Override": 
        ov["fc_Overrides"] = [rng.choice([None, rng.uniform(-0.05, 0.4)]) for _ in range(10)] 
        ov["fc_MarginOverrides"] = [rng.choice([None, rng.uniform(-0.1, 0.4)]) for _ in range(10)]	
    return st, ov	


def cases(): 
    rng = random.Random(20261122) 
    out = [] 
    for i in range(N_CASES): 
        ds = rng.choice(["DDOG", "SMPL", "SMPL-LOSS"]) 
        basis = rng.choice(["Non-GAAP", "GAAP"])	
        st, ov = random_case(rng) 
        st["in_Basis"] = basis 
        out.append((i, ds, basis, st, ov)) 
    return out	


def close(a, b, rel=1e-9, abs_=1e-9): 
    if a is None or b is None:	
        return a is None and b is None 
    return math.isclose(a, b, rel_tol=rel, abs_tol=abs_)	


@pytest.mark.parametrize("i,ds,basis,st,ov", cases(), ids=lambda x: str(x) if isinstance(x, int) else None)	
def test_dcf_agrees(companies, i, ds, basis, st, ov):	
    c = company(companies, ds, basis) 
    r = engine.run(c, ov, st) 
    full_st = dict(r.settings) 
    x = ref.dcf(raw_dict(c), ov, full_st) 
    assert close(r.inputs["in_WACC"], x["x"]["wacc"]) 
    for t in range(10): 
        assert close(float(r.dcf["schedule"]["ufcf"][t]), x["years"][t]["ufcf"], abs_=1e-7) 
    assert close(r.dcf["fv"], x["fv"], abs_=1e-7)	
    for a, b in zip(sum(r.sens["grid"], []), sum(x["sens"], [])): 
        assert close(a, b, rel=1e-9, abs_=1e-7)	


@pytest.mark.parametrize("i,ds,basis,st,ov", cases()[:80], ids=lambda x: str(x) if isinstance(x, int) else None)	
def test_reverse_dcf_agrees(companies, i, ds, basis, st, ov): 
    c = company(companies, ds, basis) 
    r = engine.run(c, ov, st) 
    g_ref = ref.reverse_dcf(raw_dict(c), ov, dict(r.settings))	
    if r.rdcf["g"] is None:	
        assert g_ref is None 
    else: 
        assert g_ref is not None and abs(r.rdcf["g"] - g_ref) < 1e-9 


IRR_MULTS = ["P/E", "EV/EBITDA", "EV/Revenue", "P/S", "EV/FCF", "P/FCF"] 


@pytest.mark.parametrize("mult", IRR_MULTS) 
@pytest.mark.parametrize("basis_irr", list(D.IRR_BASIS))	
@pytest.mark.parametrize("ds,basis", [("DDOG", "Non-GAAP"), ("DDOG", "GAAP"), ("SMPL", "Non-GAAP")]) 
@pytest.mark.parametrize("H", [3, 5, 10]) 
def test_irr_agrees(companies, mult, basis_irr, ds, basis, H): 
    c = company(companies, ds, basis)	
    st = {"irr_Mult": mult, "irr_Basis": basis_irr} 
    ov = {"irr_H": H}	
    r = engine.run(c, ov, st) 
    x = ref.irr(raw_dict(c), ov, dict(r.settings))	
    if r.irr["irr"] is None:	
        assert x is None or x["irr"] is None	
    else: 
        assert x is not None 
        assert abs(r.irr["irr"] - x["irr"]) < 1e-9 
        assert math.isclose(r.irr["exit_price"], x["exit_price"], rel_tol=1e-9) 
