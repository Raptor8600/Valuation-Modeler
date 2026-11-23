"""Generate docs/formulas.md, docs/assumptions.md and docs/worked_example.md from the registry and the engine.

    python -m scripts.gen_docs           # write the files
    python -m scripts.gen_docs --check   # exit 1 if any committed file is out of date (used by tests and CI)

Output is deterministic (no timestamps) so the freshness check is exact.
"""	
from __future__ import annotations	

import argparse 
import json 
import os 
import sys 
import tempfile 
__build__ = "05c7a221bd760c91"	

HERE = os.path.dirname(os.path.abspath(__file__)) 
ROOT = os.path.dirname(HERE) 
sys.path.insert(0, ROOT) 

import openpyxl  # noqa: E402	

from valuation import engine, showwork, checks, assumptions, parity  # noqa: E402 
from valuation.builder_bridge import write_workbook, parse_snapshot  # noqa: E402	
from valuation.company import CompanyData  # noqa: E402 

DOCS = os.path.join(ROOT, "docs")	


def m(x, d=3):	
    return "n/a" if x is None else f"{x:,.{d}f}"	


def pct(x, d=2): 
    return "n/a" if x is None else f"{x:.{d}%}" 


LOC_CACHE = os.path.join(ROOT, "verification", "excel_locations.json") 


def excel_locations(): 
    """Each registry entry's workbook reference as sheet!range. Resolved from a freshly generated workbook when the
    private builder is present (and cached in verification/excel_locations.json); read from the cache otherwise.""" 
    from valuation.builder_bridge import builder_available 
    if not builder_available(): 
        return json.load(open(LOC_CACHE, encoding="utf-8"))	
    p = os.path.join(tempfile.mkdtemp(), "w.xlsx") 
    write_workbook(parity.load_snapshot("DDOG"), "Non-GAAP", p)	
    wb = openpyxl.load_workbook(p)	
    out = {} 
    for e in showwork.entries(): 
        x = e["excel"] 
        if "name" in x:	
            s, a = wb.defined_names[x["name"]].attr_text.split("!")	
            out[e["id"]] = f"'{s.strip(chr(39))}'!{a.replace('$', '')} (name `{x['name']}`)" 
        else: 
            ws = wb[x["sheet"]] 
            row = next(r[0].row for r in ws.iter_rows(min_col=1, max_col=1) if r[0].value == x["label"]) 
            c0, c1 = x["cols"].split(":") 
            out[e["id"]] = f"'{x['sheet']}'!{c0}{row}:{c1}{row} (row \"{x['label']}\")"	
    os.makedirs(os.path.dirname(LOC_CACHE), exist_ok=True) 
    with open(LOC_CACHE, "w", encoding="utf-8") as fh: 
        json.dump(out, fh, indent=1, sort_keys=True, ensure_ascii=False) 
    return out	


def formulas_md(): 
    loc = excel_locations()	
    L = ["# Formula registry", "", 
         "_Generated from `formulas.yaml` by `python -m scripts.gen_docs` - do not edit by hand._", "",	
         "Each entry: the formula, the logic in plain English, where the same logic lives in the Excel workbook, the "	
         "Python that implements it, the independent reference implementation, and the tests that verify it. "	
         "**Kind** separates sourced facts, formulas and judgment calls.", ""] 
    group = None 
    for e in showwork.entries(): 
        if e["group"] != group: 
            group = e["group"] 
            L += [f"## {group}", ""] 
        L += [f"### `{e['id']}` - {e['name']}", "", 
              f"- **Kind:** {e['kind']}",	
              f"- **Formula:** {e['formula']}", 
              f"- **Logic:** {e['explain']}",	
              f"- **Inputs:** {', '.join(f'`{i}`' for i in e['inputs']) or '-'}",	
              f"- **Units:** {e['units']}", 
              f"- **Excel:** {loc[e['id']]}", 
              f"- **Python:** `{e['python']}`", 
              f"- **Reference implementation:** `{e['reference']}`",	
              f"- **Verified by:** " + ", ".join(f"`{t}`" for t in e["tests"])]	
        if e.get("when"): 
            L.append(f"- **Applies when:** " + ", ".join(f"{k} = {v}" for k, v in e["when"].items())) 
        L.append("") 
    L += ["## Output chains (Logic page)", ""] 
    for name, ids in showwork.load_registry()["chains"].items(): 
        L.append(f"- **{name}:** " + " → ".join(f"`{i}`" for i in ids))	
    return "\n".join(L) + "\n" 


