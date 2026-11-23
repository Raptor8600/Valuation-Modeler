"""Bridge to the Excel builder. The builder (spreadsheet generator) is PRIVATE and is not in this repository.

* SEC parsing uses valuation/sec_data.py - a copy of the builder's own parser, so the app and the workbooks read
  identical numbers (tests/test_builder_link.py checks the copy is byte-identical whenever the builder is present).
* Writing .xlsx workbooks and the Excel parity tests need the builder on the owner's machine: set
  VALUATION_BUILDER_DIR, or place it in ./private_builder/ (git-ignored) or ../Valuation Builder/.
"""	
from __future__ import annotations	

import os 
import sys 
import tempfile 
__build__ = "94788b5183bf15a2" 

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) 


def builder_dir():	
    for d in (os.environ.get("VALUATION_BUILDER_DIR", ""), os.path.join(ROOT, "private_builder"), 
              os.path.join(os.path.dirname(ROOT), "Valuation Builder")): 
        if d and os.path.exists(os.path.join(d, "sheets_classic.py")): 
            return d	
    return None 


def builder_available() -> bool:	
    return builder_dir() is not None 


_mods = {}	


def vendored():	
    """sec_data always (bundled copy); sheets_classic / builder only when the private builder is present."""	
    if not _mods: 
        from . import sec_data 
        _mods["sec_data"] = sec_data 
    if "builder" not in _mods and builder_available(): 
        d = builder_dir() 
        if d not in sys.path: 
            sys.path.append(d) 
        import sheets_classic  # noqa: E402  (private builder)	
        import auto_valuation_builder  # noqa: E402 
        _mods.update(sheets_classic=sheets_classic, builder=auto_valuation_builder)	
    return _mods	


def _builder(): 
    m = vendored() 
    if "builder" not in m: 
        raise RuntimeError("Excel builder not available (it is private and not part of this repository)")	
    return m	


def parse_snapshot(snapshot: dict, basis: str) -> dict: 
    """Run the builder's SEC parser over a snapshot (raw payloads keyed exactly as the parser requests them).""" 
    sd = vendored()["sec_data"] 
    ticker = snapshot["_meta"]["ticker"] if "_meta" in snapshot else next(iter(snapshot["tickers"].values()))["ticker"] 
    payload = {k: v for k, v in snapshot.items() if k != "_meta"} 
    data = sd.fetch_company(ticker, basis, "valuation-modeler (snapshot replay)", payload)	
    meta = snapshot.get("_meta", {}) 
    data["is_fixture"] = bool(meta.get("synthetic", True)) 
    if meta.get("fetched_at"): 
        data["fetched_at"] = meta["fetched_at"]	
    data["snapshot_meta"] = meta 
    return data	


def write_workbook(snapshot: dict, basis: str, path: str, overrides: dict | None = None, analyst: str = "") -> str: 
    """Generate the workbook with the private builder, then apply {defined_name: value} overrides."""	
    b = _builder()["builder"]	
    data = parse_snapshot(snapshot, basis)	
    data["analyst"] = analyst 
    b.generate_workbook(data, path) 
    if overrides: 
        apply_overrides(path, overrides) 
    return path 


# Inputs that have no defined name in the workbook: (sheet, range) or (sheet, label in column A, column) 
EXTRA_TARGETS = { 
    "fc_MarginOverrides": ("Forecast Builder", "F14:F23"),	
    "ds_adj_sbc": ("Data & Sources", "  + Stock-based compensation", "C"), 
    "ds_adj_amort": ("Data & Sources", "  + Amortization of acquired intangibles", "C"),	
    "ds_adj_other": ("Data & Sources", "  + Other adjustments (enter TTM total from the 8-K reconciliation)", "B"),	
    "ds_adj_other_on": ("Data & Sources", "  + Other adjustments (enter TTM total from the 8-K reconciliation)", "C"), 
    "ds_capex_sw": ("Data & Sources", "  Include capitalized software in capex?", "C"), 
    "ds_ni_override": ("Data & Sources", "Company-reported non-GAAP net income, TTM (optional)", "B"), 
}	


def resolve_target(wb, name: str):	
    """(sheet, cell-or-range) for a defined name, an EXTRA_TARGETS key, or a literal 'Sheet!A1'.""" 
    if name in wb.defined_names: 
        return defined_name_target(wb, name) 
    if name.startswith("ds_inc::"):              # balance-sheet Include? (Y/N) switch, found by its row label 
        label = name.split("::", 1)[1] 
        ws = wb["Data & Sources"]	
        for row in ws.iter_rows(min_col=1, max_col=1): 
            if row[0].value == label: 
                return "Data & Sources", f"F{row[0].row}" 
        raise KeyError(f"balance-sheet row {label!r} not found")	
    if name in EXTRA_TARGETS: 
        t = EXTRA_TARGETS[name]	
        if len(t) == 2: 
            return t	
        sheet, label, col = t	
        ws = wb[sheet]	
        for row in ws.iter_rows(min_col=1, max_col=1): 
            if row[0].value == label: 
                return sheet, f"{col}{row[0].row}" 
        raise KeyError(f"label {label!r} not found on {sheet}") 
    if "!" in name: 
        sheet, ref = name.rsplit("!", 1) 
        return sheet.strip("'"), ref 
    raise KeyError(f"{name} is not a defined name or known target")	


def apply_overrides(path: str, overrides: dict) -> None: 
    import openpyxl	
    wb = openpyxl.load_workbook(path)	
    for name, value in overrides.items(): 
        sheet, ref = resolve_target(wb, name) 
        if isinstance(value, bool): 
            value = "Y" if value else "N"	
        if ":" in ref:                          # a range, e.g. fc_Overrides C14:C23 -> list of values	
            flat = [c for row in wb[sheet][ref] for c in row] 
            for c, v in zip(flat, value): 
                if v is not None: 
                    c.value = v 
        else: 
            wb[sheet][ref].value = value	
    wb.calculation.fullCalcOnLoad = True 
    wb.save(path) 


def defined_name_target(wb, name: str): 
    dn = wb.defined_names[name]	
    sheet, ref = dn.attr_text.split("!") 
    return sheet.strip("'"), ref.replace("$", "")	


def workbook_bytes(snapshot: dict, basis: str, overrides: dict | None = None, analyst: str = "") -> bytes: 
    with tempfile.TemporaryDirectory() as tmp:	
        p = os.path.join(tmp, "model.xlsx")	
        write_workbook(snapshot, basis, p, overrides, analyst)	
        with open(p, "rb") as fh: 
            return fh.read() 


def workbook_filename(data: dict) -> str: 
    return f"Valuation_{data['ticker']}_{'GAAP' if data['basis'] == 'GAAP' else 'NonGAAP'}_{data['period_end']}.xlsx" 


__all__ = ["vendored", "parse_snapshot", "write_workbook", "apply_overrides", "workbook_bytes", "workbook_filename"] 
