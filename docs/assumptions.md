# Assumptions register

_Generated from `assumptions.yaml` by `python -m scripts.gen_docs`. Sensitivities are real re-runs of the engine on the DDOG Non-GAAP reference snapshot (data as of 2026-11-22 21:17), not descriptions._

| Assumption | Default | Current value | Sensitivity (fair value / implied growth) |
|---|---|---|---|
| **Marginal tax rate** (`in_TaxRate`) | 21% (US federal statutory) | 21.00% | 16.00%: $50.96 / 32.52% · base: $48.36 / 33.52% · 26.00%: $45.75 / 34.59% |
| **Equity risk premium** (`in_ERP`) | 5.5% | 5.50% | 4.50%: $55.22 / 30.35% · base: $48.36 / 33.52% · 6.50%: $43.24 / 36.50% |
| **Discount rate (WACC), one flat rate for all years** (`in_WACC_Direct`) | CAPM WACC rounded to 0.1% | 13.10% | 12.10%: $52.69 / 31.43% · base: $48.36 / 33.52% · 14.10%: $44.79 / 35.52% |
| **Terminal (perpetual) growth** (`in_TermG`) | 2.5% | 2.50% | 2.00%: $47.00 / 34.01% · base: $48.36 / 33.52% · 3.00%: $49.84 / 33.00% |
| **Exit multiple (exit-multiple method only)** (`in_ExitMult`) | 15x Year-10 EBITDA | 15.0x | 12.5x: $63.92 / 26.85% · base: $70.23 / 24.97% · 17.5x: $76.54 / 23.38% |
| **Growth fade shape** (`in_G1`) | Straight line from Year-1 growth (consensus) to terminal growth by Year 10 | 22.30% | 17.30%: $42.05 / 33.52% · base: $48.36 / 33.52% · 27.30%: $55.80 / 33.52% |
| **Target operating margin** (`in_MarginTarget`) | = today's TTM margin (no operating leverage) | 22.54% | 17.54%: $41.59 / 37.23% · base: $48.36 / 33.52% · 27.54%: $55.12 / 30.64% |
| **Capex intensity** (`in_CapexPct`) | TTM capex ÷ TTM revenue | 3.69% | 2.69%: $50.67 / 32.63% · base: $48.36 / 33.52% · 4.69%: $46.05 / 34.47% |
| **Working-capital intensity** (`in_NWCPct`) | TTM residual (OCF − NI − D&A − SBC) ÷ change in revenue | 7.38% | 2.38%: $47.52 / 34.01% · base: $48.36 / 33.52% · 12.38%: $49.19 / 33.05% |
| **Annual change in share count** (`in_ShareChg`) | Last year's diluted share change | 3.59% | 2.59%: $48.36 / 33.52% · base: $48.36 / 33.52% · 4.59%: $48.36 / 33.52% |
| **Year-end discounting** | End-of-year | - | base $48.36 / 33.52% → in_Timing = Mid-year: $50.71 / 32.60% |
| **Stock-based compensation treatment** | Workbook basis chosen at creation (Non-GAAP adds SBC back to operating income) | - | base $48.36 / 33.52% → in_Basis = GAAP: $11.78 / 92.68% |
| **No tax benefit on operating losses** | No tax benefit | - | base $48.36 / 33.52% → in_LossTax = Tax credit on losses: $48.36 / 33.52% |
| **Terminal value method** | Perpetuity (Gordon growth) | - | base $48.36 / 33.52% → in_TVMethod = Exit Multiple: $70.23 / 24.97% |

## Why each default, and what would change it

### Marginal tax rate

- **Default:** 21% (US federal statutory)
- **Why:** Statutory rate on NOPAT; effective tax rates are distorted by stock-comp deductions and NOLs. The TTM effective rate is shown beside it for reference.
- **What would change it:** State taxes (often +2-5pp), large foreign operations, or a long NOL shield.

### Equity risk premium

- **Default:** 5.5%
- **Why:** Middle of the 4-6% range of published implied ERP estimates (e.g. Damodaran).
- **What would change it:** Your house view of market risk pricing; only matters in CAPM mode or through the default direct WACC.

### Discount rate (WACC), one flat rate for all years

- **Default:** CAPM WACC rounded to 0.1%
- **Why:** A single rate is standard for a 10-year DCF; there is no term structure or changing capital mix.
- **What would change it:** Your hurdle rate, a changing leverage plan, or an industry beta.

### Terminal (perpetual) growth

- **Default:** 2.5%
- **Why:** Close to long-run nominal GDP growth; a business cannot outgrow the economy forever.
- **What would change it:** Inflation expectations, a structurally declining industry (lower), or a much longer high-growth runway (extend the forecast instead).

### Exit multiple (exit-multiple method only)

- **Default:** 15x Year-10 EBITDA
- **Why:** A mature-company multiple; today's multiple is a poor anchor for a business ten years older.
- **What would change it:** Sector multiples for mature peers.

### Growth fade shape

- **Default:** Straight line from Year-1 growth (consensus) to terminal growth by Year 10
- **Why:** Simple, transparent and conservative for high-growth companies.
- **What would change it:** A visible multi-year backlog (hold growth longer: Manual Override) or a maturing market (faster fade). Sensitivity shown: Year-1 growth ±5pp.

### Target operating margin

- **Default:** = today's TTM margin (no operating leverage)
- **Why:** Neutral starting point: the model does not assume margin expansion unless you do.
- **What would change it:** Your view of margin at scale (software often 25-35%).

### Capex intensity

- **Default:** TTM capex ÷ TTM revenue
- **Why:** Today's reinvestment rate carried forward.
- **What would change it:** Planned data-centre build-outs, or a capex-light shift. Long-run capex should at least match D&A.

### Working-capital intensity

- **Default:** TTM residual (OCF − NI − D&A − SBC) ÷ change in revenue
- **Why:** Captures the deferred-revenue tailwind of subscription businesses.
- **What would change it:** Billing-term changes, or using Flat mode for businesses whose working capital scales with revenue rather than growth.

### Annual change in share count

- **Default:** Last year's diluted share change
- **Why:** Dilution from stock compensation is a real cost per share in the value-over-time table and the IRR.
- **What would change it:** A buyback programme, or a slowdown in equity grants.

### Year-end discounting

- **Default:** End-of-year
- **Why:** Conservative and the simplest to audit; mid-year assumes cash arrives evenly through the year.
- **What would change it:** House convention; mid-year is common in banking models.

### Stock-based compensation treatment

- **Default:** Workbook basis chosen at creation (Non-GAAP adds SBC back to operating income)
- **Why:** Non-GAAP shows how the company presents itself; GAAP treats SBC as the real cost it is. Sensitivity shown: switch to GAAP.
- **What would change it:** Whether you think SBC is a cash-equivalent cost (GAAP) or not. Under Non-GAAP, dilution is captured only through the share-count drift.

### No tax benefit on operating losses

- **Default:** No tax benefit
- **Why:** Realistic unless the company has large usable NOLs or profitable group entities.
- **What would change it:** Evidence of usable tax losses.

### Terminal value method

- **Default:** Perpetuity (Gordon growth)
- **Why:** Intrinsic, does not import today's market multiples.
- **What would change it:** When a transaction multiple is the relevant exit (private equity style analysis).