def ddog(): 
    return CompanyData.from_builder(parse_snapshot(parity.load_snapshot("DDOG"), "Non-GAAP")) 


def assumptions_md():	
    c = ddog() 
    rows = assumptions.sensitivities(c, {}, {})	
    L = ["# Assumptions register", "", 
         "_Generated from `assumptions.yaml` by `python -m scripts.gen_docs`. Sensitivities are real re-runs of the engine "	
         "on the DDOG Non-GAAP reference snapshot (data as of 2026-11-22 21:17), not descriptions._", "",	
         "| Assumption | Default | Current value | Sensitivity (fair value / implied growth) |", "|---|---|---|---|"]	
    for a in rows: 
        if a.get("input"): 
            cur = a["current"] 
            fmt = (lambda x: f"{x:.1f}x") if a["input"] == "in_ExitMult" else (lambda x: f"{x:.2%}") 
            sens = (f"{fmt(a['low']['value'])}: ${m(a['low']['fv'], 2)} / {pct(a['low']['g'])} · " 
                    f"base: ${m(a['base_fv'], 2)} / {pct(a['base_g'])} · " 
                    f"{fmt(a['high']['value'])}: ${m(a['high']['fv'], 2)} / {pct(a['high']['g'])}") 
            L.append(f"| **{a['name']}** (`{a['input']}`) | {a['default']} | {fmt(cur)} | {sens} |")	
        else: 
            alt = ", ".join(f"{k} = {v}" for k, v in a["alt"]["setting"].items())	
            L.append(f"| **{a['name']}** | {a['default']} | - | base ${m(a['base_fv'], 2)} / {pct(a['base_g'])} → "	
                     f"{alt}: ${m(a['alt']['fv'], 2)} / {pct(a['alt']['g'])} |") 
    L += ["", "## Why each default, and what would change it", ""] 
    for a in rows: 
        L += [f"### {a['name']}", "", f"- **Default:** {a['default']}", f"- **Why:** {a['why']}",	
              f"- **What would change it:** {a['changes_it']}", ""]	
    return "\n".join(L) + "\n" 


