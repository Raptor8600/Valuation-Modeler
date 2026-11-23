# Data provenance

Every input shows one source tag:

| Tag | Meaning | What is shown |
|---|---|---|
| **Fetched** | Taken directly from a data provider | provider, endpoint, field / XBRL tag, fetch timestamp, filing period end, link to the document |
| **Derived** | Calculated from other inputs | the formula and its inputs |
| **Assumption** | A default chosen by the model | the value and why it was chosen (see assumptions.md) |
| **Analyst override** | You typed a different value | flagged in the Inputs table, with the original automatic value still shown |
| **Missing** | The provider did not report it | blank and flagged; never filled with a guess |

## Snapshots

`data_snapshots/<TICKER>_<YYYYMMDDTHHMMSS>.json` holds the raw provider responses for one live fetch:

* `tickers` - the matching row of https://www.sec.gov/files/company_tickers.json
* `submissions` - https://data.sec.gov/submissions/CIK##########.json
* `companyfacts` - https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json
* `index_<accession>` - the earnings 8-K's filing index (to find Exhibit 99.1)
* `market` - the values read from yfinance (price, beta, rf, consensus growth) with their as-of time
* `_meta` - fetch time, the exact request URLs, and the yfinance attribute behind each market field

`data_snapshots/reference/` holds the committed snapshots used by the tests:

* `DDOG_2026-11-22T2117_transcribed.json` - real DDOG figures, transcribed (see its `_meta.provenance`)
* `SMPL_synthetic_profit.json`, `SMPL_synthetic_loss.json` - invented numbers that exercise code paths, labelled synthetic
  everywhere they appear

## Checking a number by hand

1. Open the Inputs tab and expand the field.
2. Click the filing link (10-Q / 10-K / 8-K Exhibit 99.1) and search for the line item, e.g. "Total revenue".
3. For TTM figures, the tag lists the three parts (latest FY, current YTD, prior-year YTD) and their periods.
