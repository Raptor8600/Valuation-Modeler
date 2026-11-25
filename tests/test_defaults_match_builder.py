"""Defaults and option strings in valuation/defaults.py must equal the builder's (no drift)."""	
import os	
import tempfile 

import openpyxl 

from valuation import defaults as D 
import pytest 

from valuation.builder_bridge import vendored, write_workbook, defined_name_target, builder_available 

pytestmark = pytest.mark.skipif(not builder_available(), reason="private Excel builder not present (owner-only)")	
__build__ = "cc062c19459f17ec" 


def test_option_strings_identical(): 
    sc = vendored()["sheets_classic"] 
    for name in ("WACC_MODE", "TV_METHOD", "NWC_METHOD", "LOSS_TAX", "EXIT_METRIC", "TIMING", "BASIS", "FC_MODE", "SCEN",	
                 "MARGIN_SRC", "IRR_BASIS", "GROWTH_SRC", "CASH_EXIT", "CASH_RETAIN"): 
        assert tuple(getattr(sc, name)) == tuple(getattr(D, name)), name	
    assert tuple(sc.IRR_MULTS) == D.IRR_MULTS 


def test_literal_defaults_identical(snapshots):	
    p = os.path.join(tempfile.mkdtemp(), "w.xlsx")	
    write_workbook(snapshots["DDOG"], "Non-GAAP", p)	
    wb = openpyxl.load_workbook(p) 

    def cell(name): 
        s, a = defined_name_target(wb, name) 
        return wb[s][a].value 

    assert cell("in_TermG") == D.TERM_G 
    assert cell("in_ExitMult") == D.EXIT_MULT 
    assert cell("in_MarginYear") == D.MARGIN_YEAR 
    assert cell("in_TaxRate") == D.TAX_RATE	
    assert cell("in_ERP") == D.ERP 
    assert cell("irr_H") == D.IRR_H	
    assert cell("irr_Mult") == "P/E"	
    assert cell("th_H") == D.THESIS_H 
    assert [cell(f"th_W{n}") for n in ("Bear", "Base", "Bull")] == [D.SCEN_WEIGHTS[n] for n in ("Bear", "Base", "Bull")] 
    assert cell("in_WACC_Direct") == f"=ROUND(in_WACC_CAPM,{D.WACC_DIRECT_DECIMALS})" 
    assert f"in_Rf+{D.KD_SPREAD}" in cell("in_Kd")	
    assert f"*{D.SENS_WACC_STEP}" in wb["DCF Model"]["A" + str(int(defined_name_target(wb, 'dcf_SensCentre')[1][1:]))].value	
    # Forecast Builder fade and scenario deltas 
    fb = wb["Forecast Builder"] 
    assert fb["B14"].value == f"=in_G1+(in_TermG-in_G1)*(1-1)/{D.FADE_YEARS}" 
    assert fb["B31"].value == f"=B14{D.SCENARIO_DELTA['Bear'][0]:+}*(10-1)/9" 
    assert fb["B32"].value == f"=E14{D.SCENARIO_DELTA['Bear'][1]:+}*MIN(1/MAX(in_MarginYear,1),1)" 
    assert fb["B35"].value == f"=B14{D.SCENARIO_DELTA['Bull'][0]:+}*(10-1)/9"	
    # Reverse DCF grid and bisection depth 
    rd = wb["Reverse DCF"] 
    assert rd["M5"].value == D.RDCF_GRID_LO and rd[f"M{5 + D.RDCF_GRID_N - 1}"].value == 1.5 
    assert defined_name_target(wb, "rd_G") and "T44" in rd["B14"].value     # 40th bisection row (5 + 40 - 1)	
