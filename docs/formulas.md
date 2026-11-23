# Formula registry

_Generated from `formulas.yaml` by `python -m scripts.gen_docs` - do not edit by hand._

Each entry: the formula, the logic in plain English, where the same logic lives in the Excel workbook, the Python that implements it, the independent reference implementation, and the tests that verify it. **Kind** separates sourced facts, formulas and judgment calls.

## Data

### `data.ttm` - Trailing-twelve-month (TTM) figure

- **Kind:** formula
- **Formula:** TTM = latest fiscal year + current year-to-date − prior-year year-to-date
- **Logic:** Builds a full-year figure ending at the latest quarter from three reported periods. Falls back to the sum of the last four quarters when the YTD pieces are not tagged.
- **Inputs:** `XBRL duration facts`
- **Units:** $M
- **Excel:** 'Data & Sources'!C25:F25 (row "Revenue")
- **Python:** `valuation/sec_data.py::Facts._ttm_from`
- **Reference implementation:** `(parsed once by valuation/sec_data.py; both implementations consume its output)`
- **Verified by:** `tests/test_excel_parity.py::test_parity_all_metrics`, `tests/test_provenance.py::test_ttm_parts_shown`

### `data.nongaap_adj` - Non-GAAP adjustments

- **Kind:** judgment
- **Formula:** Adj = [Basis = Non-GAAP] × (SBC·s₁ + acquired-intangible amortization·s₂ + other·s₃),  sᵢ ∈ {0,1}
- **Logic:** Under Non-GAAP the selected adjustments are added back to GAAP operating income. Each has a Y/N switch (Data & Sources §4). Zero under GAAP.
- **Inputs:** `d_sbc`, `d_amort`, `other adjustments`, `in_Basis`
- **Units:** $M
- **Excel:** 'Data & Sources'!B51 (name `d_NonGAAPAdj`)
- **Python:** `valuation.company.CompanyData.derive`
- **Reference implementation:** `reference_impl.simple_valuation.resolve`
- **Verified by:** `tests/test_excel_parity.py::test_parity_all_metrics`

### `data.ebit_margin` - Operating margin on the selected basis

- **Kind:** formula
- **Formula:** m₀ = (GAAP operating income + Adj) ÷ Revenue_TTM
- **Logic:** Starting margin of the forecast.
- **Inputs:** `d_ebit`, `d_NonGAAPAdj`, `d_revenue`
- **Units:** decimal
- **Excel:** 'Data & Sources'!B54 (name `d_EBITMargin`)
- **Python:** `valuation.company.CompanyData.derive`
- **Reference implementation:** `reference_impl.simple_valuation.resolve`
- **Verified by:** `tests/test_excel_parity.py::test_parity_all_metrics`

### `data.da_used` - D&A used in the cash-flow build

- **Kind:** formula
- **Formula:** D&A_used = D&A(cash-flow statement) − [Non-GAAP and amortization added back] × acquired-intangible amortization
- **Logic:** Prevents adding amortization back twice (once in non-GAAP EBIT, once as D&A).
- **Inputs:** `d_da`, `d_amort`
- **Units:** $M
- **Excel:** 'Data & Sources'!B55 (name `d_DA_UFCF`)
- **Python:** `valuation.company.CompanyData.derive`
- **Reference implementation:** `reference_impl.simple_valuation.resolve`
- **Verified by:** `tests/test_excel_parity.py::test_parity_all_metrics`

### `data.capex` - Capital expenditure used

- **Kind:** formula
- **Formula:** Capex = purchases of PP&E + [switch] × capitalized software
- **Logic:** Cash invested in fixed assets and capitalized software.
- **Inputs:** `d_capex_ppe`, `d_capex_sw`
- **Units:** $M
- **Excel:** 'Data & Sources'!B57 (name `d_Capex`)
- **Python:** `valuation.company.CompanyData.derive`
- **Reference implementation:** `reference_impl.simple_valuation.resolve`
- **Verified by:** `tests/test_excel_parity.py::test_parity_all_metrics`

### `data.nwc_resid` - Working-capital & other operating cash items (residual)

