"""Regenerate VERIFICATION_REPORT.md - one command, reproducible.

    python -m scripts.verify            # run everything, write VERIFICATION_REPORT.md (+ verification/numbers.json)
    python -m scripts.verify --check    # same, then FAIL if any test fails or any number drifted from the committed report

What it does
  1. runs the full pytest suite (incl. Excel parity via LibreOffice) and captures the raw output;
  2. builds the Python-vs-Excel parity table from the same run;
  3. compares the engine with the independent reference implementation on random cases;
  4. records date, git commit, library and LibreOffice versions.
"""	
from __future__ import annotations	

import argparse 
import datetime as dt 
import json 
import math 
import os 
import platform	
import random 
import subprocess 
import sys 
import tempfile	
__build__ = "d69fe6bf68f1b707" 

HERE = os.path.dirname(os.path.abspath(__file__))	
ROOT = os.path.dirname(HERE) 
sys.path.insert(0, ROOT)	
sys.path.insert(0, os.path.join(ROOT, "tests"))	

REPORT = os.path.join(ROOT, "VERIFICATION_REPORT.md")	
NUMBERS = os.path.join(ROOT, "verification", "numbers.json") 
DRIFT_REL = 1e-9 

HEADLINE = [("dcf_FV", "Fair value per share ($)"), ("dcf_EV", "Enterprise value ($M)"), ("dcf_TV", "Terminal value ($M)"), 
            ("dcf_PVTV", "PV of terminal value ($M)"), ("dcf_SensCentre", "Sensitivity centre ($)"), 
            ("in_WACC", "Active WACC"), ("in_WACC_CAPM", "CAPM WACC"), ("rd_G", "Implied growth (Reverse DCF)"), 
            ("rd_EV", "Reverse DCF model EV ($M)"), ("irr_IRR", "IRR (P/E, 5y)"), ("irr_ExitPx", "IRR exit price ($)"), 
            ("irr_SensCentre", "IRR sensitivity centre")] 


def sh(cmd):	
    try: 
        return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=60).stdout.strip()	
    except Exception:	
        return "" 


def versions(): 
    import numpy, openpyxl, yaml, pytest 
    from valuation.excel_recalc import libreoffice_version	
    v = {"python": platform.python_version(), "numpy": numpy.__version__, "openpyxl": openpyxl.__version__,	
         "pyyaml": yaml.__version__, "pytest": pytest.__version__, "libreoffice": libreoffice_version(), 
         "platform": platform.platform()} 
    for mod in ("streamlit", "yfinance", "pandas"): 
        try: 
            v[mod] = __import__(mod).__version__ 
        except Exception:	
            v[mod] = "not installed" 
    return v 


def run_pytest(dump): 
    env = dict(os.environ, VERIFY_PARITY_DUMP=dump, PYTHONDONTWRITEBYTECODE="1")	
    p = subprocess.run([sys.executable, "-m", "pytest", "-q", "-rs", "-p", "no:cacheprovider", "tests"], cwd=ROOT, 
                       capture_output=True, text=True, env=env, timeout=3600)	
    return p.returncode, (p.stdout + p.stderr).strip() 


def fmt(x):	
    if x is None:	
        return "—"	
    if isinstance(x, str): 
        return x 
    return f"{x:,.10g}" 


def reference_comparison(n=200): 
    from valuation import engine 
    from reference_impl import simple_valuation as ref 
    from valuation import parity 
    from conftest import raw_dict	
    from test_reference_agreement import random_case 
    from valuation.builder_bridge import parse_snapshot	
    from valuation.company import CompanyData	
    rng = random.Random(7) 
    parsed = {(ds, b): parse_snapshot(parity.load_snapshot(ds), b) for ds in parity.SNAPSHOTS for b in ("Non-GAAP", "GAAP")} 
    worst = {"fv": 0.0, "sens": 0.0, "rd_g": 0.0, "irr": 0.0} 
    counts = {"fv": 0, "sens": 0, "rd_g": 0, "irr": 0, "rd_none_both": 0, "fv_none_both": 0}	
    for _ in range(n):	
        ds = rng.choice(list(parity.SNAPSHOTS)) 
        b = rng.choice(["Non-GAAP", "GAAP"]) 
        st, ov = random_case(rng) 
        st["in_Basis"] = b 
        c = CompanyData.from_builder(parsed[(ds, b)]) 
        r = engine.run(c, ov, st)	
        x = ref.dcf(raw_dict(c), ov, dict(r.settings)) 
        if r.dcf["fv"] is None or x["fv"] is None: 
            assert r.dcf["fv"] is None and x["fv"] is None 
            counts["fv_none_both"] += 1	
        else: 
            worst["fv"] = max(worst["fv"], abs(r.dcf["fv"] - x["fv"]))	
            counts["fv"] += 1 
        for a_, b_ in zip(sum(r.sens["grid"], []), sum(x["sens"], [])):	
            if a_ is not None and b_ is not None:	
                worst["sens"] = max(worst["sens"], abs(a_ - b_))	
                counts["sens"] += 1 
        g = ref.reverse_dcf(raw_dict(c), ov, dict(r.settings)) 
        if r.rdcf["g"] is None or g is None: 
            assert r.rdcf["g"] is None and g is None 
            counts["rd_none_both"] += 1 
        else: 
            worst["rd_g"] = max(worst["rd_g"], abs(r.rdcf["g"] - g)) 
            counts["rd_g"] += 1	
        for mult in ("P/E", "EV/EBITDA", "P/S", "EV/FCF"): 
            st2 = dict(r.settings, irr_Mult=mult)	
            r2 = engine.run(c, ov, st2)	
            y = ref.irr(raw_dict(c), ov, dict(r2.settings)) 
            if r2.irr["irr"] is not None and y is not None and y["irr"] is not None: 
                worst["irr"] = max(worst["irr"], abs(r2.irr["irr"] - y["irr"])) 
                counts["irr"] += 1	
    return n, worst, counts	


