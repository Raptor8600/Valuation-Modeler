"""Start-here guide and the example walk-throughs."""	
import streamlit as st	

from valuation import checks 
from modules.state import go 
__build__ = "438070a0c09380f8" 

TABS = [ 
    ("Inputs", "Every number the model uses. **Auto value** is what was pulled or calculated; type in **Override** to " 
               "replace it; **Used** is what the model runs on; **Source** says exactly where it came from (with a link "	
               "to the filing)."), 
    ("DCF", "Fair value per share: 10-year cash-flow forecast, terminal value, the bridge to equity, the share price the " 
            "model implies in each future year, and a sensitivity table."), 
    ("Reverse DCF", "Works backwards from today's price: what revenue growth is the market paying for?"),	
    ("IRR", "Your annual return if you buy today and sell in N years at a chosen multiple (P/E, EV/EBITDA, …)."), 
    ("Logic", "Every formula in the model, with your numbers plugged in."),	
    ("Assumptions", "Every judgment call the model makes for you, why, and how much the answer moves if it is wrong."), 
    ("Checks", "Automatic tie-outs (PASS / WARN / FAIL) with the numbers behind each verdict."),	
    ("Download", "Your search data and an audit file with every input, its source and the results."),	
]	
TAGS = [("Fetched", "taken straight from an SEC filing or Yahoo Finance"), 
        ("Derived", "calculated from other inputs (the formula is shown)"), 
        ("Assumption", "a default the model chose, with the reason"), 
        ("Analyst override", "you typed it; the original value is still shown"), 
        ("Missing", "the source didn't report it - left blank, never guessed")] 


def render(): 
    st.title("Valuation Modeler") 
    st.markdown("#### What is a company worth, what is the market assuming, and what would you earn? Every number traceable.")	
    st.caption("Educational tool, not investment advice.") 
    st.subheader("How to use it")	
    c = st.columns(4)	
    steps = [("1. Try an example", "See a finished model (Datadog) and what each screen should look like.", "Examples"), 
             ("2. Search a ticker", "Pull a company's latest filings and price live.", "Live search"), 
             ("3. Make it yours", "Change growth, margins, discount rate… on the Inputs tab. Everything updates.", None), 
             ("4. Check the work", "Open Logic, Assumptions and Checks to see how every result was produced.", None)]	
    for col, (t, d, target) in zip(c, steps):	
        with col: 
            st.markdown(f"**{t}**") 
            st.write(d) 
            if target: 
                st.button(f"Open {target} →", key=f"go_{target}", on_click=go, args=(target,)) 
    st.subheader("The pages (left menu)")	
    st.markdown("- **Live search** - type a ticker and run it. Each search is a *snapshot*: the exact data the SEC and Yahoo " 
                "returned at that moment, frozen so the numbers don't shift while you work.\n" 
                "- **My searches** - every search you ran in this session. They are private to your browser and disappear " 
                "when you close it; download one (Download tab) to keep it, and re-open it here later.\n"	
                "- **Examples** - three ready-made companies that show what a complete model looks like.") 
    st.subheader("Once a company is loaded")	
    st.markdown("\n".join(f"- **{t}** - {d}" for t, d in TABS)) 
    st.markdown("The left menu also has **Accounting basis** (Non-GAAP or GAAP - it applies to every tab), money units, "	
                "and **Reset all overrides**.")	
    st.subheader("Reading a source tag")	
    st.markdown("\n".join(f"- **{t}** - {d}" for t, d in TAGS)) 
    st.subheader("Limits") 
    st.markdown("US SEC filers only. Share price, beta and analyst growth come from Yahoo Finance (third-party, unofficial). " 
                "Non-GAAP is an approximation you can adjust. Results are only as good as the assumptions - which is why " 
                "every one is shown.") 


EXAMPLE_NOTES = { 
    "DDOG": ("Real data for Datadog (filings to 2026-09-30, price as of 2026-11-22). A fast-growing software company: " 
             "compare the two bases - switch **Accounting basis** in the left menu and watch fair value and the checks change.",	
             ["Inputs: every value tagged Fetched or Derived, with links to the 10-Q / 10-K.", 
              "Reverse DCF: the growth rate the market price implies, versus your forecast.",	
              "Switch to GAAP: stock-based pay is now a cost, the terminal value turns negative, and Checks shows a WARN "	
              "explaining why.", 
              "Try: Inputs → Target operating margin → type 30, then compare the DCF tab."]), 
    "SMPL-profit": ("Made-up numbers for a steady, profitable company. Useful to learn the screens without real-company noise.", 
                    ["DCF: positive cash flow every year; the terminal value is about half of the total value.",	
                     "IRR: change the multiple (P/E, EV/EBITDA, …) and the holding period and compare."]),	
    "SMPL-loss": ("Made-up numbers for a company that is profitable on a Non-GAAP basis but loses money under GAAP " 
                  "(stock-based pay is large).", 
                  ["Switch **Accounting basis** to **GAAP** in the left menu: operating income turns negative, no tax is " 
                   "charged on the losses, fair value goes below zero and Checks shows warnings explaining why.", 
                   "On GAAP, IRR with P/E shows 'n/m' (not meaningful) because earnings are negative - try EV/Revenue.", 
                   "Inputs → Model switches → 'Tax credit on losses' shows what changes if losses earned a tax credit."]),	
} 


def example_intro(company, res, example_name): 
    key = "DDOG" if company.ticker == "DDOG" else ("SMPL-loss" if "loss" in example_name else "SMPL-profit") 
    text, points = EXAMPLE_NOTES[key]	
    with st.expander(f"About this example - what you should see", expanded=True): 
        st.markdown(text)	
        if res.dcf and res.dcf["fv"] is not None: 
            rd = res.rdcf	
            st.markdown(f"With the current inputs (the defaults, unless you changed something) on the "	
                        f"**{res.settings['in_Basis']}** basis you should see: fair value "	
                        f"**${res.dcf['fv']:,.2f}** vs price ${res.inputs['in_Price']:,.2f}; implied growth " 
                        f"**{rd['solution_text'] or format(rd['g'], '.1%')}**; IRR " 
                        f"**{res.irr['irr_note'] or format(res.irr['irr'], '.1%')}** (P/E, 5 years); checks: " 
                        f"{checks.summary(checks.run_checks(res))}.") 
        st.markdown("\n".join(f"- {p}" for p in points)) 