- **Kind:** formula
- **Formula:** Residual = OCF − net income − D&A − SBC
- **Logic:** Everything in operating cash flow that is not earnings or a major non-cash charge; positive = cash inflow (e.g. growing deferred revenue).
- **Inputs:** `d_ocf`, `d_net_income`, `d_da`, `d_sbc`
- **Units:** $M
- **Excel:** 'Data & Sources'!B59 (name `d_NWCResid`)
- **Python:** `valuation.company.CompanyData.derive`
- **Reference implementation:** `reference_impl.simple_valuation.resolve`
- **Verified by:** `tests/test_excel_parity.py::test_parity_all_metrics`

### `data.net_cash` - Net cash

- **Kind:** formula
- **Formula:** Net cash = cash & investments counted − debt counted − other claims
- **Logic:** Balance-sheet items switched Y on Data & Sources §5; operating leases and long-term securities are off by default.
- **Inputs:** `in_Cash`, `in_Debt`, `in_Other`
- **Units:** $M
- **Excel:** 'Start Here & Guide'!B22 (name `in_NetCash`)
- **Python:** `valuation.engine.resolve_inputs`
- **Reference implementation:** `reference_impl.simple_valuation.resolve`
- **Verified by:** `tests/test_excel_parity.py::test_parity_all_metrics`

## Defaults

### `defaults.g1` - Year-1 revenue growth (default)

- **Kind:** judgment
- **Formula:** g₁ = analyst consensus next-FY revenue growth, else TTM revenue growth
- **Logic:** Starting growth of the fade. Consensus comes from Yahoo Finance; override it with your own view.
- **Inputs:** `d_Cons1y`, `d_RevGrowth`
- **Units:** decimal
- **Excel:** 'Start Here & Guide'!B33 (name `in_G1`)
- **Python:** `valuation.engine.resolve_inputs`
- **Reference implementation:** `reference_impl.simple_valuation.resolve`
- **Verified by:** `tests/test_excel_parity.py::test_parity_all_metrics`

### `defaults.ratios` - D&A, capex and working-capital ratios (defaults)

- **Kind:** formula
- **Formula:** D&A% = D&A_used ÷ Rev_TTM;  Capex% = Capex ÷ Rev_TTM;  NWC% = Residual ÷ ΔRev (incremental) or ÷ Rev_TTM (flat)
- **Logic:** Today's reported ratios carried into every forecast year unless overridden.
- **Inputs:** `d_DA_UFCF`, `d_Capex`, `d_NWCResid`, `d_revenue`, `d_dRev`
- **Units:** decimal
- **Excel:** 'Start Here & Guide'!B38 (name `in_NWCPct`)
- **Python:** `valuation.engine.resolve_inputs`
- **Reference implementation:** `reference_impl.simple_valuation.resolve`
- **Verified by:** `tests/test_excel_parity.py::test_parity_all_metrics`

## WACC

### `wacc.ke` - Cost of equity (CAPM)

- **Kind:** formula
- **Formula:** Ke = Rf + β × ERP
- **Logic:** Return shareholders require: the risk-free rate plus beta times the equity risk premium.
- **Inputs:** `in_Rf`, `in_Beta`, `in_ERP`
- **Units:** decimal
- **Excel:** 'DCF Model'!F8 (name `in_Ke`)
- **Python:** `valuation.engine.compute_wacc`
- **Reference implementation:** `reference_impl.simple_valuation.resolve`
- **Verified by:** `tests/test_excel_parity.py::test_parity_all_metrics`, `tests/test_showwork.py::test_wacc_substitution`

### `wacc.kd` - Pre-tax cost of debt (default)

- **Kind:** judgment
- **Formula:** Kd = interest expense ÷ debt if that exceeds Rf and debt > 0, else Rf + 1.5%
- **Logic:** Uses the company's own interest burden when meaningful; low-coupon convertibles fall back to Rf + 1.5%.
- **Inputs:** `d_interest`, `in_Debt`, `in_Rf`
- **Units:** decimal
- **Excel:** 'DCF Model'!F9 (name `in_Kd`)
- **Python:** `valuation.engine.resolve_inputs`
- **Reference implementation:** `reference_impl.simple_valuation.resolve`
- **Verified by:** `tests/test_excel_parity.py::test_parity_all_metrics`

