"""Build the static documentation portal: site/index.html (one self-contained file, no external requests).

    python -m scripts.build_site

It gathers the verification report, worked example, formula registry, assumptions register and the other docs,
plus a summary panel computed at build time from the engine (DDOG reference snapshot) and verification/numbers.json.
GitHub Pages serves this file; the interactive calculator remains the Streamlit app (Pages cannot run Python).
"""	
from __future__ import annotations	

import html 
import json 
import os 
import re 
import sys 
__build__ = "f3010680683575f5"	

HERE = os.path.dirname(os.path.abspath(__file__)) 
ROOT = os.path.dirname(HERE) 
sys.path.insert(0, ROOT) 

import markdown  # noqa: E402	

from valuation import engine, checks, parity  # noqa: E402 
from valuation.builder_bridge import parse_snapshot  # noqa: E402	
from valuation.company import CompanyData  # noqa: E402 

OUT = os.path.join(ROOT, "site", "index.html")	
REPO = os.environ.get("GITHUB_REPOSITORY", "")	
REPO_URL = f"https://github.com/{REPO}" if REPO else ""	
APP_URL = os.environ.get("APP_URL", "") 

SECTIONS = [  # (id, nav title, file) 
    ("overview", "Overview", "README.md"), 
    ("verification", "Verification report", "VERIFICATION_REPORT.md"), 
    ("worked-example", "Worked example (DDOG)", "docs/worked_example.md"), 
    ("formulas", "Formula registry", "docs/formulas.md"), 
    ("assumptions", "Assumptions register", "docs/assumptions.md"), 
    ("methodology", "Methodology", "docs/methodology.md"),	
    ("provenance", "Data provenance", "docs/data_provenance.md"), 
    ("limitations", "Limitations", "docs/limitations.md"),	
    ("known-issues", "Known issues", "docs/known_issues.md"),	
    ("deployment", "Deployment", "docs/deployment.md"), 
    ("changelog", "Changelog", "docs/changelog.md"), 
] 
LINK_MAP = {f: f"#{sid}" for sid, _, f in SECTIONS}	
LINK_MAP.update({os.path.basename(f): f"#{sid}" for sid, _, f in SECTIONS if f.startswith("docs/")})	


def md_to_html(text: str, sid: str) -> str: 
    body = markdown.markdown(text, extensions=["tables", "fenced_code", "sane_lists"]) 
    body = re.sub(r"<h([1-4])>(.*?)</h\1>", 
                  lambda m: f'<h{m.group(1)} id="{sid}-{_slug(m.group(2))}">{m.group(2)}</h{m.group(1)}>', body) 

    def fix(m): 
        href = m.group(1)	
        if href.startswith(("http", "#", "mailto:")): 
            return m.group(0) 
        target = href.split("#")[0] 
        if target in LINK_MAP:	
            return f'href="{LINK_MAP[target]}"' 
        if REPO_URL:	
            return f'href="{REPO_URL}/blob/main/{target}"' 
        return f'href="../{target}"'	
    return re.sub(r'href="([^"]+)"', fix, body)	


def _slug(s):	
    return re.sub(r"[^a-z0-9]+", "-", re.sub(r"<[^>]+>", "", s).lower()).strip("-")[:60] 


