# Changelog

## 0.2.0 - 2026-11-23

* App reorganised: Start here (guide) → Live search → My searches → Examples, with "what you should see" notes
  on each example. Live search asks each visitor for their SEC contact (sent only to the SEC, not stored).
* Override counter no longer counts untouched Data & Sources switches.

* Documentation and verification portal: `site/index.html` (self-contained, published to GitHub Pages by CI).
* The Excel builder is no longer included: it stays private with the owner. The SEC parser it shares with the app is
  bundled as `valuation/sec_data.py`; Excel parity tests run owner-side only; the hosted app has no .xlsx download.
* License changed to all rights reserved.

## 0.1.0 - 2026-11-22

* First release of the auditable app around the existing Excel builder (vendored unchanged, byte-checked).
* Python engine (WACC, forecast modes, DCF, sensitivity, value over time, reverse DCF, IRR) with Excel parity tests.
* Independent reference implementation and agreement tests.
* Formula registry, assumptions register, generated docs and worked example.
* Data provenance tags and raw-fetch snapshots.
* Streamlit app with Inputs / DCF / Reverse DCF / IRR / Logic / Assumptions / Checks / Download tabs.
* Verification report script and GitHub Actions workflow.