### `wacc.weights` - Capital weights

- **Kind:** formula
- **Formula:** We = P·N ÷ (P·N + D);  Wd = 1 − We
- **Logic:** Market value of equity versus book value of debt.
- **Inputs:** `in_Price`, `in_Shares`, `in_Debt`
- **Units:** decimal
- **Excel:** 'DCF Model'!F12 (name `in_We`)
- **Python:** `valuation.engine.compute_wacc`
- **Reference implementation:** `reference_impl.simple_valuation.resolve`
- **Verified by:** `tests/test_excel_parity.py::test_parity_all_metrics`, `tests/test_checks.py::test_checks_pass_on_ddog`

### `wacc.capm` - WACC (CAPM build-up)

- **Kind:** formula
- **Formula:** WACC = We × Ke + Wd × Kd × (1 − t)
- **Logic:** Blended required return of all capital providers.
- **Inputs:** `in_We`, `in_Ke`, `in_Wd`, `in_Kd`, `in_TaxRate`
- **Units:** decimal
- **Excel:** 'DCF Model'!F14 (name `in_WACC_CAPM`)
- **Python:** `valuation.engine.compute_wacc`
- **Reference implementation:** `reference_impl.simple_valuation.resolve`
- **Verified by:** `tests/test_excel_parity.py::test_parity_all_metrics`

### `wacc.active` - Active discount rate

- **Kind:** judgment
- **Formula:** WACC = direct input (Standard mode; default ROUND(CAPM WACC, 3)) or CAPM WACC (Advanced mode)
- **Logic:** One flat rate for every year (no term structure).
- **Inputs:** `in_WACCMode`, `in_WACC_Direct`, `in_WACC_CAPM`
- **Units:** decimal
- **Excel:** 'DCF Model'!B31 (name `in_WACC`)
- **Python:** `valuation.engine.resolve_inputs`
- **Reference implementation:** `reference_impl.simple_valuation.resolve`
- **Verified by:** `tests/test_excel_parity.py::test_parity_all_metrics`, `tests/test_edge_cases.py::test_excel_round_half_away_from_zero`

## Forecast

### `fc.auto` - Automatic fade (growth and margin paths)

- **Kind:** judgment
- **Formula:** g_t = g₁ + (g∞ − g₁)·(t − 1)/9;   m_t = m₀ + (m* − m₀)·min(t / T*, 1)
- **Logic:** Growth falls in a straight line from Year-1 growth to terminal growth by Year 10; margin moves in a straight line to the target margin by the target year, then holds.
- **Inputs:** `in_G1`, `in_TermG`, `in_EBITM0`, `in_MarginTarget`, `in_MarginYear`
- **Units:** decimal
- **Excel:** 'Forecast Builder'!B9:K9 (name `fc_Growth`)
- **Python:** `valuation.engine.forecast`
- **Reference implementation:** `reference_impl.simple_valuation.growth_and_margin`
- **Verified by:** `tests/test_excel_parity.py::test_parity_all_metrics`, `tests/test_reference_agreement.py::test_dcf_agrees`

### `fc.scenarios` - Bear / Base / Bull scenario paths

- **Kind:** judgment
- **Formula:** Bear: g_t − 5pp·(10 − t)/9, m_t − 3pp·min(t/T*,1);   Bull: +5pp / +3pp;   Base = automatic fade (every cell editable)
- **Logic:** Default scenario rows; select with Forecast Mode = Scenario.
- **Inputs:** `fc_Mode`, `fc_Scenario`
- **Units:** decimal
- **Excel:** 'Forecast Builder'!B31:K31 (name `fc_BearG`)
- **Python:** `valuation.engine.forecast`
- **Reference implementation:** `reference_impl.simple_valuation.growth_and_margin`
- **Verified by:** `tests/test_excel_parity.py::test_parity_all_metrics`

## DCF

### `dcf.revenue` - Revenue

