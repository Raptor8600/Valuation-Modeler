"""Values-only Excel export: the results of one run, with no formulas.

Every cell holds a number or text - nothing recalculates. The 'Calculation steps' sheet spells out each formula with
the run's numbers substituted, so the file stays checkable without being a reusable model.
"""	
from __future__ import annotations	

import io 

from openpyxl import Workbook 
from openpyxl.styles import Alignment, Font, PatternFill 
from openpyxl.utils import get_column_letter 

from . import checks, showwork 
from .app_model import FIELDS, IRR_FIELDS	
from .provenance import OVERRIDE 
__build__ = "0ac0fd8b500e3367" 

HDR = PatternFill("solid", fgColor="1F497D") 
SUB = PatternFill("solid", fgColor="DCE6F1")	
NOTE = ("Values only - this file does not recalculate. It records one run of Valuation Modeler; change the inputs in the " 
        "app and download again for a new version. Educational, not investment advice.")	
FMT = {"pct": "0.00%", "money": "#,##0.0", "px": "$#,##0.00", "shares": "#,##0.000", "num": "0.000", "mult": "0.0x", 
       "years": "0"}	


SETTING_LABELS = {	
    "in_Basis": "Accounting basis", "in_TVMethod": "Terminal value method", "in_WACCMode": "WACC mode",	
    "in_NWCMethod": "Working-capital method", "in_Timing": "Discounting convention", "in_CashRetain": "Cash between now and future dates", 
    "in_ExitMetric": "Exit multiple metric", "in_LossTax": "Tax on negative operating income", "fc_Mode": "Forecast mode", 
    "fc_Scenario": "Scenario", "rd_MarginSrc": "Reverse DCF margin path", "irr_Mult": "IRR valuation multiple", 
    "irr_Basis": "IRR timing basis", "irr_GSrc": "IRR metric growth source", "irr_Cash": "IRR net cash at exit", 
} 


class _Sheet: 
    def __init__(self, wb, title, first=False): 
        self.ws = wb.active if first else wb.create_sheet()	
        self.ws.title = title 
        self.r = 1	

    def title(self, text, sub=None):	
        c = self.ws.cell(self.r, 1, text) 
        c.font = Font(bold=True, size=14) 
        self.r += 1 
        if sub:	
            c = self.ws.cell(self.r, 1, sub)	
            c.font = Font(italic=True, color="666666") 
            self.r += 1 
        self.r += 1 

    def header(self, *cols): 
        for j, t in enumerate(cols, 1): 
            c = self.ws.cell(self.r, j, t)	
            c.font = Font(bold=True, color="FFFFFF") 
            c.fill = HDR 
            c.alignment = Alignment(wrap_text=True, vertical="center") 
        self.r += 1	

    def section(self, text): 
        self.r += 1	
        c = self.ws.cell(self.r, 1, text) 
        c.font = Font(bold=True)	
        c.fill = SUB	
        self.r += 1	

    def row(self, *vals, fmt=None, bold=False): 
        for j, v in enumerate(vals, 1): 
            if v is not None and not isinstance(v, (int, float, str)): 
                v = float(v) 
            c = self.ws.cell(self.r, j, v) 
            if isinstance(v, str) and v.startswith("="): 
                c.data_type = "s"           # text that starts with "=" must never become a formula 
            if isinstance(v, (int, float)) and fmt:	
                c.number_format = fmt[j - 1] if isinstance(fmt, (list, tuple)) else fmt 
            if bold:	
                c.font = Font(bold=True)	
        self.r += 1 

    def widths(self, *w): 
        for j, x in enumerate(w, 1): 
            self.ws.column_dimensions[get_column_letter(j)].width = x	


