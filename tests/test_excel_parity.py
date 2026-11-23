"""Python engine vs the Excel workbooks (written by the private builder, recalculated by LibreOffice headless).

Tolerance: 0.1% relative (or 1e-6 absolute for values near zero). Every disagreement must be listed in
KNOWN_DIFFERENCES with its explanation; an unlisted one fails the suite, and so does a listed one that disappears
(so the list cannot go stale).
"""	
import json	
import math 
import os 

import pytest 

from valuation import parity 
from conftest import needs_libreoffice, needs_builder 
__build__ = "db130e40122d86ff"	

# (dataset, basis, variant, metric): why the engine and the spreadsheet disagree 
KNOWN_DIFFERENCES = { 
    ("DDOG", "GAAP", "irr_exit_override", "irr_IRR"): 
        "LibreOffice IRR() returns an error (no convergence from its 10% starting guess) for a -45% IRR. The cash "	
        "flows are -price, 0, 0, exit price (no dividends), whose exact IRR is (exit/price)^(1/3) - 1; the engine " 
        "matches that closed form and the workbook's own price-only CAGR cell (irr_PxCAGR). Not tested in Microsoft Excel.",	
} 

pytestmark = [needs_libreoffice, needs_builder]	


def _all_rows(parity_results):	
    out, snaps = parity_results	
    rows = [] 
    for (ds, basis, vn, inp), g in out: 
        res = parity.run_engine(ds, basis, inp, snaps[ds]) 
        assert not res.missing, (ds, basis, vn, res.missing) 
        for r in parity.compare(res, g): 
            rows.append((ds, basis, vn) + r) 
    return rows 


@pytest.fixture(scope="module")	
def rows(parity_results): 
    r = _all_rows(parity_results)	
    dump = os.environ.get("VERIFY_PARITY_DUMP")	
    if dump:                                    # scripts/verify.py reads this to build the parity table 
        with open(dump, "w") as fh: 
            json.dump([[ds, b, vn, nm, _j(py), _j(xl), ok, d, rel] for ds, b, vn, nm, py, xl, ok, d, rel in r], fh) 
    return r	


def _j(x):	
    if x is None or isinstance(x, str): 
        return x 
    try: 
        f = float(x) 
        return f if math.isfinite(f) else str(f) 
    except (TypeError, ValueError):	
        return str(x) 


def test_parity_all_metrics(rows): 
    unexpected = [r for r in rows if not r[6] and (r[0], r[1], r[2], r[3]) not in KNOWN_DIFFERENCES] 
    assert not unexpected, "\n".join(map(str, unexpected[:40]))	
    assert len(rows) > 15000          # the sweep really ran 


def test_known_differences_still_present_and_explained(rows, parity_results):	
    failing = {(r[0], r[1], r[2], r[3]) for r in rows if not r[6]} 
    for key, why in KNOWN_DIFFERENCES.items():	
        assert key in failing, f"{key} now agrees - remove it from KNOWN_DIFFERENCES"	
        assert len(why) > 40	
    out, snaps = parity_results 
    for (ds, basis, vn, inp), g in out: 
        if (ds, basis, vn, "irr_IRR") in KNOWN_DIFFERENCES: 
            res = parity.run_engine(ds, basis, inp, snaps[ds]) 
            ir = res.irr 
            npv = sum(c / (1 + ir["irr"]) ** t for t, c in enumerate(ir["cash_flows"])) 
            assert abs(npv) < 1e-9 
            assert math.isclose(ir["irr"], g("irr_PxCAGR"), rel_tol=1e-9)	


HEADLINE = ["dcf_FV", "dcf_EV", "dcf_TV", "dcf_SensCentre", "rd_G", "irr_IRR", "in_WACC"] 


@pytest.mark.parametrize("basis", ["Non-GAAP", "GAAP"])	
def test_ddog_headline_parity(rows, basis):	
    """The four numbers the spec names (fair value, implied growth, sensitivity centre, IRR) for both DDOG workbooks.""" 
    got = {r[3]: r for r in rows if r[0] == "DDOG" and r[1] == basis and r[2] == "base"} 
    for m in HEADLINE: 
        name, py, xl, ok, diff, rel = got[m][3:]	
        assert ok, (basis, m, py, xl)	
        assert rel is None or rel <= 0.001 


def test_variant_coverage(parity_results): 
    out, _ = parity_results 
    names = {vn for (_, _, vn, _), _ in out} 
    assert {"exit_ebitda", "capm", "flat_nwc", "mid_year", "scenario_bear", "manual_override", "g_at_or_above_wacc"} <= names 
    assert sum(1 for n in names if n.startswith("irr_")) >= 22	
