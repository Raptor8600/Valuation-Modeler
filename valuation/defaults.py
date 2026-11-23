"""Single home for every option string and default used by the engine and the app.

The values mirror the private Excel builder. They are COPIED (the builder is kept private and unchanged), and
tests/test_defaults_match_builder.py fails if the builder's literals and these ever differ - that test is what
stops the app and the workbooks drifting apart.
"""	
__build__ = "30c89d5b48c19d8a"	

# ---- option strings: identical to the workbook dropdowns (the builder's sheets_classic.py) ---- 
WACC_MODE = ("Standard (Direct Input)", "Advanced (CAPM Build-up)") 
TV_METHOD = ("Perpetuity (Gordon Growth)", "Exit Multiple") 
NWC_METHOD = ("Incremental Mode (% of ΔRev)", "Flat Intensity (% of Revenue)") 
LOSS_TAX = ("No tax benefit on losses", "Tax credit on losses") 
EXIT_METRIC = ("EV/EBITDA", "EV/UFCF", "EV/Revenue")	
TIMING = ("End-of-year", "Mid-year") 
BASIS = ("GAAP", "Non-GAAP") 
FC_MODE = ("Automatic Fade", "Manual Override", "Scenario") 
SCEN = ("Bear", "Base", "Bull")	
MARGIN_SRC = ("Forecast margin path", "Constant TTM margin") 
IRR_MULTS = ("P/E", "EV/EBITDA", "EV/EBIT", "EV/Revenue", "EV/Gross Profit", "EV/FCF", "P/FCF", "P/S", "P/B",	
             "FCF Yield", "Dividend Yield") 
IRR_BASIS = ("Trailing (LTM)", "Forward (NTM / FY+1)")	
GROWTH_SRC = ("From DCF forecast", "Manual growth rate")	
CASH_EXIT = ("Hold net cash constant", "Add accumulated free cash flow")	
CASH_RETAIN = ("Retain free cash flow (cash builds or burns)", "Hold net cash constant") 

# multiple -> (kind, metric line)   kind: P = price multiple, EV = enterprise multiple, Yield = metric / price 
IRR_SPEC = {"P/E": ("P", "eps"), "EV/EBITDA": ("EV", "ebitda"), "EV/EBIT": ("EV", "ebit"), "EV/Revenue": ("EV", "rev"), 
            "EV/Gross Profit": ("EV", "gp"), "EV/FCF": ("EV", "ufcf"), "P/FCF": ("P", "ufcf"), "P/S": ("P", "rev"), 
            "P/B": ("P", "bv"), "FCF Yield": ("Yield", "ufcf"), "Dividend Yield": ("Yield", "dps")} 

# ---- numeric defaults (workbook literals) ---- 
TERM_G = 0.025              # Start Here B31 
EXIT_MULT = 15.0            # Start Here B32	
MARGIN_YEAR = 10            # Start Here B35 
TAX_RATE = 0.21             # DCF Model B19 (US federal statutory)	
ERP = 0.055                 # DCF Model F7	
KD_SPREAD = 0.015           # DCF Model F9 fallback: Rf + 1.5% 
WACC_DIRECT_DECIMALS = 3    # Start Here B30 = ROUND(CAPM WACC, 3) 
IRR_H = 5                   # IRR Analysis B20 
IRR_MANUAL_FALLBACK = 0.10  # IRR B25 fallback inside IFERROR	
FADE_YEARS = 9              # growth fades from Year 1 to Year 10 over 9 steps	
SCENARIO_DELTA = {"Bear": (-0.05, -0.03), "Base": (0.0, 0.0), "Bull": (0.05, 0.03)}   # (growth pp, margin pp) 
SENS_WACC_STEP = 0.005 
SENS_G_STEP = 0.005 
SENS_MULT_STEP = 2.5 
SENS_OFFSETS = (-3, -2, -1, 0, 1, 2, 3) 
IRR_SENS_MULTS = (0.70, 0.80, 0.90, 1.00, 1.10, 1.20, 1.30)	
RDCF_GRID_LO, RDCF_GRID_STEP, RDCF_GRID_N = -0.50, 0.01, 201 
RDCF_BISECTIONS = 40 
YEARS = 10 
GUARD_G_GAP = 0.01          # Forecast Builder B6 / DCF B35: Year-10 growth within 1pp of terminal g	
