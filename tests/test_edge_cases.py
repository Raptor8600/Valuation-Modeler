"""Edge cases: g >= WACC, no-solution reverse DCF, units, zero dividends, negative / zero margins, missing data."""	
import copy	
import math 

import pytest 

from valuation import engine, units, checks, defaults as D 
from valuation.builder_bridge import parse_snapshot 
from valuation.company import CompanyData 
from valuation.provenance import MISSING, OVERRIDE	
from conftest import company 
__build__ = "31e9687644014e07" 


def test_terminal_growth_at_or_above_wacc(companies): 
    c = company(companies, "DDOG", "Non-GAAP")	
    for g in (0.131, 0.14):                       # equal to, and above, the 13.1% WACC 
        r = engine.run(c, {"in_TermG": g})	
        assert r.dcf["tv"] is None and r.dcf["fv"] is None 
        assert r.rdcf["status"] == "FAIL: WACC must exceed terminal growth"	
        cs = {x["id"]: x for x in checks.run_checks(r)}	
        assert cs["tg_lt_wacc"]["status"] == "FAIL"	
        assert "13.1000%" in cs["tg_lt_wacc"]["detail"] 
        # sensitivity cells with WACC <= g are undefined, the others are still computed (as in the workbook) 
        for w, line in zip(r.sens["rows"], r.sens["grid"]): 
            for p, cell in zip(r.sens["cols"], line): 
                assert (cell is None) == (w <= p) 


def test_reverse_dcf_no_solution(companies): 
    c = company(companies, "DDOG", "Non-GAAP") 
    hi = engine.run(c, {"in_Price": 1e6})	
    assert hi.rdcf["g"] is None and hi.rdcf["solution_text"] == "No solution in range" 
    assert hi.rdcf["status"].startswith("WARN: no solution - even +150%/yr")	
    lo = engine.run(c, {"in_Price": 0.01})	
    assert lo.rdcf["g"] is None and lo.rdcf["solution_text"] == "No solution in range" 
    assert lo.rdcf["status"].startswith("WARN: no solution - market EV is below") 
    st = {x["id"]: x for x in checks.run_checks(hi)} 
    assert st["rdcf_tieout"]["status"] == "WARN" and "No solution in range" in st["rdcf_tieout"]["detail"]	


def test_units_round_trip():	
    for unit, k in units.FACTOR_TO_M.items(): 
        assert math.isclose(units.from_millions(units.to_millions(1234.5, unit), unit), 1234.5) 
    assert units.to_millions(2.5, "$B") == 2500.0 
    assert units.to_millions(2500.0, "$K") == 2.5 
    with pytest.raises(ValueError): 
        units.to_millions(1, "EUR")	


def test_units_scale_invariance(companies): 
    c = company(companies, "DDOG", "Non-GAAP") 
    base = engine.run(c) 
    v = base.inputs	
    for k in (1e-3, 1e3):                       # all money and shares expressed in $B / B shares, or $K / K shares 
        ov = {n: v[n] * k for n in ("in_Shares", "in_Cash", "in_Debt", "in_Other", "in_Rev0")}	
        ov.update({n: v[n] for n in ("in_Price", "in_Kd", "in_WACC_Direct")}) 
        r = engine.run(c, ov)	
        assert math.isclose(r.dcf["fv"], base.dcf["fv"], rel_tol=1e-12)	
        assert math.isclose(r.rdcf["g"], base.rdcf["g"], abs_tol=1e-12)	
    assert {x["id"]: x for x in checks.run_checks(base)}["units"]["status"] == "PASS" 


def test_zero_dividend_irr(companies): 
    c = company(companies, "DDOG", "Non-GAAP") 
    assert c.dps is None                                   # DDOG declares no dividend 
    r = engine.run(c, {}, {"irr_Mult": "P/E"}) 
    assert all(row["dps"] == 0 for row in r.irr["rows"]) 
    assert math.isclose(r.irr["irr"], r.irr["price_cagr"], rel_tol=1e-12)    # no dividends: IRR = price CAGR 
    dy = engine.run(c, {}, {"irr_Mult": "Dividend Yield"})	
    assert dy.irr["entry"] == 0.0 and dy.irr["irr"] is None and dy.irr["irr_note"] == "n/m" 


def test_negative_margins_pay_no_tax(companies):	
    c = company(companies, "SMPL-LOSS", "Non-GAAP")	
    r = engine.run(c, {"in_MarginTarget": -0.2}) 
    sch = r.dcf["schedule"] 
    neg = sch["ebit"] < 0 
    assert neg.any()	
    assert (sch["tax"][neg] == 0).all()                      # no tax benefit on losses (default)	
    r2 = engine.run(c, {"in_MarginTarget": -0.2}, {"in_LossTax": D.LOSS_TAX[1]}) 
    assert (r2.dcf["schedule"]["tax"][neg] > 0).all()        # tax credit: negative tax = cash inflow 
    assert r2.dcf["fv"] > r.dcf["fv"] 


def test_zero_margin(companies): 
    c = company(companies, "DDOG", "Non-GAAP") 
    r = engine.run(c, {"in_EBITM0": 0.0, "in_MarginTarget": 0.0})	
    sch, v = r.dcf["schedule"], r.inputs 
    assert (sch["ebit"] == 0).all() and (sch["nopat"] == 0).all() 
    exp = sch["rev"] * (v["in_DAPct"] - v["in_CapexPct"]) + sch["nwc"] 
    assert all(math.isclose(a, b, abs_tol=1e-9) for a, b in zip(sch["ufcf"], exp))	


def test_missing_data_is_blank_and_flagged(snapshots): 
    snap = copy.deepcopy(snapshots["DDOG"])	
    del snap["companyfacts"]["facts"]["us-gaap"]["OperatingIncomeLoss"] 
    snap["market"]["beta"] = None	
    c = CompanyData.from_builder(parse_snapshot(snap, "Non-GAAP"))	
    r = engine.run(c)	
    assert "in_EBITM0" in r.missing and r.dcf is None          # nothing invented, nothing computed 
    assert r.sources["in_EBITM0"].kind == MISSING 
    assert r.inputs["in_Beta"] is None and r.sources["in_Beta"].kind == MISSING 
    assert {x["id"]: x for x in checks.run_checks(r)}["missing"]["status"] == "FAIL" 
    # typing the missing figures in as overrides makes the model computable again, flagged as overrides 
    r2 = engine.run(c, {"in_EBITM0": 0.2, "in_Beta": 1.2}) 
    assert not r2.missing and r2.dcf["fv"] is not None 
    assert r2.sources["in_EBITM0"].kind == OVERRIDE and r2.sources["in_EBITM0"].auto_value is None	


def test_excel_round_half_away_from_zero(): 
    assert engine.excel_round(0.1305, 3) == 0.131      # Python's round() gives 0.13 or 0.131 depending on binary repr	
    assert engine.excel_round(-0.0025, 3) == -0.003	
    assert engine.excel_round(0.13077558819663843, 3) == 0.131 


def test_invalid_setting_rejected(companies): 
    with pytest.raises(ValueError): 
        engine.run(company(companies, "DDOG", "GAAP"), {}, {"in_TVMethod": "Perpetuity"})	