def scenario_block(sh, res):	
    """Bear / Base / Bull / weighted / current price - placed at the top of Summary and on the DCF sheet.""" 
    sc = res.scen 
    if sc is None or res.dcf is None: 
        return 
    px, H = res.inputs["in_Price"], sc["H"] 
    sh.section("Bear / Base / Bull vs today's price")	
    sh.header("Case", "Value today (DCF)", "vs price", f"Price target @ {H:g} yrs", "Return to target /yr", "10-yr revenue CAGR", "Weight") 
    f = ["$#,##0.00", "+0.0%;-0.0%", "$#,##0.00", "0.0%", "0.0%", "0%"] 

    def ret(pt): 
        return None if pt is None or pt <= 0 else (pt / px) ** (1 / H) - 1	
    for name in ("Bear", "Base", "Bull"): 
        c = sc["cases"][name]	
        sh.row(name, _n(c["v0"]), None if c["v0"] is None else c["v0"] / px - 1, _n(c["pt"]), ret(c["pt"]), c["cagr"], c["weight"], 
               fmt=[None] + f, bold=False)	
    sh.row("Probability-weighted", _n(sc["v0"]), None if sc["v0"] is None else sc["v0"] / px - 1, _n(sc["pt"]), ret(sc["pt"]),	
           None, sc["weight_sum"], fmt=[None] + f, bold=True)	
    sh.row("Current share price / market-implied growth", px, None, px, None, 
           res.rdcf["g"] if res.rdcf["g"] is not None else res.rdcf["solution_text"], None, fmt=[None] + f, bold=True) 


def _n(x): 
    return None if x is None else float(x) 


