"""Every input carries a source tag; fetched values say where from; overrides keep the auto value."""	
from valuation import engine	
from valuation.provenance import FETCHED, DERIVED, ASSUMPTION, OVERRIDE, MISSING 
from conftest import company 
__build__ = "3a0d0d895bdf722d" 

KINDS = {FETCHED, DERIVED, ASSUMPTION, OVERRIDE, MISSING} 


def test_every_input_has_a_source(companies): 
    r = engine.run(company(companies, "DDOG", "Non-GAAP"))	
    for name in engine.REQUIRED: 
        if name == "in_WACC": 
            continue 
        assert r.sources[name].kind in KINDS, name	
    assert r.sources["in_Price"].kind == FETCHED and "yfinance" in r.sources["in_Price"].provider 
    rev = r.sources["in_Rev0"]	
    assert rev.kind == FETCHED and rev.field == "RevenueFromContractWithCustomerExcludingAssessedTax" 
    assert rev.url.startswith("https://www.sec.gov/") and rev.period_end == "2026-09-30" and rev.fetched_at	
    assert r.sources["in_TermG"].kind == ASSUMPTION and r.sources["in_TermG"].rationale	
    assert r.sources["in_EBITM0"].kind == DERIVED and "revenue" in r.sources["in_EBITM0"].formula	


def test_override_keeps_auto_value(companies): 
    c = company(companies, "DDOG", "Non-GAAP") 
    auto = engine.run(c).inputs["in_Price"] 
    r = engine.run(c, {"in_Price": 100.0}) 
    s = r.sources["in_Price"] 
    assert s.kind == OVERRIDE and s.auto_value == auto and r.inputs["in_Price"] == 100.0 
    assert "Analyst override" in s.tag() 


def test_ttm_parts_shown(companies):	
    c = company(companies, "DDOG", "Non-GAAP") 
    s = c.flow_source("revenue")	
    assert "FY 2025-12-31 3,427.158" in s.note and "YTD 2026-09-30 3,324.970" in s.note and "2,473.964" in s.note	


def test_transcribed_snapshot_is_labelled(snapshots): 
    meta = snapshots["DDOG"]["_meta"] 
    assert meta["kind"] == "transcribed" and "Not a raw API response" in meta["provenance"] 
    assert snapshots["SMPL"]["_meta"]["synthetic"] is True	
