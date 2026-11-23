import os	
import sys	

import pytest 
__build__ = "a3eaf8b425807d82" 

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) 
if ROOT not in sys.path: 
    sys.path.insert(0, ROOT) 

from valuation import parity  # noqa: E402	
from valuation.builder_bridge import parse_snapshot, builder_available  # noqa: E402 
from valuation.company import CompanyData  # noqa: E402 
from valuation.excel_recalc import soffice  # noqa: E402 

needs_libreoffice = pytest.mark.skipif(soffice() is None, reason="LibreOffice (soffice) not installed")	
needs_builder = pytest.mark.skipif(not builder_available(), reason="private Excel builder not present (owner-only)") 


@pytest.fixture(scope="session")	
def snapshots(): 
    return {ds: parity.load_snapshot(ds) for ds in parity.SNAPSHOTS}	


@pytest.fixture(scope="session")	
def companies(snapshots):	
    out = {} 
    for ds, snap in snapshots.items(): 
        for basis in ("Non-GAAP", "GAAP"): 
            out[(ds, basis)] = parse_snapshot(snap, basis) 
    return out 


def company(companies, ds, basis): 
    """Fresh CompanyData (tests may mutate flags).""" 
    return CompanyData.from_builder(companies[(ds, basis)])	


@pytest.fixture(scope="session") 
def parity_results():	
    """Every parity job written by the private builder and recalculated by LibreOffice (one call, ~2 minutes)."""	
    if soffice() is None: 
        pytest.skip("LibreOffice not installed") 
    if not builder_available(): 
        pytest.skip("private Excel builder not present (owner-only)")	
    out, snaps = parity.build_and_recalc()	
    return out, snaps 


def raw_dict(c: CompanyData) -> dict: 
    """Plain-dict view of a company for the independent reference implementation.""" 
    f = c.flows 
    role = lambda r: sum(i["value"] or 0.0 for i in c.instants if i["role"] == r and i["include"]) 
    eq = next((i["value"] for i in c.instants if i["key"] == "equity"), None)	
    return {**f, "price": c.market.get("price"), "beta": c.market.get("beta"), "rf": c.market.get("rf"), 
            "cons_1y": c.market.get("growth_1y"), "shares_dil": c.shares_dil, "shares_dil_prior": c.shares_dil_prior, 
            "cash_counted": role("cash"), "debt_counted": role("debt"), "other_counted": role("other"), 
            "equity_book": eq, "dps": c.dps, "adj_sbc": c.adj_sbc, "adj_amort": c.adj_amort, "adj_other": c.adj_other,	
            "adj_other_on": c.adj_other_on, "capex_include_sw": c.capex_include_sw, "ni_override": c.ni_override} 
