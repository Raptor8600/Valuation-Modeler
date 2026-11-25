# Valuation Modeler

**DCF, Reverse DCF and IRR you can check line by line.** Enter a ticker, see the inputs pulled from the company's latest
SEC filings, type your own overrides, and get the same results as the Excel workbooks, with the formula, your numbers,
the source and a passing test behind every figure.

> **Educational tool, not investment advice.** It turns assumptions into numbers; it does not tell you whether to buy or sell anything.

<!-- Screenshot placeholders: replace with real captures after the first deployment -->
<!-- ![Inputs tab](docs/img/inputs.png) -->
<!-- ![DCF tab with show-your-work panel](docs/img/dcf.png) -->
<!-- ![Checks tab](docs/img/checks.png) -->

## What you can verify for every number

| Question | Where the answer is |
|---|---|
| What formula produced it? | "Show your work" panel under each result; **Logic** tab; [docs/formulas.md](docs/formulas.md) (all generated from [`formulas.yaml`](formulas.yaml)) |
| What is the logic in plain English? | Same places: each formula has an explanation |
| Where did each input come from? | **Inputs** tab source tag: *Fetched* (provider, XBRL tag / field, fetch time, period end, filing link), *Derived* (formula), *Assumption* (rationale), *Analyst override* (original value kept), *Missing* (blank, never guessed). Raw provider responses are saved in `data_snapshots/` |
| Is the calculation correct? | **Checks** tab (live tie-outs with numbers); [VERIFICATION_REPORT.md](VERIFICATION_REPORT.md): Excel parity, independent reference implementation, full pytest output |
| What did the model assume for me? | **Assumptions** tab / [docs/assumptions.md](docs/assumptions.md), with a real sensitivity for each |

## How it fits together

```
SEC EDGAR XBRL + Yahoo Finance ──► data_snapshots/*.json (raw, timestamped)
                                        │
                     valuation/sec_data.py  (same parser the Excel workbooks use)
                                        │
                     valuation/engine.py  (single source of truth) ──► Streamlit app (app.py + modules/)
                                        │
        tests/test_reference_agreement.py ◄── reference_impl/simple_valuation.py (independent)
        tests/test_excel_parity.py        ◄── owner's private Excel builder + LibreOffice (owner-run)
```

The Excel builder that produces the workbooks is **private and not in this repository**. The engine was verified
against it value by value (see VERIFICATION_REPORT.md); those parity tests run on the owner's machine and are skipped
everywhere else. Everything else - engine, reference implementation, edge cases, registry, provenance - is tested in CI.

## Use it

Open the hosted app (link in the repository description). It opens on **Start here**, a short guide. Then:

1. **Examples** - three ready-made companies (Datadog with real data, two made-up ones) that show what a complete model
   looks like and what each screen should display.
2. **Live search** - type a ticker plus your name and email (the SEC requires a contact on every data request; it is
   sent only to the SEC and not saved).
3. **My searches** - every search from this session (a *snapshot*: the data exactly as returned at that moment). Private
   to your browser; download one to keep it and re-open it later.

Every company opens with the current share price beside the **Bear / Base / Bull** values and the probability-weighted
value. Pick **GAAP** or **Non-GAAP** in the left menu: the basis applies to every tab. The **Download** tab gives a
values-only Excel file of the run (no formulas) and the search data.

## Verify it

CI runs the public test suite on every push. The owner regenerates the full report, including Excel parity, with
`python -m scripts.verify` (needs the private builder and LibreOffice).

## Data and its limits

* **Financial statements:** SEC EDGAR XBRL `companyfacts` (official filings, linked line by line). The spec this project
  started from suggested yfinance for statements; SEC XBRL is used instead because it is what the workbooks use (so the app
  and the spreadsheet cannot disagree) and every figure links to the filing it came from.
* **Market data:** Yahoo Finance via `yfinance` (price, beta, 10-year Treasury, consensus revenue growth), cached for
  15 minutes in the app. **Unofficial and third-party:** it can be delayed, missing or different from the exchange, and no
  filing can confirm it. Its source tag links to the Yahoo page.
* GAAP figures come straight from the filings; the Non-GAAP basis is a transparent approximation (SBC, acquired-intangible
  amortization and an "other" line you type from the 8-K), each part switchable.
* More in [docs/limitations.md](docs/limitations.md) and [docs/known_issues.md](docs/known_issues.md).

## Repository map

| Path | What |
|---|---|
| `valuation/engine.py` | WACC, forecast modes, DCF, sensitivity, value over time, reverse DCF, IRR |
| `valuation/company.py` | reported facts and the Data & Sources derivations, with source tags |
| `reference_impl/simple_valuation.py` | independent, deliberately simple re-implementation (no shared code) |
| `formulas.yaml` / `assumptions.yaml` | formula registry and assumptions register (drive the Logic / Assumptions pages and the docs) |
| `valuation/checks.py` | live integrity checks |
| `valuation/xlsx_export.py` | values-only Excel export |
| `valuation/data_sources.py` | live fetch → raw snapshot; replay |
| `valuation/sec_data.py` | SEC XBRL parser shared with the Excel builder |
| `app.py`, `modules/` | Streamlit UI |
| `tests/` | parity, reference agreement, edge cases, registry, provenance, docs freshness, builder kept out of the repo, app smoke |
| `scripts/verify.py` | builds VERIFICATION_REPORT.md |
| `scripts/build_site.py`, `site/index.html` | documentation and verification portal (GitHub Pages) |
| `docs/` | methodology, formulas, assumptions, worked example, data provenance, limitations, known issues, deployment, changelog |

## Documentation portal (index.html)

`site/index.html` is a single self-contained page that presents everything a reviewer needs: headline DDOG results and
live checks, the verification report, the worked example, the formula registry, the assumptions register and the rest of
`docs/`. GitHub Pages publishes it; CI rebuilds it on every push to `main`.
Rebuild locally: `python -m scripts.build_site`.

## Hosting

GitHub Pages cannot run Python, so it hosts the portal, not the interactive app. Deploy to Streamlit Community Cloud or any
Docker host. Steps and which features need a server are in [docs/deployment.md](docs/deployment.md). No API keys or
secrets are stored in the repository; the SEC contact goes in Streamlit secrets or an environment variable.

## License

All rights reserved - see [LICENSE](LICENSE). The code is published for transparency and review, not for reuse.
