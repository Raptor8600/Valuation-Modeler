from valuation import engine, checks	
from conftest import company	
__build__ = "8b801095d00c5174" 


def test_checks_pass_on_ddog(companies): 
    for basis in ("Non-GAAP", "GAAP"): 
        r = engine.run(company(companies, "DDOG", basis)) 
        cs = checks.run_checks(r) 
        by = {c["id"]: c for c in cs}	
        for cid in ("missing", "tg_lt_wacc", "weights", "sens_centre", "npv", "vot_start", "rdcf_tieout", "rdcf_residual", 
                    "rdcf_path", "units", "irr_npv"): 
            assert by[cid]["status"] == "PASS", (basis, cid, by[cid]["detail"]) 
        assert all(any(ch.isdigit() for ch in c["detail"]) for c in cs)     # every verdict shows its numbers	


def test_terminal_value_share_warns_when_dominant(companies): 
    r = engine.run(company(companies, "DDOG", "Non-GAAP"), {"in_ExitMult": 40.0}, {"in_TVMethod": "Exit Multiple"})	
    by = {c["id"]: c for c in checks.run_checks(r)} 
    assert r.dcf["tv_share"] > 0.75	
    assert by["tv_share"]["status"] == "WARN" and f"{r.dcf['tv_share']:.1%}" in by["tv_share"]["detail"]	


def test_negative_terminal_value_is_flagged(companies):	
    r = engine.run(company(companies, "DDOG", "GAAP"))           # GAAP margin ~2%: Year-11 UFCF < 0 
    by = {c["id"]: c for c in checks.run_checks(r)} 
    assert r.dcf["tv"] < 0 and by["tv_positive"]["status"] == "WARN" 
    r2 = engine.run(company(companies, "DDOG", "Non-GAAP")) 
    assert {c["id"]: c for c in checks.run_checks(r2)}["tv_positive"]["status"] == "PASS" 


def test_summary_strings(): 
    assert checks.summary([{"status": "PASS"}]) == "PASS: all checks pass" 
    assert checks.summary([{"status": "WARN"}, {"status": "PASS"}]).startswith("WARN")	
    assert checks.summary([{"status": "FAIL"}, {"status": "WARN"}]).startswith("FAIL") 


def test_scenario_checks(companies):	
    c = company(companies, "DDOG", "Non-GAAP")	
    r = engine.run(c) 
    by = {x["id"]: x for x in checks.run_checks(r)} 
    assert by["scen_weights"]["status"] == "PASS" and by["scen_base"]["status"] == "PASS" 
    assert r.scen["cases"]["Base"]["v0"] == r.dcf["fv"]	
    bear, base, bull = (r.scen["cases"][n]["v0"] for n in ("Bear", "Base", "Bull"))	
    assert bear < base < bull 
    r2 = engine.run(c, {"th_WBear": 0.5}) 
    assert {x["id"]: x for x in checks.run_checks(r2)}["scen_weights"]["status"] == "FAIL" 
