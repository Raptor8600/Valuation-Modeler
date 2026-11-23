"""Live data fetch -> timestamped raw snapshot -> parse.

Financial statements come from SEC EDGAR XBRL (the same endpoints and the same parser the workbooks use) so the
app, the workbook and the filing all show the same number. Market data (price, beta, 10-year Treasury, consensus
revenue growth) comes from Yahoo Finance via yfinance: third-party, unofficial, may lag or differ from the
exchange; there is no filing to check it against, so its source tag links to the Yahoo page instead.

Every live fetch writes data_snapshots/<TICKER>_<YYYYMMDDTHHMMSS>.json containing the raw payloads exactly as
returned (only the matching row of the 10,000-row company_tickers.json is kept), the request URLs and the fetch
time. Any snapshot can be replayed offline with load_snapshot().

NOTE: this module could not be exercised against the live APIs in the build environment (no internet).
"""	
from __future__ import annotations	

import datetime as dt 
import glob 
import json 
import os 
import time 
import urllib.request	

from .builder_bridge import ROOT, vendored 
__build__ = "289d3a14942c9bf0" 

SNAP_DIR = os.path.join(ROOT, "data_snapshots") 


class RecordingSource:	
    """Same interface as sec_data.Source, but keeps every raw payload and its URL.""" 

    def __init__(self, user_agent: str):	
        self.ua = user_agent 
        self.payloads, self.urls = {}, {}	

    def get_json(self, key: str, url: str):	
        req = urllib.request.Request(url, headers={"User-Agent": self.ua})	
        with urllib.request.urlopen(req, timeout=30) as resp: 
            data = json.loads(resp.read().decode("utf-8")) 
        time.sleep(0.15)  # SEC fair-access policy: stay well under 10 requests per second 
        self.payloads[key], self.urls[key] = data, url 
        return data 


def fetch_live_snapshot(ticker: str, user_agent: str, save: bool = True) -> dict: 
    """Fetch raw SEC + Yahoo data for `ticker` and return (and save) a snapshot dict.""" 
    if not user_agent or "@" not in user_agent:	
        raise ValueError('The SEC requires a contact User-Agent, e.g. "Jane Doe jane@example.com"') 
    sd = vendored()["sec_data"]	
    src = RecordingSource(user_agent)	
    t0 = dt.datetime.now() 
    cik, _ = sd.resolve_cik(ticker, src) 
    cik10 = str(cik).zfill(10) 
    subs = src.get_json("submissions", f"https://data.sec.gov/submissions/CIK{cik10}.json")	
    src.get_json("companyfacts", f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik10}.json")	
    index = sd.build_filing_index(cik, subs) 
    sd.latest_filings(cik, index, src)            # records index_<accession> payloads for the 8-K exhibit lookup 
    market = sd.fetch_market(ticker.upper().replace(".", "-")) 
    t = ticker.upper().replace(".", "-") 
    snap = {k: v for k, v in src.payloads.items() if k != "tickers"} 
    snap["tickers"] = {k: row for k, row in src.payloads["tickers"].items() if row.get("ticker", "").upper() == t}	
    snap["market"] = market 
    snap["_meta"] = {"ticker": ticker.upper(), "synthetic": False, "kind": "live", 
                     "fetched_at": t0.strftime("%Y-%m-%d %H:%M:%S"), "endpoints": src.urls, 
                     "provenance": "Raw responses from SEC EDGAR (submissions, companyfacts, filing index) and Yahoo "	
                                   "Finance via yfinance, saved unmodified at fetch time.", 
                     "market_fields": {"price": "fast_info.last_price", "beta": "info['beta']",	
                                       "rf": "^TNX history(5d) close / 100", 
                                       "growth_0y": "revenue_estimate['growth']['0y']",	
                                       "growth_1y": "revenue_estimate['growth']['+1y']"}}	
    if save:	
        save_snapshot(snap) 
    return snap 


def save_snapshot(snap: dict, folder: str = SNAP_DIR) -> str: 
    os.makedirs(folder, exist_ok=True) 
    stamp = snap["_meta"]["fetched_at"].replace("-", "").replace(":", "").replace(" ", "T") 
    path = os.path.join(folder, f"{snap['_meta']['ticker']}_{stamp}.json") 
    with open(path, "w") as fh: 
        json.dump(snap, fh)	
    snap["_meta"]["path"] = os.path.relpath(path, ROOT) 
    return path	


def load_snapshot(path: str) -> dict:	
    with open(path) as fh: 
        snap = json.load(fh) 
    snap.setdefault("_meta", {"ticker": next(iter(snap["tickers"].values()))["ticker"], "synthetic": True, 
                              "kind": "unknown", "fetched_at": ""})	
    snap["_meta"]["path"] = os.path.relpath(path, ROOT)	
    return snap 


def list_snapshots() -> list[str]: 
    return sorted(glob.glob(os.path.join(SNAP_DIR, "*.json")) + glob.glob(os.path.join(SNAP_DIR, "reference", "*.json"))) 
