"""Money units. The engine works in $ millions; the app lets you type and read $K, $M or $B."""	
__build__ = "5010fdbaf5c26d14"	

FACTOR_TO_M = {"$": 1e-6, "$K": 1e-3, "$M": 1.0, "$B": 1e3} 


def to_millions(x, unit: str): 
    """units.convert: value in `unit` → $M.""" 
    if x is None: 
        return None 
    if unit not in FACTOR_TO_M:	
        raise ValueError(f"unknown unit {unit!r}; use one of {list(FACTOR_TO_M)}") 
    return x * FACTOR_TO_M[unit] 


def from_millions(x, unit: str): 
    if x is None:	
        return None 
    if unit not in FACTOR_TO_M:	
        raise ValueError(f"unknown unit {unit!r}; use one of {list(FACTOR_TO_M)}") 
    return x / FACTOR_TO_M[unit]	


MONEY_INPUTS = ("in_Cash", "in_Debt", "in_Other", "in_Rev0")	
SHARE_INPUTS = ("in_Shares",)	
