# Known issues

## Engine vs spreadsheet disagreements (all of them)

Measured by `tests/test_excel_parity.py` across every scenario; reproduced in VERIFICATION_REPORT.md.

| Where | Engine | Spreadsheet (LibreOffice) | Why |
|---|---|---|---|
| DDOG GAAP, variant `irr_exit_override` (EV/EBITDA, exit 20x, 3 years, +1% shares/yr), `irr_IRR` | −45.35% | error (shown "n/a") | LibreOffice's IRR() does not converge from its 10% starting guess. The cash flows have no dividends, so the exact IRR is (exit ÷ price)^(1/3) − 1; the engine equals that and the workbook's own price-only CAGR cell. Not checked in Microsoft Excel. |

No other metric differs by more than 0.1% (most agree to ~1e-12).

## Deliberate behaviour differences (not numeric disagreements)

* **Missing data: the engine is stricter than Excel.** Where a reported figure is blank, some workbook formulas treat the
  blank cell as zero (e.g. a missing D&A gives D&A% = 0). The engine instead marks the input *Missing* and computes
  nothing until you type a value. The parity tests use complete data, so this never affects a compared number.
* **The app does not mirror the Thesis & Scenarios tab.** The downloaded workbook still contains it.

## Data

* **DDOG reference snapshot is transcribed, not raw.** Built from the Data & Sources tab of a workbook generated live on
  2026-11-22 21:17. Three filing dates of older filings are placeholders (marked in
  `scripts/reconstruct_ddog_snapshot.py`); they only order restatements. Weighted-average *basic* shares were not
  available, so that comparison line is blank.
* **The live fetch path was not exercised in the build environment** (no internet). `valuation/data_sources.py` uses the
  builder's parser and request logic (valuation/sec_data.py); the first live run should be checked against the filing links.

## Owner-only tests

* The Excel builder is private. Excel parity, the defaults-match-builder test and the workbook download run only on the
  owner's machine; in CI they are skipped and the committed VERIFICATION_REPORT.md is the record. The hosted app does not
  offer the formula workbook; it offers a values-only Excel export of each run instead.

## Environment

* `streamlit` and `yfinance` were not installed in the build environment, so the Streamlit UI was not run there. The app's
  logic lives in `valuation/` and is fully tested; `tests/test_app_smoke.py` runs Streamlit's AppTest when streamlit is
  installed (CI installs it).
* requirements.txt and requirements-dev.txt list packages without version pins (untested pins broke the Streamlit
  Cloud install). The exact versions used for each verification run are recorded in VERIFICATION_REPORT.md; once the
  hosted app runs, its install log shows the versions it uses, which can be copied back as pins.