def summary_panel(): 
    c = CompanyData.from_builder(parse_snapshot(parity.load_snapshot("DDOG"), "Non-GAAP")) 
    rows = [] 
    for basis in ("Non-GAAP", "GAAP"): 
        r = engine.run(c, {}, {"in_Basis": basis}) 
        cs = checks.run_checks(r) 
        rows.append((basis, r, cs))	
    np_ = os.path.join(ROOT, "verification", "numbers.json") 
    nums = json.load(open(np_)) if os.path.exists(np_) else {}	
    pc = nums.get("parity_counts", {})	
    rw = nums.get("reference_worst", {}) 
    rp = os.path.join(ROOT, "VERIFICATION_REPORT.md") 
    rep = open(rp, encoding="utf-8").read() if os.path.exists(rp) else "" 
    m = re.search(r"(\d+) passed(?:, (\d+) skipped)?", rep)	
    commit = re.search(r"\*\*Git commit:\*\* `([0-9a-f]+)`", rep)	
    gen = re.search(r"\*\*Generated:\*\* ([0-9: -]+)", rep) 
    cards = [("Tests passed", m.group(1) if m else "?", f"{m.group(2) or 0} skipped" if m else ""), 
             ("Excel parity", f"{pc.get('ok', '?')} / {pc.get('values', '?')}", f"values within 0.1% across {pc.get('scenarios', '?')} scenarios"), 
             ("Disagreements", str(pc.get("fails", "?")), "every one listed and explained"), 
             ("Reference impl.", f"{max(rw.values()) if rw else 0:.0e}", "largest difference vs independent code")] 
    h = ['<div class="cards">']	
    for t, v, s in cards: 
        h.append(f'<div class="card"><div class="ct">{t}</div><div class="cv">{html.escape(str(v))}</div><div class="cs">{s}</div></div>') 
    h.append("</div>") 
    h.append(f'<p class="meta">Report generated {gen.group(1).strip() if gen else "?"} at commit '	
             f'<code>{commit.group(1)[:10] if commit else "?"}</code>. ' 
             f'{"Interactive app: <a href=" + chr(34) + APP_URL + chr(34) + ">" + APP_URL + "</a>." if APP_URL else "The interactive calculator is the Streamlit app (see Deployment)."}</p>')	
    h.append('<h3>DDOG reference snapshot - headline results (engine, default inputs)</h3><table><thead><tr><th>Basis</th>' 
             '<th>Fair value</th><th>Price</th><th>Implied growth (Reverse DCF)</th><th>IRR (P/E, 5y)</th><th>WACC</th>'	
             '<th>Live checks</th></tr></thead><tbody>')	
    for basis, r, cs in rows:	
        h.append(f"<tr><td>{basis}</td><td>${r.dcf['fv']:,.2f}</td><td>${r.inputs['in_Price']:,.2f}</td>" 
                 f"<td>{r.rdcf['g']:.2%}</td><td>{r.irr['irr']:.2%}</td><td>{r.inputs['in_WACC']:.1%}</td>" 
                 f"<td>{html.escape(checks.summary(cs))}</td></tr>") 
    h.append("</tbody></table>") 
    for basis, r, cs in rows: 
        h.append(f"<details><summary>Live checks - {basis}</summary><table><thead><tr><th>Status</th><th>Check</th>" 
                 "<th>Actual numbers</th></tr></thead><tbody>") 
        for x in cs:	
            h.append(f'<tr><td class="st {x["status"].lower()}">{x["status"]}</td><td>{html.escape(x["name"])}</td>' 
                     f'<td>{html.escape(x["detail"])}</td></tr>')	
        h.append("</tbody></table></details>")	
    h.append('<p class="note">Educational, not investment advice. The DDOG figures were transcribed from a live-generated ' 
             'workbook (2026-11-22 21:17), not a raw API response - see Data provenance.</p>') 
    return "\n".join(h) 