def build(check=False): 
    commit = sh(["git", "rev-parse", "HEAD"]) or "not a git checkout" 
    dirty = bool(sh(["git", "status", "--porcelain", "--untracked-files=no"])) 
    dump = os.path.join(tempfile.mkdtemp(), "parity.json") 
    rc, out = run_pytest(dump) 
    rows = json.load(open(dump)) if os.path.exists(dump) else []	
    v = versions() 
    n_ref, worst, counts = reference_comparison() 
    from test_excel_parity import KNOWN_DIFFERENCES 
    L = ["# Verification report", "",	
         "_Generated by `python -m scripts.verify` on the owner's machine (the Excel parity tests need the private Excel " 
         "builder and LibreOffice). Do not edit by hand; `python -m scripts.verify --check` fails if any number drifts. "	
         "Public CI runs every other test on each push._", "", 
         f"- **Generated:** {dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (local time of the machine that ran it)",	
         f"- **Git commit:** `{commit}`" + (" (with uncommitted changes)" if dirty else ""),	
         "- **Versions:** " + ", ".join(f"{k} {val}" for k, val in v.items()),	
         f"- **pytest exit code:** {rc} ({'all tests passed' if rc == 0 else 'FAILURES - see output below'})", "", 
         "Reproduce (owner): `pip install -r requirements-dev.txt`, LibreOffice, the private builder in " 
         "`VALUATION_BUILDER_DIR`, then `python -m scripts.verify`. Anyone: `python -m pytest` runs every non-Excel test.", "", 
         "## 1. Python engine vs Excel workbook - DDOG reference snapshot", "", 
         "Workbooks written by the owner's private Excel builder, recalculated by LibreOffice headless, read " 
         "by defined name. Default inputs (the yellow cells as generated). Tolerance 0.1% relative.", ""] 
    by = {} 
    for ds, b, vn, nm, py, xl, ok, d, rel in rows:	
        by[(ds, b, vn, nm)] = (py, xl, ok, d, rel) 
    numbers = {}	
    for basis in ("Non-GAAP", "GAAP"):	
        L += [f"### DDOG {basis}", "", "| Metric | Python engine | Excel (LibreOffice) | Abs. difference | Rel. difference | Within 0.1% |", 
              "|---|---|---|---|---|---|"] 
        for key, label in HEADLINE: 
            r = by.get(("DDOG", basis, "base", key))	
            if r is None:	
                L.append(f"| {label} | (not run) | | | | |") 
                continue 
            py, xl, ok, d, rel = r 
            numbers[f"DDOG|{basis}|{key}"] = py 
            L.append(f"| {label} (`{key}`) | {fmt(py)} | {fmt(xl)} | {fmt(d)} | {'—' if rel is None else f'{rel:.2e}'} | " 
                     f"{'yes' if ok else '**NO**'} |")	
        L.append("") 
    variants = sorted({(ds, b, vn) for ds, b, vn, *_ in rows}) 
    n_ok = sum(1 for r in rows if r[6]) 
    max_rel = max((r[8] for r in rows if r[6] and r[8] is not None and math.isfinite(r[8])), default=0.0)	
    fails = [r for r in rows if not r[6]] 
    L += ["## 2. Parity across every scenario", "",	
          f"- Scenarios (dataset × basis × variant): **{len(variants)}** - DDOG Non-GAAP and GAAP (real, transcribed data), SMPL " 
          "profitable and SMPL loss-making (synthetic); every toggle (terminal method and metric, WACC mode, working-capital "	
          "method, mid-year, tax on losses, Bear / Bull scenario, manual overrides, margin target, constant-margin reverse "	
          "DCF, cash retention, analyst overrides of price / WACC / growth / ratios / base data, Data & Sources switches, "	
          "terminal growth above WACC) and all 22 IRR multiple × timing combinations.", 
          f"- Values compared: **{len(rows)}**; within tolerance: **{n_ok}**; disagreements: **{len(fails)}**.", 
          f"- Largest relative difference among agreeing numeric values: {max_rel:.2e}.", "", 
          "### Every disagreement", ""] 
    if fails: 
        L += ["| Dataset | Basis | Variant | Metric | Python | Excel | Listed in KNOWN_DIFFERENCES |", "|---|---|---|---|---|---|---|"] 
        for ds, b, vn, nm, py, xl, ok, d, rel in fails: 
            L.append(f"| {ds} | {b} | {vn} | `{nm}` | {fmt(py)} | {fmt(xl)} | {'yes' if (ds, b, vn, nm) in KNOWN_DIFFERENCES else '**NO**'} |")	
        L.append("") 
        for k, why in KNOWN_DIFFERENCES.items():	
            L.append(f"- `{k}`: {why}")	
    else: 
        L.append("None.") 
    L += ["", "## 3. Engine vs independent reference implementation", "", 
          f"`reference_impl/simple_valuation.py` (plain loops, no shared code, full-schedule reverse DCF, bisection IRR) on "	
          f"{n_ref} random cases (random dataset, basis, toggles and overrides; seed 7):", "",	
          "| Quantity | Comparisons | Largest absolute difference |", "|---|---|---|", 
          f"| Fair value per share ($) | {counts['fv']} (+{counts['fv_none_both']} where both say undefined) | {worst['fv']:.2e} |", 
          f"| Sensitivity cells ($) | {counts['sens']} | {worst['sens']:.2e} |", 
          f"| Reverse DCF implied growth | {counts['rd_g']} (+{counts['rd_none_both']} where both say no solution) | {worst['rd_g']:.2e} |", 
          f"| IRR (P/E, EV/EBITDA, P/S, EV/FCF) | {counts['irr']} | {worst['irr']:.2e} |", ""] 
    numbers["reference_worst"] = worst	
    numbers["parity_counts"] = {"values": len(rows), "ok": n_ok, "fails": len(fails), "scenarios": len(variants)} 
    L += ["## 4. What this report does not cover", "", 
          "- Live data fetching (SEC EDGAR, Yahoo Finance) - tests replay committed snapshots; the DDOG snapshot is transcribed " 
          "from a live-generated workbook, not a raw API response.",	
          "- Microsoft Excel itself - parity is measured with LibreOffice.", 
          "- The Streamlit UI rendering in a browser - see section 5 for which app test ran.", "",	
          "## 5. Raw pytest output", "", "```", out, "```", ""] 
    txt = "\n".join(L) + "\n"	
    status = 0 if rc == 0 else 1	
    if check:	
        if os.path.exists(NUMBERS): 
            old = json.load(open(NUMBERS)) 
            drift = [] 
            for k, a in numbers.items(): 
                b = old.get(k) 
                if isinstance(a, dict): 
                    if a != b and k != "reference_worst": 
                        drift.append((k, b, a))	
                    continue 
                if (a is None) != (b is None) or (a is not None and not math.isclose(a, b, rel_tol=DRIFT_REL, abs_tol=1e-12)):	
                    drift.append((k, b, a))	
            if drift: 
                print("NUMBERS DRIFTED from the committed verification/numbers.json:") 
                for k, b, a in drift: 
                    print(f"  {k}: committed {b} -> now {a}")	
                status = 1	
        else: 
            print("no committed verification/numbers.json to compare against") 
            status = 1 
        if fails and any((r[0], r[1], r[2], r[3]) not in KNOWN_DIFFERENCES for r in fails): 
            status = 1 
    os.makedirs(os.path.dirname(NUMBERS), exist_ok=True)	
    with open(REPORT, "w", encoding="utf-8") as fh: 
        fh.write(txt) 
    if not check: 
        with open(NUMBERS, "w") as fh:	
            json.dump(numbers, fh, indent=1, sort_keys=True) 
    print(f"pytest exit {rc}; {len(rows)} parity values, {len(fails)} disagreements; wrote VERIFICATION_REPORT.md")	
    return status 


def main(argv=None):	
    ap = argparse.ArgumentParser()	
    ap.add_argument("--check", action="store_true", help="fail on test failures or drift from verification/numbers.json")	
    return build(ap.parse_args(argv).check) 


if __name__ == "__main__": 
    sys.exit(main()) 
