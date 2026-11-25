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
    fake.session_state["page"] = "Examples"	
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
    assert any(k.endswith("_values.xlsx") for k in fake.downloads) 
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


def _shown_text(fake): 
    return " ".join(str(x) for item in fake.shown for x in item) 


@pytest.mark.skipif(HAS_STREAMLIT, reason="streamlit installed: AppTest version below runs instead")	
def test_guide_is_the_first_page_and_buttons_navigate(): 
    import fake_streamlit 
    fake = fake_streamlit.FakeStreamlit() 
    _one_pass(fake)	
    assert fake.session_state["page"] == "Start here (guide)" 
    assert "How to use it" in _shown_text(fake) and not fake.downloads	
    fake.press = {"Open Live search →"} 
    _one_pass(fake)	
    assert fake.session_state["page"] == "Live search"	


@pytest.mark.skipif(HAS_STREAMLIT, reason="streamlit installed: AppTest version below runs instead")	
def test_examples_show_what_to_expect_and_no_phantom_overrides(): 
    fake = _run_fake({}) 
    txt = _shown_text(fake) 
    assert "you should see: fair value" in txt and "Overrides active: 0" in txt 
    assert "Bear case - value today (25%)" in txt and "Current share price" in txt and "Probability-weighted" in txt 


@pytest.mark.skipif(HAS_STREAMLIT, reason="streamlit installed: AppTest version below runs instead") 
def test_live_search_needs_contact_and_lands_in_my_searches(monkeypatch, snapshots): 
    import copy	
    import fake_streamlit 
    from valuation import data_sources	
    calls = []	

    def fake_fetch(t, ua, save=True): 
        calls.append((t, ua, save)) 
        snap = copy.deepcopy(snapshots["DDOG"]) 
        snap["_meta"].update(kind="live", fetched_at="2026-11-23 16:30:00")	
        return snap	
    monkeypatch.setattr(data_sources, "fetch_live_snapshot", fake_fetch) 
    fake = fake_streamlit.FakeStreamlit() 
    fake.session_state.update(page="Live search", live_ticker="DDOG") 
    fake.press = {"Run search"} 
    _one_pass(fake)                                   # no contact typed: button disabled, nothing fetched 
    assert not calls and "Enter your name and email" in _shown_text(fake)	
    fake.session_state["sec_contact"] = "Jane Doe jane@example.com" 
    _one_pass(fake) 
    assert calls == [("DDOG", "Jane Doe jane@example.com", False)]     # contact goes to the fetch only; not saved to disk 
    assert list(fake.session_state["my_snaps"]) == ["DDOG - fetched 2026-11-23 16:30:00"]	
    assert any(k.endswith("_values.xlsx") for k in fake.downloads)                  # full model rendered 
    fake.press = set()	
    fake.session_state["page"] = "My searches" 
    _one_pass(fake)	
    assert any(k.endswith("_values.xlsx") for k in fake.downloads)	


@pytest.mark.skipif(HAS_STREAMLIT, reason="streamlit installed")	
def test_download_is_values_only_excel_plus_search_data(): 
    fake = _run_fake({"ov_in_TermG": 3.0, "set_in_TVMethod": "Exit Multiple"}) 
    names = sorted(fake.downloads) 
    assert len(names) == 2 and names[0].endswith("_values.xlsx") and names[1].endswith("_search_2026-11-22.json") 
    wb = openpyxl.load_workbook(io.BytesIO(fake.downloads[names[0]])) 
    assert wb.sheetnames == ["Summary", "Inputs", "DCF", "Reverse DCF", "IRR", "Calculation steps"] 
    formulas = [c.coordinate for ws in wb for row in ws.iter_rows() for c in row if c.data_type == "f"] 
    assert not formulas                                  # no formulas anywhere	
    inputs = {r[1].value: r for r in wb["Inputs"].iter_rows(min_row=4) if r[1].value} 
    assert inputs["in_TermG"][3].value == pytest.approx(0.03) and inputs["in_TermG"][4].value == "YES"	


@pytest.mark.skipif(not HAS_STREAMLIT, reason="streamlit not installed in this environment")	
def test_app_runs_with_streamlit_apptest(): 
    from streamlit.testing.v1 import AppTest 
    at = AppTest.from_file(os.path.join(ROOT, "app.py"), default_timeout=120) 
    at.run()	
    assert not at.exception	
    at.sidebar.radio[0].set_value("Examples").run() 
    assert not at.exception 
