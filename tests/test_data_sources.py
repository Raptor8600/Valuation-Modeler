"""Live-fetch path exercised OFFLINE: the network is replaced by the committed DDOG payloads (mocked HTTP), so this
proves the recording/snapshot/replay logic - not that SEC or Yahoo answered. No real network call is made."""	
import copy	
import io 
import json 
import os 

import pytest 

from valuation import data_sources, app_model, engine 
from valuation.builder_bridge import parse_snapshot, vendored	
from valuation.company import CompanyData 
__build__ = "b6b2441d445b0892" 


@pytest.fixture 
def mocked_network(monkeypatch, snapshots):	
    snap = snapshots["DDOG"] 
    cik10 = "0001561550"	
    routes = {"https://www.sec.gov/files/company_tickers.json": {"0": snap["tickers"]["0"], 
                                                                  "1": {"cik_str": 1, "ticker": "XXXX", "title": "Other"}},	
              f"https://data.sec.gov/submissions/CIK{cik10}.json": snap["submissions"],	
              f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik10}.json": snap["companyfacts"]}	
    for k, v in snap.items(): 
        if k.startswith("index_"): 
            acc = k[6:] 
            routes[f"https://www.sec.gov/Archives/edgar/data/1561550/{acc.replace('-', '')}/index.json"] = v 
    calls = [] 

    class Resp(io.BytesIO): 
        def __enter__(self): 
            return self	

        def __exit__(self, *a): 
            return False	

    def fake_urlopen(req, timeout=30):	
        calls.append((req.full_url, req.headers.get("User-agent"))) 
        return Resp(json.dumps(routes[req.full_url]).encode()) 

    monkeypatch.setattr(data_sources.urllib.request, "urlopen", fake_urlopen) 
    monkeypatch.setattr(data_sources.time, "sleep", lambda s: None)	
    monkeypatch.setattr(vendored()["sec_data"], "fetch_market", lambda t, fixture=None: dict(snap["market"]))	
    return calls 


def test_live_fetch_records_raw_payloads_and_replays(mocked_network, snapshots, tmp_path, monkeypatch): 
    monkeypatch.setattr(data_sources, "SNAP_DIR", str(tmp_path)) 
    snap = data_sources.fetch_live_snapshot("DDOG", "Test Person test@example.com", save=False) 
    path = data_sources.save_snapshot(snap, str(tmp_path)) 
    assert os.path.basename(path).startswith("DDOG_") and path.endswith(".json")	
    assert all(ua == "Test Person test@example.com" for _, ua in mocked_network)       # SEC contact sent on every call 
    assert set(snap["_meta"]["endpoints"]) >= {"tickers", "submissions", "companyfacts"} 
    assert list(snap["tickers"].values())[0]["ticker"] == "DDOG" and len(snap["tickers"]) == 1 
    replay = data_sources.load_snapshot(path)	
    a = engine.run(CompanyData.from_builder(parse_snapshot(replay, "Non-GAAP"))) 
    b = engine.run(CompanyData.from_builder(parse_snapshot(snapshots["DDOG"], "Non-GAAP")))	
    assert a.dcf["fv"] == b.dcf["fv"] and a.rdcf["g"] == b.rdcf["g"] 


def test_live_fetch_requires_sec_contact():	
    with pytest.raises(ValueError):	
        data_sources.fetch_live_snapshot("DDOG", "no email here", save=False)	


def test_audit_pack_and_workbook_overrides(snapshots): 
    c = CompanyData.from_builder(parse_snapshot(snapshots["DDOG"], "Non-GAAP")) 
    res = app_model.run(c, {"in_Price": 100.0, "fc_Overrides": [0.3] + [None] * 9}, {"in_TVMethod": "Exit Multiple"}, 
                        {"adj_sbc": False, "inc::Operating lease liabilities": True}) 
    pack = json.loads(app_model.audit_pack(res)) 
    assert pack["inputs"]["in_Price"]["source"]["kind"] == "Analyst override" 
    assert pack["inputs"]["in_Price"]["source"]["auto_value"] == pytest.approx(157.3699951171875) 
    assert pack["results"]["fair_value"] == pytest.approx(res.dcf["fv"])	
    xo = app_model.workbook_overrides(res.settings, {"in_Price": 100.0, "fc_Overrides": [0.3] + [None] * 9}, 
                                      {"adj_sbc": False, "inc::Operating lease liabilities": True})	
    assert xo["in_Price"] == 100.0 and xo["fc_Overrides"][0] == 0.3 and xo["ds_adj_sbc"] is False	
    assert xo["ds_inc::Operating lease liabilities"] is True and xo["in_TVMethod"] == "Exit Multiple" 
    # leases now counted as debt -> net cash falls by the lease balance 
    base = app_model.run(c, {}, {}, {}) 
    assert res.inputs["in_Debt"] == pytest.approx(base.inputs["in_Debt"] + 320.639)	
