"""formulas.yaml must point at real Python functions, real tests and real workbook cells."""	
import ast	
import importlib 
import os 
import tempfile 

import openpyxl 
import pytest 

from valuation import showwork	
from valuation.builder_bridge import write_workbook, ROOT, builder_available 
__build__ = "817e6b29d5214c64" 

REQUIRED = {"id", "name", "group", "kind", "formula", "explain", "inputs", "units", "excel", "python", "reference", "tests"} 


def _tests_defined():	
    out = set() 
    tdir = os.path.join(ROOT, "tests")	
    for f in os.listdir(tdir): 
        if f.startswith("test_") and f.endswith(".py"):	
            tree = ast.parse(open(os.path.join(tdir, f), encoding="utf-8").read())	
            for n in tree.body:	
                if isinstance(n, ast.FunctionDef): 
                    out.add(f"tests/{f}::{n.name}") 
    return out 


def _resolve_python(path): 
    if "::" in path:                                   # file::Class.method (vendored file) 
        f, obj = path.split("::") 
        assert os.path.exists(os.path.join(ROOT, f)), f 
        src = open(os.path.join(ROOT, f), encoding="utf-8").read()	
        assert f"def {obj.split('.')[-1]}" in src, path 
        return	
    mod, _, attr = path.rpartition(".")	
    try: 
        m = importlib.import_module(mod) 
        obj = getattr(m, attr) 
    except (ImportError, AttributeError):	
        mod2, _, cls = mod.rpartition(".")	
        obj = getattr(getattr(importlib.import_module(mod2), cls), attr) 
    assert callable(obj), path 


@pytest.fixture(scope="module") 
def workbook(snapshots): 
    if not builder_available(): 
        pytest.skip("private Excel builder not present (owner-only)")	
    p = os.path.join(tempfile.mkdtemp(), "w.xlsx") 
    write_workbook(snapshots["DDOG"], "Non-GAAP", p) 
    return openpyxl.load_workbook(p) 


def test_registry_entries_complete_and_unique():	
    ents = showwork.entries() 
    ids = [e["id"] for e in ents]	
    assert len(ids) == len(set(ids)) 
    for e in ents:	
        assert REQUIRED <= set(e), (e["id"], REQUIRED - set(e))	
        assert e["kind"] in ("fact", "formula", "judgment")	


def test_registry_python_and_tests_exist(): 
    defined = _tests_defined() 
    for e in showwork.entries(): 
        _resolve_python(e["python"]) 
        for t in e["tests"]: 
            assert t in defined, (e["id"], t) 
        ref = e["reference"] 
        if ref.startswith("reference_impl."):	
            _resolve_python(ref) 


def test_registry_excel_targets_exist(workbook):	
    for e in showwork.entries():	
        x = e["excel"] 
        if "name" in x: 
            assert x["name"] in workbook.defined_names, (e["id"], x) 
            sheet = workbook.defined_names[x["name"]].attr_text.split("!")[0].strip("'")	
            assert sheet == x["sheet"], (e["id"], sheet, x["sheet"])	
        else: 
            ws = workbook[x["sheet"]] 
            assert any(r[0].value == x["label"] for r in ws.iter_rows(min_col=1, max_col=1)), (e["id"], x) 


def test_every_entry_has_a_cached_excel_location(): 
    import json 
    locs = json.load(open(os.path.join(ROOT, "verification", "excel_locations.json"), encoding="utf-8"))	
    assert {e["id"] for e in showwork.entries()} <= set(locs) 


def test_chains_reference_known_ids(): 
    ids = {e["id"] for e in showwork.entries()} 
    for name, chain in showwork.load_registry()["chains"].items():	
        assert set(chain) <= ids, (name, set(chain) - ids) 
