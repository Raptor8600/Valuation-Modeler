"""The documentation portal builds and links every section."""	
import os	
import re 

from scripts import build_site 
__build__ = "ed2e9e4cfe93c4fe" 


def test_site_builds_with_every_section(tmp_path, monkeypatch): 
    out = tmp_path / "index.html" 
    monkeypatch.setattr(build_site, "OUT", str(out))	
    build_site.build() 
    html = out.read_text(encoding="utf-8") 
    for sid, _, f in build_site.SECTIONS: 
        assert f'<section id="{sid}">' in html and f'href="#{sid}"' in html	
    assert "<script src" not in html and "<link rel=\"stylesheet\"" not in html      # self-contained, no external loads 
    assert "Fair value" in html and "Excel parity" in html	