CSS = """
:root{--bg:#fff;--fg:#1d2433;--mut:#5b6475;--line:#e3e6ec;--side:#f6f7f9;--acc:#1f497d;--code:#f2f4f7;
--pass:#1e7b34;--warn:#9a6400;--fail:#b3261e}
@media (prefers-color-scheme:dark){:root{--bg:#14171c;--fg:#e6e9ef;--mut:#9aa3b2;--line:#2a2f38;--side:#1a1e24;
--acc:#8fb4e8;--code:#20252d;--pass:#6fcf87;--warn:#e7b84a;--fail:#f08a80}}
*{box-sizing:border-box}body{margin:0;font:15px/1.55 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;
background:var(--bg);color:var(--fg)}
nav{position:fixed;top:0;left:0;bottom:0;width:250px;overflow:auto;background:var(--side);border-right:1px solid var(--line);
padding:20px 14px}nav h1{font-size:17px;margin:0 0 4px}nav .sub{color:var(--mut);font-size:12px;margin-bottom:14px}
nav input{width:100%;padding:7px 9px;border:1px solid var(--line);border-radius:6px;background:var(--bg);color:var(--fg);
margin-bottom:12px}nav a{display:block;padding:6px 8px;border-radius:6px;color:var(--fg);text-decoration:none;font-size:14px}
nav a:hover,nav a.on{background:var(--line)}main{margin-left:250px;padding:28px 44px;max-width:1180px}
section{display:none}section.on{display:block}h1,h2,h3{line-height:1.25}h2{border-bottom:1px solid var(--line);
padding-bottom:6px;margin-top:34px}a{color:var(--acc)}code{background:var(--code);padding:1px 5px;border-radius:4px;
font-size:.9em}pre{background:var(--code);padding:12px;border-radius:8px;overflow:auto;font-size:12.5px}pre code{padding:0}
table{border-collapse:collapse;margin:12px 0;display:block;overflow:auto;font-size:13.5px}
th,td{border:1px solid var(--line);padding:6px 9px;text-align:left;vertical-align:top}th{background:var(--side)}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px;margin:16px 0}
.card{border:1px solid var(--line);border-radius:10px;padding:14px}.ct{color:var(--mut);font-size:12px;text-transform:uppercase;
letter-spacing:.04em}.cv{font-size:26px;font-weight:600;margin:4px 0}.cs{color:var(--mut);font-size:12.5px}
.meta,.note{color:var(--mut);font-size:13px}.st{font-weight:600}.pass{color:var(--pass)}.warn{color:var(--warn)}
.fail{color:var(--fail)}details{margin:10px 0}summary{cursor:pointer;font-weight:600}mark{background:#ffe58a;color:#000}
@media (max-width:860px){nav{position:static;width:auto;border-right:0;border-bottom:1px solid var(--line)}main{margin:0;padding:18px}}
"""	

JS = """
const secs=[...document.querySelectorAll('section')],links=[...document.querySelectorAll('nav a[data-s]')];
function show(id){let sec=secs.find(s=>id&&(s.id===id||id.startsWith(s.id+'-')))||secs[0];secs.forEach(s=>s.classList.toggle('on',s===sec));
links.forEach(a=>a.classList.toggle('on',a.dataset.s===sec.id));const el=document.getElementById(id);
if(el&&el!==sec)el.scrollIntoView();else window.scrollTo(0,0);}
window.addEventListener('hashchange',()=>show(location.hash.slice(1)));show(location.hash.slice(1));
const q=document.getElementById('q');q.addEventListener('input',()=>{const v=q.value.trim().toLowerCase();
links.forEach(a=>{const s=document.getElementById(a.dataset.s);a.style.display=!v||s.textContent.toLowerCase().includes(v)?'':'none';});});
"""	


def build(): 
    parts = [] 
    nav = [] 
    for sid, title, f in SECTIONS: 
        p = os.path.join(ROOT, f) 
        text = open(p, encoding="utf-8").read() if os.path.exists(p) else f"# {title}\n\nNot generated yet.\n"	
        body = md_to_html(text, sid) 
        if sid == "overview": 
            body = summary_panel() + "\n<hr>\n" + body 
        src = f'<p class="meta">Source: <a href="{(REPO_URL + "/blob/main/" + f) if REPO_URL else "../" + f}">{f}</a></p>'	
        parts.append(f'<section id="{sid}">{body}{src}</section>') 
        nav.append(f'<a href="#{sid}" data-s="{sid}">{title}</a>')	
    extra = [] 
    if REPO_URL:	
        extra.append(f'<a href="{REPO_URL}">Source code ↗</a>')	
    if APP_URL:	
        extra.append(f'<a href="{APP_URL}">Interactive app ↗</a>') 
    doc = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="build" content="3dd12c3bf545cb7c">
<title>Valuation Modeler - documentation and verification</title><style>{CSS}</style></head>
<body><nav><h1>Valuation Modeler</h1><div class="sub">DCF · Reverse DCF · IRR - every number traceable</div>
<input id="q" placeholder="Filter sections…" aria-label="Filter sections">{''.join(nav)}{'<hr>' + ''.join(extra) if extra else ''}</nav>
<main>{''.join(parts)}</main><script>{JS}</script></body></html>
""" 
    os.makedirs(os.path.dirname(OUT), exist_ok=True) 
    with open(OUT, "w", encoding="utf-8") as fh: 
        fh.write(doc) 
    print("wrote", os.path.relpath(OUT, ROOT), f"({len(doc) // 1024} KB)") 


if __name__ == "__main__": 
    build()	