def build(res, snapshot_meta: dict | None = None) -> bytes: 
    c, v, s = res.company, res.inputs, res.settings 
    wb = Workbook() 
    unit_note = "Money in $ millions, shares in millions, per-share values in $."	

    # ---------------------------------------------------------------- Summary 
    sh = _Sheet(wb, "Summary", first=True)	
    sh.title(f"{c.name} ({c.ticker}) - {s['in_Basis']} basis", NOTE)	
    for k, val in [("Latest filing period", c.period_end), ("Data as of", c.fetched_at), 
                   ("Data", "SYNTHETIC (made-up numbers)" if c.synthetic else (snapshot_meta or {}).get("kind", "live")), 
                   ("Units", unit_note)]: 
        sh.row(k, val)	
    scenario_block(sh, res)	
    sh.section("Settings") 
    for k, val in s.items(): 
        sh.row(SETTING_LABELS.get(k, k), val) 
    if res.dcf is None: 
        sh.section("Not computable - missing inputs") 
        for m in res.missing:	
            sh.row(m) 
    else: 
        d, rd, ir = res.dcf, res.rdcf, res.irr 
        sh.section("Results")	
        rows = [("Fair value per share", d["fv"], "$#,##0.00"), ("Share price", v["in_Price"], "$#,##0.00"), 
                ("Upside / (downside)", d["upside"], "0.0%"), ("Enterprise value ($M)", d["ev"], "#,##0.0"),	
                ("Equity value ($M)", d["equity"], "#,##0.0"), ("Active WACC", v["in_WACC"], "0.00%"), 
                ("Terminal value share of EV", d["tv_share"], "0.0%"),	
                ("Implied 10-year revenue growth (Reverse DCF)", rd["g"] if rd["g"] is not None else rd["solution_text"], "0.00%"),	
                ("Reverse DCF status", rd["status"], None),	
                (f"IRR ({s['irr_Mult']}, {ir['H']} years)", ir["irr"] if ir["irr"] is not None else ir["irr_note"], "0.00%"), 
                ("Exit share price", ir["exit_price"], "$#,##0.00")] 
        for k, val, f in rows: 
            sh.row(k, _n(val) if isinstance(val, (int, float)) or val is None else val, fmt=[None, f]) 
        sh.section("Checks") 
        for ch in checks.run_checks(res): 
            sh.row(ch["status"], ch["name"], ch["detail"]) 
    sh.widths(44, 22, 110)	

    # ---------------------------------------------------------------- Inputs 
    sh = _Sheet(wb, "Inputs")	
    sh.title("Inputs used", "Auto value = what was pulled or calculated; Used = what this run used. " + unit_note)	
    sh.header("Input", "Name", "Auto value", "Used", "Overridden?", "Source type", "Source detail", "Link") 
    for name, label, kind, _ in FIELDS + [(n, l, k, "") for n, l, k in IRR_FIELDS]: 
        src = res.sources.get(name) 
        used = v.get(name)	
        auto = src.auto_value if (src is not None and src.kind == OVERRIDE) else used	
        if src is None: 
            continue 
        detail = " · ".join(x for x in (src.provider, src.field, f"period {src.period_end}" if src.period_end else "", 
                                        f"fetched {src.fetched_at}" if src.fetched_at else "", src.formula, src.rationale, 
                                        src.note) if x) 
        sh.row(label, name, _n(auto), _n(used), "YES" if src.kind == OVERRIDE else "", src.kind, detail, src.url or "",	
               fmt=[None, None, FMT[kind], FMT[kind]]) 
    sh.section("Reported figures behind the defaults ($M, trailing twelve months)") 
    sh.header("Line", "XBRL tag", "TTM value", "How built", "Filing") 
    for k, m in c.flow_meta.items():	
        fs = c.flow_source(k) 
        sh.row(m["label"], m.get("tag") or "-", _n(m["value"]), fs.note, fs.url, fmt=[None, None, "#,##0.000"])	
    sh.widths(38, 16, 14, 14, 12, 16, 90, 60) 

    if res.dcf is not None:	
        d, sch = res.dcf, res.dcf["schedule"]	
        # ------------------------------------------------------------ DCF	
        sh = _Sheet(wb, "DCF") 
        sh.title("Discounted cash flow", unit_note) 
        sh.header("Line", *[f"Year {t}" for t in range(1, 11)], "Terminal (Yr 11)") 
        lines = [("Revenue growth", "growth", "0.00%"), ("Revenue", "rev", "#,##0.0"), ("Operating margin", "margin", "0.00%"), 
                 ("EBIT", "ebit", "#,##0.0"), ("Taxes", "tax", "#,##0.0"), ("NOPAT", "nopat", "#,##0.0"), 
                 ("D&A", "da", "#,##0.0"), ("Capex", "capex", "#,##0.0"), ("Change in working capital", "nwc", "#,##0.0"), 
                 ("Unlevered free cash flow", "ufcf", "#,##0.0"), ("Memo: EBITDA", "ebitda", "#,##0.0")] 
        for lab, k, f in lines:	
            sh.row(lab, *[float(x) for x in sch[k]], fmt=[None] + [f] * 11, bold=(k == "ufcf")) 
        sh.row("Discount period (years)", *[float(x) for x in d["per"]], fmt="0.0")	
        sh.row("Present value of UFCF", *[float(x) for x in d["pv"]], fmt=[None] + ["#,##0.0"] * 10)	
        scenario_block(sh, res) 
        sh.section("Enterprise value to value per share") 
        for lab, val, f in [("Sum of PV, Years 1-10", d["sum_pv"], "#,##0.0"), ("Terminal value", d["tv"], "#,##0.0"), 
                            ("Terminal value discount period", d["tv_per"], "0.0"), ("PV of terminal value", d["pv_tv"], "#,##0.0"),	
                            ("Enterprise value", d["ev"], "#,##0.0"), ("+ Cash & investments", v["in_Cash"], "#,##0.0"),	
                            ("- Debt", v["in_Debt"], "#,##0.0"), ("- Other claims", v["in_Other"], "#,##0.0"), 
                            ("Equity value", d["equity"], "#,##0.0"), ("Diluted shares (M)", v["in_Shares"], "#,##0.000"), 
                            ("Fair value per share", d["fv"], "$#,##0.00"), 
                            ("Implied exit EV/EBITDA", d["imp_mult"], "0.0x"), ("Implied perpetual growth", d["imp_g"], "0.00%")]: 
            sh.row(lab, _n(val), fmt=[None, f], bold=lab == "Fair value per share") 
        sh.section("Value over time (if the forecast is delivered)")	
        sh.header("Year", "EV", "Net cash", "Equity", "Shares (M)", "Price per share", "Annual return from today's price") 
        for x in res.vot: 
            if x: 
                sh.row(x["t"], x["ev"], x["net_cash"], x["equity"], x["shares"], x["price"], x["ann_return"],	
                       fmt=["0", "#,##0.0", "#,##0.0", "#,##0.0", "#,##0.00", "$#,##0.00", "0.0%"]) 
        sn = res.sens	
        sh.section(f"Sensitivity: fair value per share (rows WACC, columns {'terminal growth' if sn['perp'] else 'exit multiple'})") 
        sh.row("", *[float(x) for x in sn["cols"]], fmt=[None] + (["0.0%"] if sn["perp"] else ["0.0x"]) * 7, bold=True)	
        for w, line in zip(sn["rows"], sn["grid"]):	
            sh.row(float(w), *[_n(x) for x in line], fmt=["0.0%"] + ["$#,##0.00"] * 7)	
        sh.widths(34, *[13] * 11) 

        # ------------------------------------------------------------ Reverse DCF 
        rd = res.rdcf 
        sh = _Sheet(wb, "Reverse DCF") 
        sh.title("Reverse DCF - growth implied by today's price", unit_note) 
        for lab, val, f in [("Market enterprise value", rd["target"], "#,##0.0"), 
                            ("Implied 10-year revenue growth", rd["g"] if rd["g"] is not None else rd["solution_text"], "0.00%"), 
                            ("Your forecast's 10-year revenue CAGR", rd["forecast_cagr"], "0.00%"),	
                            ("Gap (implied - forecast)", rd["gap"], "0.00%"), ("Model EV at implied growth", rd["ev"], "#,##0.0"), 
                            ("Tie-out (model - market, $M)", rd["tieout"], "0.000000"), ("Status", rd["status"], None)]:	
            sh.row(lab, val if isinstance(val, str) else _n(val), fmt=[None, f])	
        if rd["proof"]: 
            p = rd["proof"]["schedule"] 
            sh.section("Proof schedule at the implied growth") 
            sh.header("Line", *[f"Year {t}" for t in range(1, 11)], "Terminal (Yr 11)")	
            for lab, k, f in [("Revenue", "rev", "#,##0.0"), ("Operating margin", "margin", "0.00%"),	
                              ("NOPAT", "nopat", "#,##0.0"), ("UFCF", "ufcf", "#,##0.0")]: 
                sh.row(lab, *[float(x) for x in p[k]], fmt=[None] + [f] * 11) 
            sh.section("Implied share price over time") 
            sh.header("Year", "Price per share", "Annual return") 
            for x in rd["path"]: 
                sh.row(x["t"], x["price"], x["ann_return"], fmt=["0", "$#,##0.00", "0.0%"])	
        sh.widths(38, *[13] * 11) 

        # ------------------------------------------------------------ IRR 
        ir = res.irr 
        sh = _Sheet(wb, "IRR")	
        sh.title(f"IRR - {s['irr_Mult']} ({s['irr_Basis']}), {ir['H']}-year hold", "Per-share figures in $.") 
        for lab, val, f in [("Entry multiple", ir["entry"], "0.00"), ("Exit multiple", ir["exit"], "0.00"),	
                            ("Exit share price", ir["exit_price"], "$#,##0.00"), 
                            ("IRR", ir["irr"] if ir["irr"] is not None else ir["irr_note"], "0.00%"),	
                            ("Price-only annual growth", ir["price_cagr"], "0.00%"),	
                            ("Total return multiple", ir["total_multiple"], "0.00x")]:	
            sh.row(lab, val if isinstance(val, str) else _n(val), fmt=[None, f]) 
        sh.section("Projections") 
        sh.header("Year", "Metric total ($M)", "Shares (M)", "Metric per share", "Dividend per share", "Net cash per share", 
                  "Price if sold", "Cash flow for IRR") 
        for r in ir["rows"]: 
            sh.row(r["t"], _n(r["metric_total"]), r["shares"], _n(r["metric_ps"]), r["dps"], r["nc_ps"], _n(r["exit_price"]), 
                   _n(r["cash_flow"]), fmt=["0", "#,##0.0", "#,##0.00", "#,##0.00", "#,##0.00", "#,##0.00", "$#,##0.00", "#,##0.00"]) 
        sn = ir["sens"]	
        sh.section("Sensitivity: annual return (rows entry multiple, columns exit multiple)") 
        sh.row("", *[_n(x) for x in sn["cols"]], fmt="0.00", bold=True)	
        for a, line in zip(sn["rows"], sn["grid"]):	
            sh.row(_n(a), *[_n(x) for x in line], fmt=["0.00"] + ["0.0%"] * 7) 
        sh.widths(22, *[16] * 8) 

        # ------------------------------------------------------------ Calculation steps 
        sh = _Sheet(wb, "Calculation steps")	
        sh.title("How each result was calculated", "Formula, then the same formula with this run's numbers.")	
        sh.header("Result", "Step", "Formula", "With this run's numbers") 
        for chain_name in showwork.load_registry()["chains"]: 
            for e, txt in showwork.chain(chain_name, res): 
                sh.row(chain_name, e["name"], e["formula"], txt) 
        for row in sh.ws.iter_rows(min_row=4): 
            for cell in row:	
                cell.alignment = Alignment(wrap_text=True, vertical="top") 
        sh.widths(26, 34, 70, 90) 

    for ws in wb.worksheets: 
        ws.freeze_panes = None	
        ws.sheet_view.showGridLines = True 
    buf = io.BytesIO()	
    wb.save(buf) 
    return buf.getvalue()	


def filename(res) -> str:	
    return f"{res.company.ticker}_{res.settings['in_Basis'].replace('-', '')}_{res.company.period_end}_values.xlsx"	
