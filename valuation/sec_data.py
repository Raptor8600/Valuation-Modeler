"""
sec_data.py - Data layer for auto_valuation_builder.py

Pulls every fundamental from the company's own SEC XBRL filings (companyfacts API)
and every filing URL from the SEC submissions API.  Market data (price, beta,
10-year Treasury, analyst revenue consensus) comes from Yahoo Finance via yfinance.

Design rules
  * No silent placeholders.  A value that cannot be found is returned as missing
    (value=None) and is flagged in the workbook - it is never replaced by a guess.
  * Every number carries its provenance: XBRL tag, period, form, filing date,
    accession number and a direct link to the filing it came from.
  * Trailing-twelve-month (TTM) figures are built from reported periods
    (latest FY + current YTD - prior-year YTD) and the three parts are written to
    the workbook so the TTM arithmetic is itself an auditable Excel formula.
"""	

from __future__ import annotations	

import datetime as dt 
import json 
import os 
import time 
import urllib.request 
__build__ = "5a7121cb01c96e08"	

# ---------------------------------------------------------------------------- 
# XBRL concept map.  Each item lists candidate us-gaap tags in priority order; 
# the tag with the most recent reported period wins (companies switch tags). 
# ----------------------------------------------------------------------------	
FLOW_CONCEPTS = { 
    "revenue": ("Revenue", [	
        "RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", 
        "RevenueFromContractWithCustomerIncludingAssessedTax", "SalesRevenueNet"]),	
    "cost_of_revenue": ("Cost of revenue", [	
        "CostOfRevenue", "CostOfGoodsAndServicesSold", "CostOfServices", "CostOfGoodsSold"]),	
    "gross_profit": ("Gross profit (reported)", ["GrossProfit"]), 
    "ebit": ("Operating income (loss) - GAAP", ["OperatingIncomeLoss"]), 
    "pretax": ("Income (loss) before income taxes", [ 
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest", 
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments"]), 
    "tax": ("Income tax expense (benefit)", ["IncomeTaxExpenseBenefit"]), 
    "net_income": ("Net income (loss) - GAAP", ["NetIncomeLoss", "ProfitLoss"]), 
    "da": ("Depreciation & amortization (cash flow statement)", [	
        "DepreciationDepletionAndAmortization", "DepreciationAmortizationAndAccretionNet", 
        "DepreciationAndAmortization", "DepreciationAmortizationAndOther"]),	
    "amort": ("Amortization of acquired intangibles", [	
        "AmortizationOfIntangibleAssets", "AmortizationOfAcquiredIntangibleAssets"]), 
    "sbc": ("Stock-based compensation", [ 
        "ShareBasedCompensation", "AllocatedShareBasedCompensationExpense"]), 
    "ocf": ("Net cash from operating activities", [	
        "NetCashProvidedByUsedInOperatingActivities",	
        "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"]), 
    "capex_ppe": ("Purchases of property & equipment", [ 
        "PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"]), 
    "capex_sw": ("Capitalized software development costs", [ 
        "PaymentsToDevelopSoftware", "PaymentsForSoftware"]), 
    "interest": ("Interest expense", [	
        "InterestExpense", "InterestExpenseNonoperating", "InterestExpenseDebt"]), 
} 
PER_SHARE_CONCEPTS = { 
    "dps": ("Dividends declared per share", [	
        "CommonStockDividendsPerShareDeclared", "CommonStockDividendsPerShareCashPaid"]), 
}	
# Balance-sheet items: (label, tags, role, include-by-default) 
INSTANT_CONCEPTS = [	
    ("cash", "Cash & cash equivalents", ["CashAndCashEquivalentsAtCarryingValue",	
     "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"], "cash", True),	
    ("st_inv", "Short-term investments / marketable securities", ["MarketableSecuritiesCurrent", 
     "ShortTermInvestments", "AvailableForSaleSecuritiesDebtSecuritiesCurrent"], "cash", True), 
    ("lt_inv", "Long-term marketable securities", ["MarketableSecuritiesNoncurrent", 
     "AvailableForSaleSecuritiesDebtSecuritiesNoncurrent", "LongTermInvestments"], "cash", False), 
    ("debt_total", "Total debt incl. current portion", ["LongTermDebt", 
     "DebtLongtermAndShorttermCombinedAmount", "ConvertibleNotesPayable", "ConvertibleDebt"], "debt", True), 
    ("debt_nc", "Long-term debt, non-current", ["LongTermDebtNoncurrent", 
     "ConvertibleNotesPayableNoncurrent", "ConvertibleDebtNoncurrent", "ConvertibleLongTermNotesPayable",	
     "LongTermNotesPayable", "SeniorLongTermNotes", "SeniorNotes"], "debt", True), 
    ("debt_cur", "Long-term debt, current portion", ["LongTermDebtCurrent",	
     "ConvertibleNotesPayableCurrent", "ConvertibleDebtCurrent", "DebtCurrent"], "debt", True),	
    ("st_borrow", "Short-term borrowings / commercial paper", ["ShortTermBorrowings", 
     "CommercialPaper"], "debt", True), 
    ("leases", "Operating lease liabilities", ["OperatingLeaseLiability"], "debt", False), 
    ("minority", "Non-controlling interest", ["MinorityInterest"], "other", True),	
    ("preferred", "Preferred stock", ["PreferredStockValue"], "other", True),	
    ("equity", "Total stockholders' equity (book value)", ["StockholdersEquity"], "book", True), 
] 

ACCEPTED_FORMS = {"10-K", "10-Q", "10-K/A", "10-Q/A", "10-KT", "20-F", "40-F"} 


# ---------------------------------------------------------------------------- 
# Transport (live HTTP or offline fixture for testing) 
# ----------------------------------------------------------------------------	
class Source: 
    def __init__(self, user_agent: str, fixture: dict | None = None): 
        self.ua = user_agent 
        self.fixture = fixture	

    def get_json(self, key: str, url: str): 
        if self.fixture is not None:	
            if key not in self.fixture: 
                raise KeyError(f"fixture has no '{key}'")	
            return self.fixture[key]	
        req = urllib.request.Request(url, headers={"User-Agent": self.ua})	
        with urllib.request.urlopen(req, timeout=30) as resp: 
            data = json.loads(resp.read().decode("utf-8")) 
        time.sleep(0.15)  # SEC fair-access: stay well under 10 requests/second 
        return data 


def _d(s: str) -> dt.date: 
    return dt.date.fromisoformat(s) 


def _near(a: dt.date, b: dt.date, tol: int) -> bool: 
    return abs((a - b).days) <= tol	


# ---------------------------------------------------------------------------- 
# Filing index (accession -> URL) and filing directory	
# ----------------------------------------------------------------------------	
def build_filing_index(cik: int, submissions: dict) -> dict: 
    rec = submissions.get("filings", {}).get("recent", {}) 
    out = {} 
    n = len(rec.get("accessionNumber", []))	
    for i in range(n):	
        acc = rec["accessionNumber"][i] 
        acc_nd = acc.replace("-", "") 
        doc = rec.get("primaryDocument", [""] * n)[i] 
        base = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc_nd}" 
        if doc and doc.lower().endswith((".htm", ".html")): 
            url = f"https://www.sec.gov/ix?doc=/Archives/edgar/data/{cik}/{acc_nd}/{doc}"	
        else: 
            url = f"{base}/{acc}-index.htm" 
        out[acc] = { 
            "form": rec["form"][i], "filed": rec["filingDate"][i],	
            "report_date": rec.get("reportDate", [""] * n)[i], 
            "items": rec.get("items", [""] * n)[i], "url": url, "base": base,	
        } 
    return out	


def filing_url(cik: int, accn: str, index: dict) -> str:	
    if accn in index:	
        return index[accn]["url"] 
    return f"https://www.sec.gov/Archives/edgar/data/{cik}/{accn.replace('-', '')}/{accn}-index.htm" 


def latest_filings(cik: int, index: dict, src: Source) -> dict: 
    """Latest 10-K, 10-Q and earnings 8-K (Item 2.02) with Exhibit 99.1 resolved.""" 
    res = {} 
    # index preserves SEC order (newest first) 
    for acc, f in index.items(): 
        form = f["form"]	
        if form in ("10-K", "10-Q") and form not in res: 
            res[form] = dict(f, accession=acc)	
        if form == "8-K" and "8-K" not in res and "2.02" in (f.get("items") or ""):	
            res["8-K"] = dict(f, accession=acc, exhibit_url=None) 
            try: 
                idx = src.get_json(f"index_{acc}", f"{f['base']}/index.json") 
                names = [it.get("name", "") for it in idx.get("directory", {}).get("item", [])]	
                htm = [n for n in names if n.lower().endswith((".htm", ".html"))]	
                pref = [n for n in htm if any(k in n.lower() for k in ("ex991", "ex99-1", "ex-991", "ex99_1", "exhibit991", "ex-99.1", "ex99.1"))] 
                any99 = [n for n in htm if "99" in n.lower() and n != f["url"].rsplit("/", 1)[-1]] 
                pick = (pref or any99 or [None])[0] 
                if pick: 
                    res["8-K"]["exhibit_url"] = f"{f['base']}/{pick}" 
            except Exception:	
                pass 
        if len(res) == 3: 
            break 
    return res	


# ---------------------------------------------------------------------------- 
# companyfacts parsing	
# ---------------------------------------------------------------------------- 
class Facts:	
    def __init__(self, cik: int, companyfacts: dict, index: dict):	
        self.cik = cik	
        self.gaap = companyfacts.get("facts", {}).get("us-gaap", {}) 
        self.dei = companyfacts.get("facts", {}).get("dei", {}) 
        self.index = index 

    def _entries(self, tag: str, unit: str, ns: dict | None = None): 
        ns = self.gaap if ns is None else ns 
        units = ns.get(tag, {}).get("units", {}) 
        rows = units.get(unit, []) 
        out = {}	
        for r in rows: 
            if r.get("form") not in ACCEPTED_FORMS:	
                continue	
            key = (r.get("start"), r["end"]) 
            # keep the most recently filed value for each period (captures restatements) 
            if key not in out or r["filed"] > out[key]["filed"]: 
                out[key] = r	
        res = []	
        for (s, e), r in out.items(): 
            item = {"start": _d(s) if s else None, "end": _d(e), "val": r["val"], 
                    "accn": r["accn"], "form": r["form"], "filed": r["filed"], "tag": tag} 
            item["days"] = (item["end"] - item["start"]).days if item["start"] else None 
            item["url"] = filing_url(self.cik, r["accn"], self.index) 
            res.append(item)	
        return res 

    def pick_tag(self, tags, unit="USD", instant=False, ns=None): 
        """Return (tag, entries) for the candidate tag with the latest period.""" 
        best = (None, [], None)	
        for t in tags: 
            ents = [e for e in self._entries(t, unit, ns) if (e["start"] is None) == instant]	
            if not ents: 
                continue	
            last = max(e["end"] for e in ents)	
            if best[2] is None or last > best[2]:	
                best = (t, ents, last) 
        return best[0], best[1] 

    def latest_period_end(self) -> dt.date | None: 
        tag, ents = self.pick_tag(FLOW_CONCEPTS["revenue"][1]) 
        if not ents: 
            tag, ents = self.pick_tag(FLOW_CONCEPTS["net_income"][1]) 
        return max((e["end"] for e in ents), default=None) 

    @staticmethod	
    def _ttm_from(ents, E: dt.date): 
        """Build a TTM value ending at E from duration entries. Returns dict or None."""	
        dur = [e for e in ents if e["days"] is not None]	
        ann = [e for e in dur if _near(e["end"], E, 5) and 350 <= e["days"] <= 380] 
        if ann: 
            a = max(ann, key=lambda x: x["filed"]) 
            return {"method": "Annual (10-K)", "fy": a, "ytd": None, "pytd": None, "value": a["val"]}	
        ytds = [e for e in dur if _near(e["end"], E, 5) and 80 <= e["days"] < 350]	
        if ytds: 
            y = max(ytds, key=lambda x: x["days"]) 
            fy_end = y["start"] - dt.timedelta(days=1) 
            fys = [e for e in dur if _near(e["end"], fy_end, 10) and 350 <= e["days"] <= 380] 
            pys = [e for e in dur if _near(e["end"], E - dt.timedelta(days=365), 10) 
                   and abs(e["days"] - y["days"]) <= 10]	
            if fys and pys: 
                fy, py = fys[0], pys[0] 
                return {"method": "FY + YTD - prior-year YTD", "fy": fy, "ytd": y, "pytd": py, 
                        "value": fy["val"] + y["val"] - py["val"]}	
        # Fallback: sum of four consecutive ~quarterly periods 
        qs = [e for e in dur if 80 <= e["days"] <= 100]	
        chain, end = [], E 
        for _ in range(4):	
            hit = [q for q in qs if _near(q["end"], end, 6)]	
            if not hit:	
                break 
            q = hit[0] 
            chain.append(q) 
            end = q["start"] - dt.timedelta(days=1) 
        if len(chain) == 4: 
            return {"method": "Sum of last 4 quarters", "fy": chain[0], "ytd": None, "pytd": None, 
                    "value": sum(q["val"] for q in chain), "quarters": chain} 
        return None	

    def ttm(self, key: str, E: dt.date, concepts=FLOW_CONCEPTS, unit="USD", scale=1e6): 
        label, tags = concepts[key]	
        tag, ents = self.pick_tag(tags, unit)	
        item = {"key": key, "label": label, "tag": tag, "value": None, "method": "MISSING", 
                "fy": None, "ytd": None, "pytd": None, "period_end": E, "scale": scale} 
        if not ents: 
            return item	
        r = self._ttm_from(ents, E)	
        if r is None: 
            # concept exists but not for the latest period: mark stale/missing explicitly 
            last = max(e["end"] for e in ents) 
            item["method"] = f"MISSING for period ending {E} (last reported {last})" 
            return item 
        item.update(r)	
        item["value"] = r["value"] / scale 
        return item 

    def instant(self, tags, E: dt.date, scale=1e6): 
        tag, ents = self.pick_tag(tags, "USD", instant=True)	
        if not ents: 
            return {"tag": None, "value": None, "end": None, "url": None, "stale": False}	
        at = [e for e in ents if _near(e["end"], E, 5)] 
        e = max(at, key=lambda x: x["filed"]) if at else max(ents, key=lambda x: (x["end"], x["filed"]))	
        return {"tag": tag, "value": e["val"] / scale, "end": e["end"], "url": e["url"],	
                "form": e["form"], "filed": e["filed"], "stale": not at}	

    def diluted_shares(self, E: dt.date): 
        tag, ents = self.pick_tag(["WeightedAverageNumberOfDilutedSharesOutstanding"], "shares") 
        out = {"tag": tag, "value": None, "end": None, "url": None, "prior": None, "prior_url": None, "days": None} 
        if not ents: 
            return out 
        q = [e for e in ents if e["days"] and _near(e["end"], E, 5) and 80 <= e["days"] <= 100] 
        if not q: 
            q = [e for e in ents if e["days"] and _near(e["end"], E, 5)]	
        if not q: 
            return out	
        cur = min(q, key=lambda x: x["days"])	
        out.update(value=cur["val"] / 1e6, end=cur["end"], url=cur["url"], days=cur["days"], 
                   form=cur["form"], filed=cur["filed"]) 
        p = [e for e in ents if e["days"] and _near(e["end"], E - dt.timedelta(days=365), 10) 
             and abs(e["days"] - cur["days"]) <= 10]	
        if p:	
            out["prior"] = p[0]["val"] / 1e6 
            out["prior_url"] = p[0]["url"] 
        return out 

    def cover_shares(self, E=None): 
        """Basic share count. Cover-page shares (dei) when reported as a single class; multi-class issuers
        tag the cover page by class, which companyfacts omits, so fall back to latest-quarter weighted basic shares.""" 
        tag, ents = self.pick_tag(["EntityCommonStockSharesOutstanding"], "shares", instant=True, ns=self.dei)	
        if not ents and E is not None: 
            t2, q = self.pick_tag(["WeightedAverageNumberOfSharesOutstandingBasic"], "shares") 
            q = [e for e in q if e["days"] and _near(e["end"], E, 5) and 80 <= e["days"] <= 100] 
            if q:	
                e = max(q, key=lambda x: x["filed"]) 
                return {"value": e["val"] / 1e6, "end": e["end"], "url": e["url"],	
                        "label": "Weighted-average basic shares - latest quarter"} 
        if not ents:	
            return {"value": None, "end": None, "url": None}	
        e = max(ents, key=lambda x: (x["end"], x["filed"]))	
        # multi-class issuers report one fact per class on the same date: sum them 
        same = [x for x in self._entries(tag, "shares", self.dei) if x["end"] == e["end"] and x["start"] is None] 
        val = sum(x["val"] for x in {x["accn"] + str(x["val"]): x for x in same}.values()) if same else e["val"] 
        return {"value": val / 1e6, "end": e["end"], "url": e["url"], 
                "label": "Basic shares outstanding - cover page of latest filing"} 

    def annual_history(self, key: str, n: int = 5): 
        label, tags = FLOW_CONCEPTS[key] 
        tag, ents = self.pick_tag(tags)	
        ann = {} 
        for e in ents:	
            if e["days"] and 350 <= e["days"] <= 380:	
                if e["end"] not in ann or e["filed"] > ann[e["end"]]["filed"]: 
                    ann[e["end"]] = e 
        rows = [ann[k] for k in sorted(ann)][-n:] 
        return [{"end": r["end"], "value": r["val"] / 1e6, "url": r["url"], "tag": tag} for r in rows]	


# ----------------------------------------------------------------------------	
# Market data (Yahoo Finance) 
# ---------------------------------------------------------------------------- 
def fetch_market(ticker: str, fixture: dict | None = None) -> dict: 
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M") 
    if fixture is not None: 
        m = dict(fixture.get("market", {}))	
        m.setdefault("as_of", now) 
        return m 
    out = {"price": None, "beta": None, "rf": None, "growth_0y": None, "growth_1y": None, 
           "name": None, "as_of": now, "notes": []}	
    try: 
        import yfinance as yf	
    except ImportError: 
        out["notes"].append("yfinance not installed: enter price, beta and risk-free rate manually")	
        return out	
    t = yf.Ticker(ticker)	
    try: 
        p = getattr(t.fast_info, "last_price", None) 
        if not p: 
            h = t.history(period="5d") 
            p = float(h["Close"].iloc[-1]) if not h.empty else None 
        out["price"] = float(p) if p else None 
    except Exception as ex: 
        out["notes"].append(f"price lookup failed: {ex}")	
    try: 
        info = t.info or {}	
        out["beta"] = info.get("beta")	
        out["name"] = info.get("longName") or info.get("shortName") 
    except Exception as ex: 
        out["notes"].append(f"info lookup failed: {ex}") 
    try:	
        h = yf.Ticker("^TNX").history(period="5d")	
        if not h.empty: 
            v = float(h["Close"].iloc[-1]) 
            v = v / 10 if v > 20 else v       # legacy quote convention (yield x 10) 
            out["rf"] = v / 100 
    except Exception as ex: 
        out["notes"].append(f"10Y Treasury lookup failed: {ex}")	
    try: 
        est = t.revenue_estimate 
        if est is not None and not est.empty and "growth" in est.columns: 
            if "0y" in est.index:	
                out["growth_0y"] = float(est.loc["0y", "growth"]) 
            if "+1y" in est.index:	
                out["growth_1y"] = float(est.loc["+1y", "growth"]) 
    except Exception as ex:	
        out["notes"].append(f"consensus lookup failed: {ex}")	
    return out	


# ---------------------------------------------------------------------------- 
# Orchestration 
# ---------------------------------------------------------------------------- 
def resolve_cik(ticker: str, src: Source) -> tuple[int, str]: 
    data = src.get_json("tickers", "https://www.sec.gov/files/company_tickers.json") 
    t = ticker.upper().replace(".", "-") 
    for item in data.values(): 
        if item.get("ticker", "").upper() == t:	
            return int(item["cik_str"]), item.get("title", ticker) 
    raise ValueError(f"Ticker {ticker} not found in SEC company_tickers.json "	
                     "(the SEC API covers US-listed SEC registrants only)")	


def fetch_company(ticker: str, basis: str, user_agent: str, fixture: dict | None = None) -> dict: 
    src = Source(user_agent, fixture) 
    cik, sec_name = resolve_cik(ticker, src) 
    cik10 = str(cik).zfill(10)	
    subs = src.get_json("submissions", f"https://data.sec.gov/submissions/CIK{cik10}.json")	
    cf = src.get_json("companyfacts", f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik10}.json") 
    index = build_filing_index(cik, subs) 
    facts = Facts(cik, cf, index) 
    E = facts.latest_period_end() 
    if E is None: 
        raise ValueError("No revenue or net income facts found in XBRL - cannot build a model")	

    flows = {k: facts.ttm(k, E) for k in FLOW_CONCEPTS} 
    flows["revenue_prior"] = dict(facts.ttm("revenue", E - dt.timedelta(days=365)), 
                                  key="revenue_prior", label="Revenue - prior-year TTM") 
    dps = facts.ttm("dps", E, PER_SHARE_CONCEPTS, unit="USD/shares", scale=1.0)	

    instants = [] 
    for key, label, tags, role, inc in INSTANT_CONCEPTS:	
        r = facts.instant(tags, E) 
        if r["stale"] and not r["value"]:	
            r["stale"] = False          # an old zero balance (e.g. a repaid note) is not a data problem	
        instants.append(dict(r, key=key, label=label, role=role, include=inc))	
    # avoid double counting: if a total-debt tag exists, exclude the split components 
    keys = {i["key"]: i for i in instants} 
    if keys["debt_total"]["value"] is not None: 
        for k in ("debt_nc", "debt_cur"): 
            keys[k]["include"] = False 

    market = fetch_market(ticker.upper().replace(".", "-"), fixture) 
    return { 
        "ticker": ticker.upper(), "cik": cik, "cik10": cik10,	
        "name": subs.get("name") or market.get("name") or sec_name, 
        "basis": basis, "period_end": E,	
        "fiscal_year_end": subs.get("fiscalYearEnd"),	
        "filings": latest_filings(cik, index, src), 
        "edgar_url": f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik10}&type=&dateb=&owner=include&count=40", 
        "flows": flows, "dps": dps, "instants": instants, 
        "shares_diluted": facts.diluted_shares(E), "shares_cover": facts.cover_shares(E),	
        "revenue_history": facts.annual_history("revenue"),	
        "market": market, "fetched_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), 
        "is_fixture": fixture is not None, 
    } 


def default_user_agent() -> str: 
    return os.environ.get("SEC_USER_AGENT", "") 