- **Kind:** formula
- **Formula:** Rev_t = Rev_{t−1} × (1 + g_t),  Rev₀ = TTM revenue;  Year 11 uses g∞
- **Logic:** Compounds TTM revenue along the selected growth path.
- **Inputs:** `in_Rev0`, `fc_Growth`
- **Units:** $M
- **Excel:** 'DCF Model'!B40:K40 (name `dcf_rev`)
- **Python:** `valuation.engine.schedule`
- **Reference implementation:** `reference_impl.simple_valuation.build_years`
- **Verified by:** `tests/test_excel_parity.py::test_parity_all_metrics`, `tests/test_reference_agreement.py::test_dcf_agrees`

### `dcf.nopat` - EBIT, taxes and NOPAT

- **Kind:** formula
- **Formula:** EBIT_t = Rev_t × m_t;  Tax_t = t × max(EBIT_t, 0) [no benefit on losses] or t × EBIT_t [tax credit];  NOPAT_t = EBIT_t − Tax_t
- **Logic:** Unlevered after-tax operating profit. By default losses get no tax credit.
- **Inputs:** `in_TaxRate`, `in_LossTax`
- **Units:** $M
- **Excel:** 'DCF Model'!B44:L44 (row "NOPAT ($M)")
- **Python:** `valuation.engine.schedule`
- **Reference implementation:** `reference_impl.simple_valuation.one_year`
- **Verified by:** `tests/test_excel_parity.py::test_parity_all_metrics`, `tests/test_edge_cases.py::test_negative_margins_pay_no_tax`

### `dcf.ufcf` - Unlevered free cash flow

- **Kind:** formula
- **Formula:** UFCF_t = NOPAT_t + Rev_t·D&A% − Rev_t·Capex% + NWC_t,   NWC_t = NWC%·(Rev_t − Rev_{t−1}) [incremental] or NWC%·Rev_t [flat]
- **Logic:** Cash the operations generate for all capital providers.
- **Inputs:** `in_DAPct`, `in_CapexPct`, `in_NWCPct`, `in_NWCMethod`
- **Units:** $M
- **Excel:** 'DCF Model'!B52:K52 (name `dcf_ufcf`)
- **Python:** `valuation.engine.schedule`
- **Reference implementation:** `reference_impl.simple_valuation.one_year`
- **Verified by:** `tests/test_excel_parity.py::test_parity_all_metrics`, `tests/test_reference_agreement.py::test_dcf_agrees`

### `dcf.pv` - Discounting and NPV of Years 1-10

- **Kind:** formula
- **Formula:** PV_t = UFCF_t ÷ (1 + WACC)^(t − ½·mid);   NPV₁₋₁₀ = Σ PV_t
- **Logic:** End-of-year discounting by default; mid-year moves each cash flow half a year earlier.
- **Inputs:** `in_WACC`, `in_Timing`
- **Units:** $M
- **Excel:** 'DCF Model'!B59 (name `dcf_SumPV`)
- **Python:** `valuation.engine.dcf`
- **Reference implementation:** `reference_impl.simple_valuation.enterprise_value`
- **Verified by:** `tests/test_excel_parity.py::test_parity_all_metrics`, `tests/test_checks.py::test_checks_pass_on_ddog`

### `dcf.tv_perpetuity` - Terminal value - Gordon growth

- **Kind:** formula
- **Formula:** TV = UFCF₁₁ ÷ (WACC − g∞),  UFCF₁₁ built explicitly from Rev₁₁ = Rev₁₀(1 + g∞) at the Year-10 margin;  undefined if WACC ≤ g∞
- **Logic:** Value at Year 10 of all cash flows after Year 10, growing forever at g∞. Year 11 is a normalised year with its own working-capital charge.
- **Inputs:** `in_TermG`, `in_WACC`
- **Units:** $M
- **Excel:** 'DCF Model'!B60 (name `dcf_TV`)
- **Python:** `valuation.engine.terminal_value`
- **Reference implementation:** `reference_impl.simple_valuation.enterprise_value`
- **Verified by:** `tests/test_excel_parity.py::test_parity_all_metrics`, `tests/test_edge_cases.py::test_terminal_growth_at_or_above_wacc`
- **Applies when:** in_TVMethod = Perpetuity (Gordon Growth)

