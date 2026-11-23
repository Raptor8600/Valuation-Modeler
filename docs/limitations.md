# Limitations

* **Educational, not investment advice.** The model is a structured way to state and test assumptions; its output is
  only as good as those assumptions.
* **Market data is third-party.** Price, beta, the 10-year Treasury yield and analyst consensus come from Yahoo Finance via
  the unofficial `yfinance` library. They can be delayed, revised, missing, or differ from the exchange and from other
  vendors. Nothing in an SEC filing can confirm them; the source tag links to the Yahoo page so you can compare.
* **XBRL coverage.** The SEC `companyfacts` API holds only non-dimensional facts. Segment data, multi-class share counts on
  the cover page and some company-specific tags are not available. A figure that is not found is left blank and flagged -
  never guessed - and you can type it in from the linked filing.
* **US SEC registrants only.** Foreign private issuers filing 20-F/40-F are partially supported by the parser; non-SEC
  companies are not supported.
* **Non-GAAP is an approximation.** The bridge adds back SBC, acquired-intangible amortization and an "other" figure you
  type from the 8-K. Companies define non-GAAP differently; compare with Exhibit 99.1.
* **Model simplifications** (all visible in the Assumptions register): one flat WACC; constant D&A / capex / NWC ratios;
  statutory tax with no NOL schedule; no explicit SBC cash cost under non-GAAP (dilution enters only through the share-count
  drift); book value of debt; operating leases excluded by default.
* **Reverse DCF** solves only for a constant growth rate between −50% and +150% a year; margins are not solved for.
* **IRR** proxies gross profit and book value by scaling with revenue; P/E scales net income with NOPAT.
* **Thesis & Scenarios tab** (probability-weighted price target) exists in the workbook but is not mirrored in the app.
* **Excel parity is tested with LibreOffice**, not Microsoft Excel. The two agree on all functions used here except one
  documented IRR convergence case (see known_issues.md).
