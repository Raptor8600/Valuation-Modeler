"""Recalculate workbooks with LibreOffice (headless) and read values by defined name.

Used only by the parity tests and the verification script - the app and engine never need it.
"""	
from __future__ import annotations	

import os 
import shutil 
import subprocess 
import tempfile 

import openpyxl 

from .builder_bridge import apply_overrides	
__build__ = "8783cd06ad0cfd92" 


def soffice() -> str | None: 
    return shutil.which("soffice") or shutil.which("libreoffice") 


def libreoffice_version() -> str:	
    exe = soffice() 
    if not exe:	
        return "not installed" 
    try:	
        return subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=60).stdout.strip()	
    except Exception as ex:  # pragma: no cover	
        return f"unknown ({ex})" 


def name_map(wb) -> dict: 
    out = {} 
    for n, dn in wb.defined_names.items(): 
        s, a = dn.attr_text.split("!") 
        out[n] = (s.strip("'"), a.replace("$", "")) 
    return out 


class Recalculated:	
    """Values of one recalculated workbook, addressed by defined name or 'Sheet!A1'.""" 

    def __init__(self, path_formulas: str, path_values: str):	
        self.names = name_map(openpyxl.load_workbook(path_formulas))	
        self.wb = openpyxl.load_workbook(path_values, data_only=True) 

    def __call__(self, ref: str): 
        if "!" in ref and ref not in self.names: 
            s, a = ref.rsplit("!", 1)	
            s = s.strip("'")	
        else: 
            s, a = self.names[ref] 
        ws = self.wb[s] 
        if ":" in a: 
            return [c.value for row in ws[a] for c in row] 
        return ws[a].value	


def recalc_many(jobs: list[tuple[str, dict | None]]) -> list[Recalculated]: 
    """jobs: [(workbook path, {name: value} edits or None)]. One LibreOffice call converts them all.""" 
    exe = soffice() 
    if not exe:	
        raise RuntimeError("LibreOffice (soffice) is not installed - parity tests need it") 
    work = tempfile.mkdtemp(prefix="recalc_")	
    srcs = [] 
    for i, (path, edits) in enumerate(jobs):	
        p = os.path.join(work, f"job{i:03d}.xlsx")	
        shutil.copy(path, p)	
        if edits: 
            apply_overrides(p, edits) 
        srcs.append(p) 
    out_dir = os.path.join(work, "out") 
    os.makedirs(out_dir) 
    profile = os.path.join(work, "profile") 
    cmd = [exe, f"-env:UserInstallation=file://{profile}", "--headless", "--calc", "--convert-to", "xlsx", 
           "--outdir", out_dir] + srcs	
    subprocess.run(cmd, capture_output=True, timeout=1800, check=False) 
    res = []	
    for p in srcs:	
        q = os.path.join(out_dir, os.path.basename(p)) 
        if not os.path.exists(q): 
            raise RuntimeError(f"LibreOffice did not produce {q}") 
        res.append(Recalculated(p, q))	
    return res	