### `dcf.tv_exit` - Terminal value - exit multiple

- **Kind:** judgment
- **Formula:** TV = exit multiple × Year-10 metric (EBITDA, UFCF or revenue)
- **Logic:** Sale of the business at the end of Year 10 at a market multiple.
- **Inputs:** `in_ExitMult`, `in_ExitMetric`
- **Units:** $M
- **Excel:** 'DCF Model'!B60 (name `dcf_TV`)
- **Python:** `valuation.engine.terminal_value`
- **Reference implementation:** `reference_impl.simple_valuation.enterprise_value`
- **Verified by:** `tests/test_excel_parity.py::test_parity_all_metrics`
- **Applies when:** in_TVMethod = Exit Multiple

### `dcf.pv_tv` - Present value of terminal value

- **Kind:** formula
- **Formula:** PV(TV) = TV ÷ (1 + WACC)^N,  N = 10 − ½·mid (perpetuity) or 10 (exit multiple)
- **Logic:** A perpetuity follows the cash-flow timing convention; an exit is a sale at the end of Year 10.
- **Inputs:** `dcf_TV`, `in_WACC`
- **Units:** $M
- **Excel:** 'DCF Model'!B62 (name `dcf_PVTV`)
- **Python:** `valuation.engine.dcf`
- **Reference implementation:** `reference_impl.simple_valuation.enterprise_value`
- **Verified by:** `tests/test_excel_parity.py::test_parity_all_metrics`

### `dcf.ev` - Enterprise value

- **Kind:** formula
- **Formula:** EV = NPV₁₋₁₀ + PV(TV)
- **Logic:** Value of the operations.
- **Inputs:** `dcf_SumPV`, `dcf_PVTV`
- **Units:** $M
- **Excel:** 'DCF Model'!B63 (name `dcf_EV`)
- **Python:** `valuation.engine.dcf`
- **Reference implementation:** `reference_impl.simple_valuation.enterprise_value`
- **Verified by:** `tests/test_excel_parity.py::test_ddog_headline_parity`

### `dcf.equity` - Equity value

- **Kind:** formula
- **Formula:** Equity = EV + cash − debt − other claims
- **Logic:** Enterprise-to-equity bridge.
- **Inputs:** `dcf_EV`, `in_NetCash`
- **Units:** $M
- **Excel:** 'DCF Model'!B68 (name `dcf_Equity`)
- **Python:** `valuation.engine.dcf`
- **Reference implementation:** `reference_impl.simple_valuation.dcf`
- **Verified by:** `tests/test_excel_parity.py::test_parity_all_metrics`

### `dcf.fair_value` - Fair value per share

- **Kind:** formula
- **Formula:** Fair value = Equity ÷ diluted shares;  Upside = fair value ÷ price − 1
- **Logic:** Intrinsic value per diluted share.
- **Inputs:** `dcf_Equity`, `in_Shares`, `in_Price`
- **Units:** $/share
- **Excel:** 'DCF Model'!B69 (name `dcf_FV`)
- **Python:** `valuation.engine.dcf`
- **Reference implementation:** `reference_impl.simple_valuation.dcf`
- **Verified by:** `tests/test_excel_parity.py::test_ddog_headline_parity`, `tests/test_reference_agreement.py::test_dcf_agrees`

### `dcf.cross_checks` - Implied exit multiple and implied perpetual growth

- **Kind:** formula
- **Formula:** Implied EV/EBITDA = TV ÷ EBITDA₁₀;   implied g ≈ (TV·WACC − UFCF₁₀) ÷ (TV + UFCF₁₀)
- **Logic:** Translate whichever terminal method you used into the other method's terms.
- **Inputs:** `dcf_TV`, `in_WACC`
- **Units:** x / decimal
- **Excel:** 'DCF Model'!B70 (name `dcf_ImpMult`)
- **Python:** `valuation.engine.dcf`
- **Reference implementation:** `(not re-implemented: pure arithmetic on checked values)`
- **Verified by:** `tests/test_excel_parity.py::test_parity_all_metrics`

### `dcf.sensitivity` - Sensitivity table (fair value per share)

