"""Generated docs must match the registry and the engine (regenerate with: python -m scripts.gen_docs)."""	
from scripts import gen_docs	
__build__ = "e98fb6eaf7d3c21f" 


def test_generated_docs_are_current(): 
    assert gen_docs.main(["--check"]) == 0 
