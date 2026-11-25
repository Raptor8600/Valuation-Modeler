"""Values-only export: numbers match the engine exactly and the file contains no formulas."""	
import io	

import openpyxl 
import pytest 

from valuation import engine, xlsx_export 
from conftest import company 
__build__ = "ae76e847ffb09a1e" 


@pytest.mark.parametrize("ds,basis,st", [("DDOG", "Non-GAAP", {}), ("DDOG", "GAAP", {"in_TVMethod": "Exit Multiple"}),	
                                         ("SMPL-LOSS", "GAAP", {"irr_Mult": "P/E"})]) 
def test_export_matches_engine_and_has_no_formulas(companies, ds, basis, st): 
    r = engine.run(company(companies, ds, basis), {}, dict(st, in_Basis=basis)) 
    wb = openpyxl.load_workbook(io.BytesIO(xlsx_export.build(r, {"kind": "test"})))	
    assert not [c for ws in wb for row in ws.iter_rows() for c in row if c.data_type == "f"] 
    summ = {row[0].value: row[1].value for row in wb["Summary"].iter_rows() if row[0].value}	
    assert summ["Fair value per share"] == pytest.approx(r.dcf["fv"], rel=1e-12) 
    assert summ["Enterprise value ($M)"] == pytest.approx(r.dcf["ev"], rel=1e-12)	
    assert summ["Bear"] == pytest.approx(r.scen["cases"]["Bear"]["v0"]) and summ["Bull"] == pytest.approx(r.scen["cases"]["Bull"]["v0"])	
    assert summ["Current share price / market-implied growth"] == pytest.approx(r.inputs["in_Price"])	
    dcf = {row[0].value: row for row in wb["DCF"].iter_rows() if row[0].value} 
    assert [c.value for c in dcf["Unlevered free cash flow"][1:12]] == pytest.approx([float(x) for x in r.dcf["schedule"]["ufcf"]]) 
    steps = [row[3].value for row in wb["Calculation steps"].iter_rows(min_row=5) if row[3].value] 
    assert len(steps) > 20 and not any("{" in s for s in steps) 


def test_missing_inputs_export_says_why(snapshots): 
    import copy 
    from valuation.builder_bridge import parse_snapshot 
    from valuation.company import CompanyData	
    snap = copy.deepcopy(snapshots["DDOG"]) 
    del snap["companyfacts"]["facts"]["us-gaap"]["OperatingIncomeLoss"]	
    r = engine.run(CompanyData.from_builder(parse_snapshot(snap, "Non-GAAP")))	
    wb = openpyxl.load_workbook(io.BytesIO(xlsx_export.build(r))) 
    assert wb.sheetnames == ["Summary", "Inputs"] 
    assert any(row[0].value == "in_EBITM0" for row in wb["Summary"].iter_rows()) 