- **Kind:** formula
- **Formula:** Cell(i,j) = [Σ UFCF_t (1+w_i)^−per_t + PV_TV(w_i, p_j) + net cash] ÷ shares;  w_i = WACC + 0.5pp·i, p_j = g∞ + 0.5pp·j (or multiple + 2.5x·j), i,j ∈ −3..3
- **Logic:** Years 1-10 stay fixed; for perpetuity the Year-11 cash flow is rebuilt at each column's growth rate. The centre cell equals the base fair value (checked).
- **Inputs:** `in_WACC`, `in_TermG`, `in_ExitMult`
- **Units:** $/share
- **Excel:** 'DCF Model'!E108 (name `dcf_SensCentre`)
- **Python:** `valuation.engine.dcf_sensitivity`
- **Reference implementation:** `reference_impl.simple_valuation.dcf`
- **Verified by:** `tests/test_excel_parity.py::test_parity_all_metrics`, `tests/test_reference_agreement.py::test_dcf_agrees`

### `dcf.value_over_time` - Value of the company and the share at the end of each year

- **Kind:** formula
- **Formula:** EV_t = Σ_{k>t} UFCF_k ÷ (1+WACC)^(per_k − t) + TV ÷ (1+WACC)^(N − t);  Cash_t = net cash + Σ_{k≤t} UFCF_k (if retained);  Price_t = (EV_t + Cash_t) ÷ (shares × (1 + Δshares)^t)
- **Logic:** What the model says the stock is worth in t years if the forecast is delivered. Holding at fair value earns about the WACC.
- **Inputs:** `dcf_ufcf`, `dcf_TV`, `in_CashRetain`, `in_ShareChg`
- **Units:** $/share
- **Excel:** 'DCF Model'!B80:L80 (name `dcf_PxPath`)
- **Python:** `valuation.engine.value_over_time`
- **Reference implementation:** `(checked against Excel only)`
- **Verified by:** `tests/test_excel_parity.py::test_parity_all_metrics`, `tests/test_checks.py::test_checks_pass_on_ddog`

## Reverse DCF

### `rdcf.target` - Market enterprise value (the target)

- **Kind:** formula
- **Formula:** Market EV = price × diluted shares − net cash
- **Logic:** What the market pays for the operations today.
- **Inputs:** `in_Price`, `in_Shares`, `in_NetCash`
- **Units:** $M
- **Excel:** 'Reverse DCF'!F20 (name `rd_Target`)
- **Python:** `valuation.engine.reverse_dcf`
- **Reference implementation:** `reference_impl.simple_valuation.reverse_dcf`
- **Verified by:** `tests/test_excel_parity.py::test_parity_all_metrics`

### `rdcf.ev_of_g` - Model EV as a function of constant growth g

- **Kind:** formula
- **Formula:** EV(g) = Rev₀ Σ_{t=1..10} (1+g)^t [a_t + b·g/(1+g)] (1+WACC)^−P_t + TV(g)·(1+WACC)^−N;   a_t = m_t − t·max(m_t,0) + D&A% − Capex% [+ NWC% if flat];  b = NWC% if incremental
- **Logic:** Same mechanics as the DCF Model with one unknown: a constant revenue growth rate for Years 1-10. Margins follow the forecast path or stay at TTM.
- **Inputs:** `rd_MarginSrc`, `in_WACC`, `in_TermG`
- **Units:** $M
- **Excel:** 'Reverse DCF'!B100:K100 (name `rd_A`)
- **Python:** `valuation.engine.rdcf_ev`
- **Reference implementation:** `reference_impl.simple_valuation.reverse_dcf`
- **Verified by:** `tests/test_excel_parity.py::test_parity_all_metrics`, `tests/test_reference_agreement.py::test_reverse_dcf_agrees`

### `rdcf.solve` - Solving for the implied growth (grid scan + bisection)