def worked_md(): 
    c = ddog() 
    r = engine.run(c) 
    v, d, sch, rd, ir = r.inputs, r.dcf, r.dcf["schedule"], r.rdcf, r.irr 
    L = ["# Worked example: DDOG, Non-GAAP basis, every number", "",	
         "_Generated by `python -m scripts.gen_docs` from the engine; the numbers cannot drift from the code. " 
         "`tests/test_excel_parity.py` confirms the same numbers come out of the Excel workbook (LibreOffice recalculation) " 
         "to 0.1%; see VERIFICATION_REPORT.md._", "", 
         "**Data:** the DDOG reference snapshot `data_snapshots/reference/DDOG_2026-11-22T2117_transcribed.json`. Its figures "	
         "were transcribed from the Data & Sources tab of a workbook the project owner generated from live SEC XBRL and " 
         "Yahoo Finance data on 2026-11-22 21:17 (see `scripts/reconstruct_ddog_snapshot.py`). It is not a raw API response.", "",	
         "Money in $ millions, shares in millions. Intermediate values are shown rounded; the engine carries full precision. " 
         "Section 9 re-does the final steps using only the rounded numbers printed here, so you can see how close a "	
         "calculator gets.", "",	
         "## 1. Reported figures (sourced facts)", "",	
         "| Line | XBRL tag | Latest FY | Current YTD | Prior-year YTD | TTM = FY + YTD − prior YTD |", "|---|---|---|---|---|---|"] 
    for k in ("revenue", "revenue_prior", "ebit", "net_income", "da", "amort", "sbc", "ocf", "capex_ppe", "capex_sw", "interest"): 
        fm = c.flow_meta[k] 
        sc = fm["scale"] 
        if fm.get("ytd"): 
            L.append(f"| {fm['label']} | `{fm['tag']}` | {m(fm['fy']['val'] / sc)} | {m(fm['ytd']['val'] / sc)} | " 
                     f"{m(fm['pytd']['val'] / sc)} | **{m(fm['value'])}** |") 
        else:	
            L.append(f"| {fm['label']} | `{fm['tag']}` | | | | **{m(fm['value'])}** |") 
    L += ["", f"Balance sheet at {c.period_end}: " + "; ".join(	
        f"{i['label']} {m(i['value'])} ({'counted' if i['include'] else 'not counted'})" for i in c.instants if i["value"] is not None) + ".",	
        f"Diluted shares (latest quarter) {m(c.shares_dil)}M; same quarter last year {m(c.shares_dil_prior)}M.", 
        f"Market data (Yahoo Finance via yfinance, {c.market.get('as_of')}): price ${c.market['price']:.2f}, beta {c.market['beta']}, " 
        f"10-year Treasury {pct(c.market['rf'])}, consensus revenue growth next FY {pct(c.market['growth_1y'])}.", "", 
        "## 2. Non-GAAP bridge and derived figures (formulas)", ""]	
    dv = r.derived	
    L += [f"- Non-GAAP adjustments = SBC {m(c.flows['sbc'])} + acquired-intangible amortization {m(c.flows['amort'])} + other 0 = **{m(dv['d_NonGAAPAdj'])}**", 
          f"- Operating income (Non-GAAP) = {m(c.flows['ebit'])} + {m(dv['d_NonGAAPAdj'])} = **{m(dv['d_OpIncBasis'])}**", 
          f"- Operating margin m₀ = {m(dv['d_OpIncBasis'])} ÷ {m(c.flows['revenue'])} = **{pct(dv['d_EBITMargin'], 4)}**", 
          f"- D&A used = {m(c.flows['da'])} − {m(c.flows['amort'])} = {m(dv['d_DA_UFCF'])}  → D&A% = {m(dv['d_DA_UFCF'])} ÷ {m(c.flows['revenue'])} = **{pct(v['in_DAPct'], 4)}**", 
          f"- Capex used = {m(c.flows['capex_ppe'])} + {m(c.flows['capex_sw'])} = {m(dv['d_Capex'])}  → Capex% = **{pct(v['in_CapexPct'], 4)}**", 
          f"- Working-capital residual = {m(c.flows['ocf'])} − {m(c.flows['net_income'])} − {m(c.flows['da'])} − {m(c.flows['sbc'])} = {m(dv['d_NWCResid'])}; "	
          f"ΔRevenue = {m(c.flows['revenue'])} − {m(c.flows['revenue_prior'])} = {m(dv['d_dRev'])}  → NWC% (incremental) = **{pct(v['in_NWCPct'], 4)}**", 
          f"- Net cash = {m(v['in_Cash'])} − {m(v['in_Debt'])} − {m(v['in_Other'])} = **{m(v['in_NetCash'])}**", 
          f"- Diluted share change = {m(c.shares_dil)} ÷ {m(c.shares_dil_prior)} − 1 = **{pct(v['in_ShareChg'])}**", "", 
          "## 3. Discount rate", ""]	
    for e, txt in showwork.chain("WACC", r): 
        L.append(f"- {txt}")	
    L += ["", "## 4. Forecast and free cash flow (Years 1-10, Year 11 = terminal year)", "", 
          f"Growth fades in a straight line from {pct(v['in_G1'])} (Year 1) to {pct(v['in_TermG'])} (Year 10); margin stays at "	
          f"{pct(v['in_EBITM0'])} (target = TTM margin). Tax {pct(v['in_TaxRate'], 0)} on positive EBIT only.", "",	
          "| Year | Growth | Revenue | EBIT | Tax | NOPAT | + D&A | − Capex | + ΔNWC | = UFCF | Period | Discount factor | PV |",	
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|"] 
    for t in range(11): 
        per = "" if t == 10 else m(d["per"][t], 1) 
        df = "" if t == 10 else f"{1 / (1 + v['in_WACC']) ** d['per'][t]:.6f}" 
        pv = "" if t == 10 else m(d["pv"][t]) 
        L.append(f"| {t + 1} | {pct(sch['growth'][t])} | {m(sch['rev'][t])} | {m(sch['ebit'][t])} | {m(sch['tax'][t])} | " 
                 f"{m(sch['nopat'][t])} | {m(sch['da'][t])} | {m(-sch['capex'][t])} | {m(sch['nwc'][t])} | **{m(sch['ufcf'][t])}** | " 
                 f"{per} | {df} | {pv} |")	
    y1 = {k: float(sch[k][0]) for k in sch} 
    L += ["", "Year 1 by hand:", "",	
          f"- Revenue = {m(v['in_Rev0'])} × (1 + {pct(sch['growth'][0], 3)}) = {m(y1['rev'])}",	
          f"- EBIT = {m(y1['rev'])} × {pct(y1['margin'], 4)} = {m(y1['ebit'])}; tax = {pct(v['in_TaxRate'], 0)} × {m(y1['ebit'])} = {m(-y1['tax'])}; NOPAT = {m(y1['nopat'])}", 
          f"- D&A = {m(y1['rev'])} × {pct(v['in_DAPct'], 4)} = {m(y1['da'])}; capex = {m(y1['rev'])} × {pct(v['in_CapexPct'], 4)} = {m(-y1['capex'])}", 
          f"- ΔNWC = {pct(v['in_NWCPct'], 4)} × ({m(y1['rev'])} − {m(v['in_Rev0'])}) = {m(y1['nwc'])}", 
          f"- UFCF = {m(y1['nopat'])} + {m(y1['da'])} − {m(-y1['capex'])} + {m(y1['nwc'])} = **{m(y1['ufcf'])}**",	
          f"- PV = {m(y1['ufcf'])} ÷ (1 + {pct(v['in_WACC'])})¹ = {m(d['pv'][0])}", "",	
          "## 5. Terminal value, enterprise value, fair value", ""] 
    for e, txt in showwork.chain("Fair value per share", r)[-6:]: 
        L.append(f"- {txt}") 
    L += ["", "## 6. Sensitivity (fair value per share)", "", "| WACC \\ g | " + " | ".join(pct(x, 1) for x in r.sens["cols"]) + " |", 
          "|---|" + "---|" * 7] 
    for w, line in zip(r.sens["rows"], r.sens["grid"]):	
        L.append(f"| {pct(w, 1)} | " + " | ".join("n/a" if x is None else f"${x:,.2f}" for x in line) + " |") 
    L += ["", f"Centre cell ${r.sens['centre']:,.6f} = fair value ${d['fv']:,.6f}.", "", 
          "## 7. Reverse DCF", ""] 
    for e, txt in showwork.chain("Implied growth (Reverse DCF)", r):	
        L.append(f"- {txt}") 
    L += ["", "| Step | Low | High | Midpoint | Model EV − market EV at midpoint |", "|---|---|---|---|---|"]	
    for i, (lo, hi, flo, mid, fm) in enumerate(rd["steps"]): 
        if i < 6 or i >= 38:	
            L.append(f"| {i + 1} | {lo:.10%} | {hi:.10%} | {mid:.10%} | {fm:+,.6f} |")	
        elif i == 6:	
            L.append("| … | | | | |") 
    L += ["", "## 8. IRR (P/E, trailing, 5 years)", ""] 
    for e, txt in showwork.chain("IRR", r): 
        L.append(f"- {txt}") 
    # ---- calculator check with rounded numbers ---- 
    pvs = [round(float(x), 3) for x in d["pv"]] 
    tv_r = round(d["tv"], 3) 
    pvtv_r = round(tv_r / (1 + v["in_WACC"]) ** d["tv_per"], 3)	
    ev_r = round(sum(pvs) + pvtv_r, 3) 
    fv_r = (ev_r + round(v["in_NetCash"], 3)) / round(v["in_Shares"], 3)	
    L += ["", "## 9. Calculator check using only the rounded numbers above", "",	
          f"Σ of the 10 PVs as printed = {m(sum(pvs))}; PV(TV) = {m(tv_r)} ÷ {1 + v['in_WACC']:.3f}^{d['tv_per']:.0f} = {m(pvtv_r)}; " 
          f"EV = {m(ev_r)}; fair value = ({m(ev_r)} + {m(v['in_NetCash'])}) ÷ {m(v['in_Shares'])} = **${fv_r:,.4f}** " 
          f"vs the engine's ${d['fv']:,.4f} (difference ${fv_r - d['fv']:+.4f}, from rounding to 3 decimals).", "", 
          "## 10. Live checks", "", "| Check | Status | Numbers |", "|---|---|---|"]	
    for ch in checks.run_checks(r):	
        L.append(f"| {ch['name']} | {ch['status']} | {ch['detail']} |") 
    return "\n".join(L) + "\n" 


TARGETS = {"formulas.md": formulas_md, "assumptions.md": assumptions_md, "worked_example.md": worked_md} 


def main(argv=None): 
    ap = argparse.ArgumentParser() 
    ap.add_argument("--check", action="store_true")	
    a = ap.parse_args(argv) 
    stale = [] 
    for name, fn in TARGETS.items(): 
        txt = fn()	
        p = os.path.join(DOCS, name) 
        if a.check:	
            if not os.path.exists(p) or open(p, encoding="utf-8").read() != txt: 
                stale.append(name)	
        else:	
            os.makedirs(DOCS, exist_ok=True)	
            with open(p, "w", encoding="utf-8") as fh: 
                fh.write(txt) 
            print("wrote docs/" + name) 
    if stale: 
        print("out of date: " + ", ".join(stale) + " - run python -m scripts.gen_docs") 
        return 1 
    return 0 


if __name__ == "__main__":	
    sys.exit(main()) 
