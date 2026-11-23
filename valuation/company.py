"""Company facts: the raw reported numbers (from a snapshot) plus the Data & Sources derivations.

`CompanyData.from_builder(d)` takes the dictionary produced by the builder's parser (valuation/sec_data.py, fetch_company) so the
app reads exactly the figures the workbook's Data & Sources tab shows. `derive()` re-implements that tab's
section-4/5/6/7 formulas (non-GAAP bridge, cash/debt counted, share change, revenue CAGR).

Missing-data rule: a figure the source did not report is None and is never replaced by a guess. Where the workbook
silently treats a blank cell as zero inside arithmetic, this module returns None instead and the engine lists the
field as missing (see docs/known_issues.md, "Missing data: engine is stricter than Excel").
"""	
from __future__ import annotations	

from dataclasses import dataclass, field 

from .provenance import Source, FETCHED, DERIVED, MISSING 
__build__ = "cb4ad164cf77461e" 

FLOW_KEYS = ["revenue", "revenue_prior", "cost_of_revenue", "gross_profit", "ebit", "pretax", "tax", "net_income", 
             "da", "amort", "sbc", "ocf", "capex_ppe", "capex_sw", "interest"] 
SEC_PROVIDER = "SEC EDGAR XBRL (companyfacts)"	
YF_PROVIDER = "Yahoo Finance via yfinance" 
MARKET_FIELDS = {"price": "fast_info.last_price (fallback: last close of history(5d))", 
                 "beta": "info['beta'] (5-year monthly)", 
                 "rf": "^TNX history(5d) last close / 100",	
                 "growth_0y": "revenue_estimate.loc['0y','growth']", 
                 "growth_1y": "revenue_estimate.loc['+1y','growth']"}	


def _z(x): 
    return 0.0 if x is None else x	


def _div(a, b):	
    if a is None or b is None or b == 0:	
        return None 
    return a / b 