- **Kind:** formula
- **Formula:** Scan g = −50%, −49%, …, +150%; take the first bracket where EV(g) − market EV changes sign; halve the bracket 40 times; g* = midpoint of the 40th bracket.  No sign change ⇒ 'No solution in range'
- **Logic:** A macro-free root finder that Excel can run. Multiple sign changes are reported; the lowest root is shown.
- **Inputs:** `rd_Target`
- **Units:** decimal
- **Excel:** 'Reverse DCF'!B14 (name `rd_G`)
- **Python:** `valuation.engine.reverse_dcf`
- **Reference implementation:** `reference_impl.simple_valuation.reverse_dcf`
- **Verified by:** `tests/test_excel_parity.py::test_ddog_headline_parity`, `tests/test_edge_cases.py::test_reverse_dcf_no_solution`

### `rdcf.proof` - Proof schedule and tie-out

- **Kind:** formula
- **Formula:** Rebuild Years 1-11 at g*;  tie-out = Σ PV + PV(TV) − market EV ≈ 0
- **Logic:** The answer is only trusted if the full schedule at g* reproduces market EV.
- **Inputs:** `rd_G`
- **Units:** $M
- **Excel:** 'Reverse DCF'!B51 (name `rd_TieOut`)
- **Python:** `valuation.engine.reverse_dcf`
- **Reference implementation:** `reference_impl.simple_valuation.reverse_dcf`
- **Verified by:** `tests/test_checks.py::test_checks_pass_on_ddog`, `tests/test_excel_parity.py::test_parity_all_metrics`

### `rdcf.gap` - Expectation gap

- **Kind:** formula
- **Formula:** Gap = g* − your forecast's 10-year revenue CAGR,  CAGR = (Rev₁₀ ÷ Rev₀)^(1/10) − 1
- **Logic:** Positive = the market expects more growth than your forecast.
- **Inputs:** `rd_G`, `dcf_rev`
- **Units:** decimal
- **Excel:** 'Reverse DCF'!B26 (name `rd_Gap`)
- **Python:** `valuation.engine.reverse_dcf`
- **Reference implementation:** `(arithmetic on checked values)`
- **Verified by:** `tests/test_excel_parity.py::test_parity_all_metrics`

## IRR

### `irr.metric_path` - Metric path for the chosen multiple

- **Kind:** formula
- **Formula:** Metric_t = DCF line at Year t (trailing) or t+1 (forward); EPS scales net income on the selected basis by NOPAT_t ÷ NOPAT₀ (revenue ratio if either is ≤ 0); gross profit and book value scale with revenue; DPS grows at the dividend growth rate
- **Logic:** Every IRR metric comes from the same forecast as the DCF.
- **Inputs:** `irr_Mult`, `irr_Basis`, `irr_GSrc`, `irr_GMan`
- **Units:** $M / $ per share
- **Excel:** 'IRR Analysis'!B21 (name `irr_EntryPS`)
- **Python:** `valuation.engine.irr_analysis`
- **Reference implementation:** `reference_impl.simple_valuation.irr`
- **Verified by:** `tests/test_excel_parity.py::test_parity_all_metrics`, `tests/test_reference_agreement.py::test_irr_agrees`

### `irr.entry_multiple` - Entry multiple

- **Kind:** formula
- **Formula:** P multiples: price ÷ metric/share;  EV multiples: (price − net cash/share) ÷ metric/share;  yields: metric/share ÷ price
- **Logic:** Computed from today's price so it always reconciles; not meaningful (n/m) when the metric is ≤ 0.
- **Inputs:** `in_Price`, `in_NetCashPS`
- **Units:** x
- **Excel:** 'IRR Analysis'!B14 (name `irr_Entry`)
- **Python:** `valuation.engine.irr_analysis`
- **Reference implementation:** `reference_impl.simple_valuation.irr`
- **Verified by:** `tests/test_excel_parity.py::test_parity_all_metrics`

### `irr.exit_price` - Exit price

- **Kind:** formula
- **Formula:** Exit price_H = exit multiple × metric/share_H [+ net cash/share_H for EV multiples];  yields: metric/share ÷ exit yield
- **Logic:** Exit multiple defaults to today's multiple (no re-rating). Net cash is held constant or grows with retained FCF less dividends.
- **Inputs:** `irr_Exit`, `irr_H`, `irr_Cash`, `irr_S`
- **Units:** $/share
- **Excel:** 'IRR Analysis'!B44 (name `irr_ExitPx`)
- **Python:** `valuation.engine.irr_analysis`
- **Reference implementation:** `reference_impl.simple_valuation.irr`
- **Verified by:** `tests/test_excel_parity.py::test_parity_all_metrics`

