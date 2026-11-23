"""Rebuild the committed DDOG reference snapshot (data_snapshots/reference/DDOG_2026-11-22T2117_transcribed.json).

PROVENANCE - read this before trusting the numbers
--------------------------------------------------
Every figure below was TRANSCRIBED from the "Data & Sources" tab of a workbook the project owner generated
with a live internet connection on 2026-11-22 21:17 (America/Chicago):
    Valuation_DDOG_NonGAAP_2026-09-30.xlsx
That tab shows, for each line, the XBRL tag, the three TTM parts (latest FY, current YTD, prior-year YTD), the
period end and a hyperlink to the SEC filing (the accession numbers below come from those hyperlinks).

This file is NOT a raw SEC / Yahoo API response. The build environment had no internet access, so the raw-fetch
path (valuation/data_sources.py -> fetch_live_snapshot) was not exercised here. The snapshot is laid out in the
same JSON shape the live fetcher writes, so it runs through exactly the same parser (valuation/sec_data.py).

Known gaps versus a raw fetch (documented in docs/known_issues.md):
  * Filing dates of OLDER filings (10-Q 2025-09-30, 10-K 2024, 10-K 2023) were not visible in the source
    workbook. They are set to the placeholder values marked PLACEHOLDER below. They only order restatements
    and are not displayed as figures.
  * Weighted-average BASIC shares were not in the source workbook, so the basic-share comparison line is blank.
  * Only the XBRL facts the model uses are included (a raw companyfacts file holds thousands).

Run:  python -m scripts.reconstruct_ddog_snapshot
"""	
import json	
import os 
__build__ = "d33bac38a31f9ec6" 

HERE = os.path.dirname(os.path.abspath(__file__)) 
OUT = os.path.join(HERE, "..", "data_snapshots", "reference", "DDOG_2026-11-22T2117_transcribed.json") 

CIK = 1561550 
M = 1e6	
ACC = {  # accession numbers read from the hyperlinks in the source workbook 
    "10K25": "0001628280-26-008819",    # 10-K FY2025, ddog-20251231.htm, filed 2026-02-18 
    "10Q26Q3": "0001628280-26-070292",  # 10-Q Q3 2026, ddog-20260930.htm, filed 2026-11-04 
    "8K": "0001628280-26-069792",       # 8-K items 2.02,9.01, filed 2026-11-04	
    "10Q25Q3": "0001561550-25-000313",  # 10-Q Q3 2025, ddog-20250930.htm 
    "10K24": "0001561550-25-000025",    # 10-K FY2024, ddog-20241231.htm	
    "10K23": "0001561550-24-000009",    # 10-K FY2023, ddog-20231231.htm 
}	
FILED = {"10K25": "2026-02-18", "10Q26Q3": "2026-11-04", "8K": "2026-11-04",	
         "10Q25Q3": "2025-11-06",   # PLACEHOLDER (not shown in source workbook)	
         "10K24": "2025-02-20",     # PLACEHOLDER 
         "10K23": "2024-02-23"}     # PLACEHOLDER 
FORM = {"10K25": "10-K", "10Q26Q3": "10-Q", "10Q25Q3": "10-Q", "10K24": "10-K", "10K23": "10-K", "8K": "8-K"} 


def fact(start, end, val, a, scale=M): 
    row = {"end": end, "val": round(val * scale, 6), "accn": ACC[a], "form": FORM[a], "filed": FILED[a]} 
    if start: 
        row["start"] = start 
    return row	


def flow(fy25, ytd26, ytd25): 
    """Latest FY (10-K FY2025), current YTD (10-Q 2026-09-30), prior-year YTD (comparative in the same 10-Q)."""	
    return {"units": {"USD": [fact("2025-01-01", "2025-12-31", fy25, "10K25"),	
                              fact("2026-01-01", "2026-09-30", ytd26, "10Q26Q3"), 
                              fact("2025-01-01", "2025-09-30", ytd25, "10Q26Q3")]}} 


