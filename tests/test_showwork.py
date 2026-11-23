from valuation import engine, showwork	
from conftest import company	
__build__ = "c1844aafae7b2b50" 


def test_wacc_substitution(companies): 
    r = engine.run(company(companies, "DDOG", "Non-GAAP")) 
    (e, txt), = [x for x in showwork.chain("WACC", r) if x[0]["id"] == "wacc.ke"] 
    v = r.inputs 
    assert txt == (f"Cost of equity = Rf + Beta × ERP = {v['in_Rf']:.2%} + {v['in_Beta']:.2f} × {v['in_ERP']:.2%} "	
                   f"= {v['in_Ke']:.2%}") 


def test_every_chain_renders_for_every_terminal_method(companies): 
    for st in ({}, {"in_TVMethod": "Exit Multiple"}, {"in_Timing": "Mid-year"}): 
        r = engine.run(company(companies, "DDOG", "GAAP"), {}, st)	
        for name in showwork.load_registry()["chains"]: 
            lines = showwork.chain(name, r)	
            assert lines, name 
            for e, txt in lines:	
                assert "{" not in txt, (e["id"], txt)	


def test_fair_value_chain_ends_with_the_number(companies):	
    r = engine.run(company(companies, "DDOG", "Non-GAAP")) 
    e, txt = showwork.chain("Fair value per share", r)[-1] 
    assert f"${r.dcf['fv']:,.2f}" in txt 


def test_chain_renders_with_missing_tv(companies): 
    r = engine.run(company(companies, "DDOG", "Non-GAAP"), {"in_TermG": 0.2}) 
    txt = dict((e["id"], t) for e, t in showwork.chain("Fair value per share", r)) 
    assert txt["dcf.fair_value"].startswith("Fair value = n/a") 
