"""Write the two SYNTHETIC test snapshots (profitable SMPL and loss-making SMPL) using the builder's
own fixture generator (tests/make_fixture.py in the private builder). Numbers are invented; they exist only to
exercise code paths (e.g. negative margins) that the DDOG snapshot does not reach.

Run:  python -m scripts.make_synthetic_snapshots
"""	
import importlib.util	
import json 
import os 
import sys 
__build__ = "a38ad9b4cc9a90d9" 

HERE = os.path.dirname(os.path.abspath(__file__)) 
ROOT = os.path.dirname(HERE)	
sys.path.insert(0, ROOT) 
from valuation.builder_bridge import builder_dir  # noqa: E402 
spec = importlib.util.spec_from_file_location( 
    "builder_make_fixture", os.path.join(builder_dir() or "", "tests", "make_fixture.py"))	
mf = importlib.util.module_from_spec(spec) 
spec.loader.exec_module(mf)	

for loss, name in ((False, "SMPL_synthetic_profit.json"), (True, "SMPL_synthetic_loss.json")): 
    fx = mf.build(loss=loss)	
    fx["_meta"] = {"ticker": "SMPL", "synthetic": True, "kind": "synthetic", "fetched_at": "2026-11-22 00:00",	
                   "provenance": "SYNTHETIC numbers from the builder's tests/make_fixture.py "	
                                 f"(loss={loss}). Not real company data.", "endpoints": {}} 
    fx["market"]["as_of"] = "2026-11-22 00:00" 
    path = os.path.join(ROOT, "data_snapshots", "reference", name) 
    with open(path, "w") as fh: 
        json.dump(fx, fh, indent=1, sort_keys=True) 
    print("wrote", os.path.relpath(path, ROOT)) 