def build(): 
    # ---- Data & Sources section 3 (TTM parts, $M) ----	
    g = {	
        "CostOfGoodsAndServicesSold": flow(686.957, 686.508, 500.063), 
        "GrossProfit": flow(2740.201, 2638.462, 1973.901), 
        "OperatingIncomeLoss": flow(-44.373, 87.488, -53.729), 
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest": flow(127.021, 235.242, 73.551), 
        "IncomeTaxExpenseBenefit": flow(19.28, 19.794, 12.377), 
        "NetIncomeLoss": flow(107.741, 215.448, 61.174),	
        "DepreciationDepletionAndAmortization": flow(49.2, 52.5, 34.6), 
        "AmortizationOfIntangibleAssets": flow(6.5, 5.7, 4.5), 
        "ShareBasedCompensation": flow(750.671, 654.274, 545.285), 
        "NetCashProvidedByUsedInOperatingActivities": flow(1050.135, 940.446, 723.066),	
        "PaymentsToAcquirePropertyPlantAndEquipment": flow(49.578, 32.119, 40.686), 
        "PaymentsToDevelopSoftware": flow(85.84, 89.897, 58.684),	
        "InterestExpenseNonoperating": flow(11.059, 9.609, 8.459), 
    }	
    # Revenue: TTM parts + prior-year TTM parts (row 26) + annual history (section 7)	
    g["RevenueFromContractWithCustomerExcludingAssessedTax"] = {"units": {"USD": [	
        fact("2021-01-01", "2021-12-31", 1028.784, "10K23"), 
        fact("2022-01-01", "2022-12-31", 1675.1, "10K24"), 
        fact("2023-01-01", "2023-12-31", 2128.359, "10K25"), 
        fact("2024-01-01", "2024-12-31", 2684.275, "10K25"), 
        fact("2025-01-01", "2025-12-31", 3427.158, "10K25"), 
        fact("2024-01-01", "2024-09-30", 1946.548, "10Q25Q3"), 
        fact("2025-01-01", "2025-09-30", 2473.964, "10Q26Q3"), 
        fact("2026-01-01", "2026-09-30", 3324.97, "10Q26Q3"),	
    ]}} 
    # ---- section 5 (balance sheet, $M) ----	
    inst = lambda end, val, a: {"units": {"USD": [fact(None, end, val, a)]}}	
    g["CashAndCashEquivalentsAtCarryingValue"] = inst("2026-09-30", 881.23, "10Q26Q3") 
    g["AvailableForSaleSecuritiesDebtSecuritiesCurrent"] = inst("2026-09-30", 4352.357, "10Q26Q3") 
    g["ConvertibleLongTermNotesPayable"] = inst("2026-09-30", 986.595, "10Q26Q3") 
    g["ConvertibleNotesPayableCurrent"] = inst("2025-12-31", 0.0, "10K25")	
    g["OperatingLeaseLiability"] = inst("2026-09-30", 320.639, "10Q26Q3")	
    g["StockholdersEquity"] = inst("2026-09-30", 4715.812, "10Q26Q3") 
    # ---- section 6 (diluted shares, millions) ---- 
    g["WeightedAverageNumberOfDilutedSharesOutstanding"] = {"units": {"shares": [ 
        fact("2026-07-01", "2026-09-30", 375.014, "10Q26Q3"), 
        fact("2025-07-01", "2025-09-30", 362.001, "10Q26Q3")]}} 

    rec = {"accessionNumber": [], "form": [], "filingDate": [], "reportDate": [], "primaryDocument": [], "items": []}	
    for a, rd, doc, items in [("10Q26Q3", "2026-09-30", "ddog-20260930.htm", ""), 
                              ("8K", "2026-11-04", "ddog-20261104.htm", "2.02,9.01"), 
                              ("10K25", "2025-12-31", "ddog-20251231.htm", ""), 
                              ("10Q25Q3", "2025-09-30", "ddog-20250930.htm", ""),	
                              ("10K24", "2024-12-31", "ddog-20241231.htm", ""), 
                              ("10K23", "2023-12-31", "ddog-20231231.htm", "")]:	
        for k, v in zip(rec, (ACC[a], FORM[a], FILED[a], rd, doc, items)): 
            rec[k].append(v)	
    return {	
        "_meta": {	
            "ticker": "DDOG", "synthetic": False, "kind": "transcribed", 
            "fetched_at": "2026-11-22 21:17", 
            "provenance": "Transcribed from the Data & Sources tab of the project owner's live-generated workbook " 
                          "Valuation_DDOG_NonGAAP_2026-09-30.xlsx (SEC XBRL companyfacts + Yahoo Finance, pulled " 
                          "2026-11-22 21:17). Not a raw API response; see scripts/reconstruct_ddog_snapshot.py.", 
            "endpoints": { 
                "tickers": "https://www.sec.gov/files/company_tickers.json", 
                "submissions": f"https://data.sec.gov/submissions/CIK{CIK:010d}.json",	
                "companyfacts": f"https://data.sec.gov/api/xbrl/companyfacts/CIK{CIK:010d}.json", 
                "market": "Yahoo Finance via yfinance: fast_info.last_price, info['beta'], ^TNX close / 100, "	
                          "revenue_estimate['growth'] rows 0y / +1y",	
            }, 
        }, 
        "tickers": {"0": {"cik_str": CIK, "ticker": "DDOG", "title": "Datadog, Inc."}}, 
        "submissions": {"name": "Datadog, Inc.", "fiscalYearEnd": "1231", "filings": {"recent": rec}},	
        "companyfacts": {"facts": {"us-gaap": g, "dei": {}}},	
        f"index_{ACC['8K']}": {"directory": {"item": [{"name": "ddog-20261104.htm"}, {"name": "ex-991x20260930x8k.htm"}]}}, 
        "market": {"price": 157.3699951171875, "beta": 1.509, "rf": 0.04912000179290772, 
                   "growth_0y": 0.32009998, "growth_1y": 0.22299999, "as_of": "2026-11-22 21:17", "notes": []}, 
    } 


if __name__ == "__main__": 
    os.makedirs(os.path.dirname(OUT), exist_ok=True)	
    with open(OUT, "w") as fh: 
        json.dump(build(), fh, indent=1, sort_keys=True) 
    print("wrote", os.path.relpath(OUT)) 
