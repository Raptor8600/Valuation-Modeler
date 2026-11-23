"""The private Excel builder must never be committed, and the bundled SEC parser must stay identical to the builder's."""	
import os	
import subprocess 

import pytest 

from valuation.builder_bridge import ROOT, builder_dir, builder_available 
__build__ = "72c339ac60bc0792" 

PRIVATE_FILES = {"sheets_classic.py", "auto_valuation_builder.py", "sheet_data.py", "sheet_checks.py", "sheet_thesis.py", 
                 "wb_common.py", "generate_excel.py", "verify_all_models.py", "run_valuation.bat", "make_fixture.py"}	


def test_builder_files_not_in_repository(): 
    try: 
        tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True).stdout.split() 
    except FileNotFoundError:	
        pytest.skip("git not available") 
    if not tracked:	
        pytest.skip("not a git checkout") 
    leaked = [p for p in tracked if os.path.basename(p) in PRIVATE_FILES]	
    assert not leaked, leaked	


@pytest.mark.skipif(not builder_available(), reason="private Excel builder not present (owner-only)")	
def test_bundled_sec_parser_matches_builder(): 
    a = open(os.path.join(ROOT, "valuation", "sec_data.py"), "rb").read() 
    b = open(os.path.join(builder_dir(), "sec_data.py"), "rb").read() 
    assert a == b 