### `irr.irr` - IRR (annualized return incl. dividends)

- **Kind:** formula
- **Formula:** Find r with −P₀ + Σ_{t<H} DPS_t/(1+r)^t + (DPS_H + exit price_H)/(1+r)^H = 0
- **Logic:** Excel IRR() on per-share cash flows. Not meaningful when the exit price is ≤ 0 or the multiple is n/m.
- **Inputs:** `irr_ExitPx`, `in_Price`, `d_dps`, `irr_DG`
- **Units:** decimal per year
- **Excel:** 'IRR Analysis'!B16 (name `irr_IRR`)
- **Python:** `valuation.engine.excel_irr`
- **Reference implementation:** `reference_impl.simple_valuation.irr_bisect`
- **Verified by:** `tests/test_excel_parity.py::test_ddog_headline_parity`, `tests/test_edge_cases.py::test_zero_dividend_irr`

### `irr.sensitivity` - IRR sensitivity (entry × exit multiple)

- **Kind:** formula
- **Formula:** Cell(i,j) = ((exit price(j) + cumulative dividends) ÷ entry price(i))^(1/H) − 1, multiples × 0.7…1.3
- **Logic:** Simple (not reinvested) annualized return; the centre equals the IRR when there are no dividends.
- **Inputs:** `irr_Entry`, `irr_Exit`
- **Units:** decimal per year
- **Excel:** 'IRR Analysis'!E52 (name `irr_SensCentre`)
- **Python:** `valuation.engine.irr_analysis`
- **Reference implementation:** `(checked against Excel only)`
- **Verified by:** `tests/test_excel_parity.py::test_parity_all_metrics`

## Units

### `units.convert` - Unit conversion

- **Kind:** formula
- **Formula:** $M = $K ÷ 1,000 = $B × 1,000
- **Logic:** The engine works in $ millions and millions of shares; per-share values are unit-free (checked live).
- **Inputs:** -
- **Units:** $M
- **Excel:** 'Start Here & Guide'!B19 (name `in_Cash`)
- **Python:** `valuation.units.to_millions`
- **Reference implementation:** `(n/a)`
- **Verified by:** `tests/test_edge_cases.py::test_units_round_trip`, `tests/test_edge_cases.py::test_units_scale_invariance`

## Output chains (Logic page)

- **Fair value per share:** `data.ebit_margin` → `defaults.ratios` → `wacc.active` → `fc.auto` → `dcf.revenue` → `dcf.nopat` → `dcf.ufcf` → `dcf.pv` → `dcf.tv_perpetuity` → `dcf.tv_exit` → `dcf.pv_tv` → `dcf.ev` → `dcf.equity` → `dcf.fair_value`
- **Enterprise value:** `dcf.pv` → `dcf.tv_perpetuity` → `dcf.tv_exit` → `dcf.pv_tv` → `dcf.ev`
- **WACC:** `wacc.ke` → `wacc.kd` → `wacc.weights` → `wacc.capm` → `wacc.active`
- **Terminal value:** `dcf.tv_perpetuity` → `dcf.tv_exit` → `dcf.pv_tv` → `dcf.cross_checks`
- **Value over time:** `dcf.value_over_time`
- **Sensitivity:** `dcf.sensitivity`
- **Implied growth (Reverse DCF):** `rdcf.target` → `rdcf.ev_of_g` → `rdcf.solve` → `rdcf.proof` → `rdcf.gap`
- **IRR:** `irr.metric_path` → `irr.entry_multiple` → `irr.exit_price` → `irr.irr` → `irr.sensitivity`
- **Data bridge:** `data.ttm` → `data.nongaap_adj` → `data.ebit_margin` → `data.da_used` → `data.capex` → `data.nwc_resid` → `data.net_cash` → `defaults.g1` → `defaults.ratios`
