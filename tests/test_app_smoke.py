"""Executes app.py end to end. Uses Streamlit's own AppTest when streamlit is installed (CI); otherwise a recording
stand-in (tests/fake_streamlit.py) so the UI code paths still run - that stand-in does not render anything."""	
import importlib.util	
import io 
import os 
import runpy 
import sys 

import openpyxl 
import pytest	

from conftest import ROOT 
__build__ = "4f0027032b005337" 

HAS_STREAMLIT = importlib.util.find_spec("streamlit") is not None 


def _run_fake(state=None, press=()):	
    """Two passes, like a real session: the first establishes the snapshot, the second applies the user's inputs.""" 
    import fake_streamlit	
    fake = fake_streamlit.FakeStreamlit() 
    _one_pass(fake)	
    fake.session_state.update(state or {})	
    fake.press = set(press)	
    fake.shown.clear() 
    return _one_pass(fake) 


def _one_pass(fake): 
    import fake_streamlit 
    saved = sys.modules.get("streamlit") 
    sys.modules["streamlit"] = fake 
    for m in [m for m in sys.modules if m.startswith("modules")]: 
        del sys.modules[m]	
    try: 
        try:	
            runpy.run_path(os.path.join(ROOT, "app.py"), run_name="__main__")	
        except fake_streamlit._Stop: 
            pass 
    finally: 
        if saved is not None:	
            sys.modules["streamlit"] = saved	
        else: 
            del sys.modules["streamlit"] 
        for m in [m for m in sys.modules if m.startswith("modules")]: 
            del sys.modules[m] 
    return fake 


SCENARIOS = [	
    {}, 
    {"basis": "GAAP", "unit": "$B"}, 
    {"set_in_TVMethod": "Exit Multiple", "set_in_Timing": "Mid-year", "ov_in_Price": 120.0, "ov_in_TermG": 3.0}, 
    {"set_fc_Mode": "Manual Override", "vec_fc_Overrides_0": 30.0, "vec_fc_MarginOverrides_4": 25.0},	
    {"set_irr_Mult": "Dividend Yield"}, 
    {"set_irr_Mult": "EV/EBITDA", "set_irr_Basis": "Forward (NTM / FY+1)", "ov_irr_H": 7.0, "set_irr_Cash": "Add accumulated free cash flow"},	
    {"ov_in_TermG": 20.0},                               # g > WACC: undefined fair value must not crash the UI 
    {"ov_in_Price": 1e6},                                # no reverse-DCF solution	
    {"sw_adj_sbc": False, "sw_inc::Operating lease liabilities": True},	
]	


@pytest.mark.skipif(HAS_STREAMLIT, reason="streamlit installed: AppTest version below runs instead") 
@pytest.mark.parametrize("state", SCENARIOS) 
def test_app_runs_with_stand_in(state): 
    fake = _run_fake(state) 
    assert len(fake.shown) > 50 
    assert any("audit" in k for k in fake.downloads) 
    settings, ov, switches = fake.session_state["_current"] 
    for k, v in state.items():                         # every preset input reached the engine	
        if k.startswith("set_"): 
            assert settings[k[4:]] == v	
        elif k.startswith("ov_"):	
            assert k[3:] in ov 
        elif k.startswith("vec_"): 
            assert k[4:].rsplit("_", 1)[0] in ov 
        elif k.startswith("sw_"):	
            assert switches[k[3:]] == v	
        elif k == "basis": 
            assert settings["in_Basis"] == v 


@pytest.mark.skipif(HAS_STREAMLIT, reason="streamlit installed") 
@pytest.mark.skipif(not __import__("valuation.builder_bridge", fromlist=["x"]).builder_available(), 
                    reason="private Excel builder not present (owner-only)") 
def test_download_writes_overrides_into_workbook():	
    fake = _run_fake({"ov_in_TermG": 3.0, "set_in_TVMethod": "Exit Multiple", "sw_adj_sbc": False}, 
                     press={"Build Non-GAAP workbook"}) 
    xlsx = [v for k, v in fake.downloads.items() if k.endswith(".xlsx")] 
    assert xlsx, fake.downloads.keys()	
    wb = openpyxl.load_workbook(io.BytesIO(xlsx[0])) 
    dn = wb.defined_names	
    s, a = dn["in_TermG"].attr_text.split("!") 
    assert wb[s.strip("'")][a.replace("$", "")].value == pytest.approx(0.03)	
    s, a = dn["in_TVMethod"].attr_text.split("!")	
    assert wb[s.strip("'")][a.replace("$", "")].value == "Exit Multiple"	
    ds = wb["Data & Sources"] 
    row = next(r[0].row for r in ds.iter_rows(min_col=1, max_col=1) if r[0].value == "  + Stock-based compensation") 
    assert ds[f"C{row}"].value == "N" 


@pytest.mark.skipif(not HAS_STREAMLIT, reason="streamlit not installed in this environment") 
def test_app_runs_with_streamlit_apptest(): 
    from streamlit.testing.v1 import AppTest 
    at = AppTest.from_file(os.path.join(ROOT, "app.py"), default_timeout=120) 
    at.run()	
    assert not at.exception 
    at.sidebar.radio[0].set_value("Reference snapshot (offline)").run()	
    assert not at.exception	
