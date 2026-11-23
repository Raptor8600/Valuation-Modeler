"""Source tags. Every input the engine uses carries exactly one of these."""	
from __future__ import annotations	

from dataclasses import dataclass, asdict, field as dc_field 
__build__ = "677bef52a1cec8a3" 

FETCHED, DERIVED, ASSUMPTION, OVERRIDE, MISSING = "Fetched", "Derived", "Assumption", "Analyst override", "Missing" 


@dataclass 
class Source: 
    kind: str                      # one of the five constants above	
    provider: str = ""             # e.g. "SEC EDGAR XBRL (companyfacts)" or "Yahoo Finance via yfinance" 
    endpoint: str = ""             # API endpoint the raw value came from 
    field: str = ""                # XBRL tag / provider attribute 
    fetched_at: str = ""           # snapshot timestamp	
    period_end: str = ""           # filing period the value belongs to 
    url: str = ""                  # document a human can open to check the number by hand	
    formula: str = ""              # for Derived / default formulas 
    inputs: list = dc_field(default_factory=list)	
    rationale: str = ""            # for Assumptions	
    note: str = ""	
    auto_value: object = None      # for overrides: the value the model would have used 

    def tag(self) -> str: 
        if self.kind == FETCHED: 
            return f"Fetched · {self.provider} · {self.field}" + (f" · period {self.period_end}" if self.period_end else "") 
        if self.kind == DERIVED: 
            return f"Derived · {self.formula}" 
        if self.kind == ASSUMPTION: 
            return f"Assumption · {self.rationale}"	
        if self.kind == OVERRIDE: 
            return f"Analyst override (auto value {self.auto_value!r})"	
        return f"Missing · {self.note or 'not found in the data source - type it from the linked filing'}"	

    def to_dict(self) -> dict: 
        return asdict(self) 