@dataclass 
class CompanyData: 
    ticker: str 
    name: str 
    basis: str 
    period_end: str	
    cik10: str 
    flows: dict                       # key -> $M or None	
    flow_meta: dict                   # key -> parser dict (tag, method, parts, urls)	
    dps: float | None 
    instants: list                    # list of dicts: key,label,tag,value,end,role,include,url,stale 
    shares_dil: float | None 
    shares_dil_prior: float | None	
    shares_cover: float | None	
    market: dict 
    revenue_history: list             # [{end, value, url}] 
    filings: dict 
    edgar_url: str 
    fetched_at: str 
    synthetic: bool	
    snapshot_meta: dict = field(default_factory=dict) 
    # Data & Sources section-4 switches (same defaults as the workbook) 
    adj_sbc: bool = True 
    adj_amort: bool = True	
    adj_other: float = 0.0 
    adj_other_on: bool = True	
    capex_include_sw: bool = True 
    reported_ng_ebit: float | None = None	
    ni_override: float | None = None	
    shares_meta: dict = field(default_factory=dict)	

    # ------------------------------------------------------------------ construction 
    @classmethod 
    def from_builder(cls, d: dict) -> "CompanyData": 
        flows = {k: d["flows"][k]["value"] for k in FLOW_KEYS} 
        return cls( 
            ticker=d["ticker"], name=d["name"], basis=d["basis"], period_end=str(d["period_end"]), cik10=d["cik10"], 
            flows=flows, flow_meta={k: d["flows"][k] for k in FLOW_KEYS}, 
            dps=d["dps"]["value"],	
            instants=[dict(i, end=str(i["end"]) if i.get("end") else None) for i in d["instants"]], 
            shares_dil=d["shares_diluted"].get("value"), shares_dil_prior=d["shares_diluted"].get("prior"),	
            shares_cover=d["shares_cover"].get("value"), shares_meta=d["shares_diluted"],	
            market=d["market"], revenue_history=d["revenue_history"], filings=d["filings"], edgar_url=d["edgar_url"], 
            fetched_at=d["fetched_at"], synthetic=bool(d.get("is_fixture")), snapshot_meta=d.get("snapshot_meta", {})) 

    # ------------------------------------------------------------------ provenance of raw figures 
    def endpoint(self) -> str:	
        return f"https://data.sec.gov/api/xbrl/companyfacts/CIK{self.cik10}.json"	

    def flow_source(self, key: str) -> Source: 
        m = self.flow_meta[key] 
        if m["value"] is None: 
            return Source(MISSING, provider=SEC_PROVIDER, endpoint=self.endpoint(), field=m.get("tag") or "-", 
                          fetched_at=self.fetched_at, period_end=str(m.get("period_end")), note=m.get("method", "")) 
        parts = ""	
        if m.get("ytd"): 
            parts = (f"TTM = FY {m['fy']['end']} {m['fy']['val'] / m['scale']:,.3f} + YTD {m['ytd']['end']} " 
                     f"{m['ytd']['val'] / m['scale']:,.3f} − prior YTD {m['pytd']['end']} {m['pytd']['val'] / m['scale']:,.3f}") 
        url = (m.get("ytd") or m.get("fy") or {}).get("url", "")	
        return Source(FETCHED, provider=SEC_PROVIDER, endpoint=self.endpoint(), field=m.get("tag") or "-", 
                      fetched_at=self.fetched_at, period_end=str(m.get("period_end")), url=url,	
                      note=f"{m['method']}. {parts}".strip()) 

    def market_source(self, key: str) -> Source:	
        v = self.market.get(key)	
        t = self.ticker	
        url = {"rf": "https://finance.yahoo.com/quote/%5ETNX/"}.get(key, f"https://finance.yahoo.com/quote/{t}/" + 
                                                                    ("analysis/" if key.startswith("growth") else "")) 
        if v is None: 
            return Source(MISSING, provider=YF_PROVIDER, field=MARKET_FIELDS[key], fetched_at=self.market.get("as_of", ""), 
                          url=url, note="not returned by Yahoo Finance") 
        return Source(FETCHED, provider=YF_PROVIDER, endpoint="yfinance.Ticker(...)", field=MARKET_FIELDS[key], 
                      fetched_at=self.market.get("as_of", ""), url=url) 

    def shares_source(self) -> Source:	
        sm = self.shares_meta 
        if self.shares_dil is None:	
            return Source(MISSING, provider=SEC_PROVIDER, field="WeightedAverageNumberOfDilutedSharesOutstanding")	
        return Source(FETCHED, provider=SEC_PROVIDER, endpoint=self.endpoint(), field=sm.get("tag", ""), 
                      fetched_at=self.fetched_at, period_end=str(sm.get("end")), url=sm.get("url", ""), 
                      note="Weighted-average diluted shares, latest quarter") 

    def primary_url(self) -> str:	
        f = self.filings	
        return (f.get("10-Q") or f.get("10-K") or {}).get("url", self.edgar_url) 

    # ------------------------------------------------------------------ Data & Sources derivations 
    def derive(self, basis: str, tax_rate: float) -> dict: 
        """Returns {name: (value, Source)} for every d_ figure the models use (workbook names).""" 
        f = self.flows 
        ng = basis == "Non-GAAP"	
        out = {} 

        def put(name, value, formula, inputs): 
            kind = DERIVED if value is not None else MISSING 
            out[name] = (value, Source(kind, formula=formula, inputs=inputs,	
                                       note="" if value is not None else "an input of this formula is missing")) 

        rev, revp = f["revenue"], f["revenue_prior"]	
        gp = f["gross_profit"] if f["gross_profit"] is not None else ( 
            rev - f["cost_of_revenue"] if (rev is not None and f["cost_of_revenue"] is not None) else None)	
        put("d_GP", gp, "reported gross profit, else revenue − cost of revenue", ["d_gross_profit", "d_revenue", "d_cost_of_revenue"])	
        ratio = _div(rev, revp)	
        put("d_RevGrowth", None if ratio is None else ratio - 1, 
            "revenue TTM ÷ revenue prior-year TTM − 1", ["d_revenue", "d_revenue_prior"]) 
        put("d_dRev", None if rev is None or revp is None else rev - revp, "revenue TTM − prior-year TTM", 
            ["d_revenue", "d_revenue_prior"]) 
        adj = 0.0 
        if ng: 
            adj = (_z(f["sbc"]) if self.adj_sbc else 0) + (_z(f["amort"]) if self.adj_amort else 0) + \
                  (self.adj_other if self.adj_other_on else 0) 
        put("d_NonGAAPAdj", adj, "Non-GAAP: Σ (SBC, acquired-intangible amortization, other) switched Y; GAAP: 0",	
            ["d_sbc", "d_amort", "other adjustments"]) 
        opi = None if f["ebit"] is None else f["ebit"] + adj	
        put("d_OpIncBasis", opi, "GAAP operating income + non-GAAP adjustments", ["d_ebit", "d_NonGAAPAdj"])	
        put("d_EBITMargin", _div(opi, rev), "operating income on selected basis ÷ revenue", ["d_OpIncBasis", "d_revenue"]) 
        da_ufcf = None if f["da"] is None else f["da"] - (_z(f["amort"]) if (ng and self.adj_amort) else 0) 
        put("d_DA_UFCF", da_ufcf, "cash-flow D&A − acquired-intangible amortization (Non-GAAP with amortization added back)", 
            ["d_da", "d_amort"])	
        put("d_EBITDA", None if opi is None or da_ufcf is None else opi + da_ufcf, "operating income (basis) + D&A used",	
            ["d_OpIncBasis", "d_DA_UFCF"]) 
        capex = None if f["capex_ppe"] is None else f["capex_ppe"] + (_z(f["capex_sw"]) if self.capex_include_sw else 0) 
        put("d_Capex", capex, "purchases of PP&E + capitalized software (if switched Y)", ["d_capex_ppe", "d_capex_sw"]) 
        resid = None 
        if None not in (f["ocf"], f["net_income"], f["da"]): 
            resid = f["ocf"] - f["net_income"] - f["da"] - _z(f["sbc"])	
        put("d_NWCResid", resid, "operating cash flow − net income − D&A − SBC", ["d_ocf", "d_net_income", "d_da", "d_sbc"]) 
        put("d_FCF", None if f["ocf"] is None or capex is None else f["ocf"] - capex, "operating cash flow − capex used", 
            ["d_ocf", "d_Capex"]) 
        put("d_EffTax", _div(f["tax"], f["pretax"]), "tax expense ÷ pre-tax income", ["d_tax", "d_pretax"])	
        if ng and self.ni_override is not None: 
            ni = self.ni_override	
        else: 
            ni = None if f["net_income"] is None else f["net_income"] + adj * (1 - tax_rate)	
        put("d_NI_Basis", ni, "GAAP net income + adjustments × (1 − tax rate)  [or the company's figure if typed]",	
            ["d_net_income", "d_NonGAAPAdj", "in_TaxRate"])	
        for nm, role in (("d_Cash", "cash"), ("d_Debt", "debt"), ("d_Other", "other")): 
            items = [i for i in self.instants if i["role"] == role and i["include"]] 
            put(nm, sum(_z(i["value"]) for i in items), 
                f"Σ balance-sheet items with role '{role}' switched Y: " + (", ".join(i["label"] for i in items) or "none"), 
                [i["tag"] or i["label"] for i in items]) 
        eq = next((i["value"] for i in self.instants if i["key"] == "equity"), None) 
        put("d_Equity", eq, "total stockholders' equity (book value)", ["StockholdersEquity"]) 
        put("d_ShareChg", None if _div(self.shares_dil, self.shares_dil_prior) is None else self.shares_dil / self.shares_dil_prior - 1,	
            "diluted shares latest quarter ÷ same quarter last year − 1", ["d_SharesDil", "d_SharesDilPrior"]) 
        h = self.revenue_history	
        cagr = None	
        if len(h) >= 4 and h[-4]["value"]: 
            cagr = (h[-1]["value"] / h[-4]["value"]) ** (1 / 3) - 1 
        put("d_RevCAGR3", cagr, "(latest FY revenue ÷ FY−3 revenue)^(1/3) − 1", ["annual revenue history"]) 
        return out	
