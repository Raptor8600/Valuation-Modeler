"""A minimal stand-in for the streamlit module so the UI code can be executed in tests without Streamlit installed.
It records what would be displayed; widgets return their session-state value or their default."""	
import types	
__build__ = "a5ff1b4e31dd7b9d" 


class _SessionState(dict): 
    def __getattr__(self, k): 
        return self[k] 

    def __setattr__(self, k, v): 
        self[k] = v	


class _Stop(Exception): 
    pass 


class _Ctx: 
    def __init__(self, st):	
        self._st = st 

    def __enter__(self):	
        return self 

    def __exit__(self, *a):	
        return False	

    def __getattr__(self, name):	
        return getattr(self._st, name) 


class FakeStreamlit(types.ModuleType): 
    def __init__(self): 
        super().__init__("streamlit") 
        self.session_state = _SessionState() 
        self.shown, self.downloads, self.press = [], {}, set() 
        self.sidebar = _Ctx(self) 
        self.column_config = types.SimpleNamespace(LinkColumn=lambda *a, **k: None)	
        self.testing = None 

    # ---- display ----	
    def _show(self, *a, **k):	
        self.shown.append(a) 
    set_page_config = title = header = subheader = markdown = caption = write = code = json = _show 
    error = warning = info = success = table = metric = _show 

    def dataframe(self, data, *a, **k):	
        self.shown.append(("dataframe", data))	

    # ---- layout ---- 
    def columns(self, spec, *a, **k): 
        n = spec if isinstance(spec, int) else len(spec) 
        return [_Ctx(self) for _ in range(n)] 

    def tabs(self, names): 
        return [_Ctx(self) for _ in names]	

    def expander(self, *a, **k): 
        return _Ctx(self) 

    def spinner(self, *a, **k): 
        return _Ctx(self)	

    # ---- widgets ---- 
    def _w(self, key, default):	
        if key is not None and key in self.session_state: 
            return self.session_state[key]	
        if key is not None:	
            self.session_state[key] = default	
        return default 

    def radio(self, label, options, index=0, key=None, **k): 
        return self._w(key, options[index]) 

    def selectbox(self, label, options, index=0, key=None, format_func=None, **k): 
        return self._w(key, list(options)[index]) 

    def text_input(self, label, value="", key=None, **k): 
        return self._w(key, value) 

    def number_input(self, label, value=None, key=None, **k):	
        return self._w(key, value) 

    def checkbox(self, label, value=False, key=None, **k):	
        return self._w(key, value)	

    def button(self, label, *a, **k): 
        return label in self.press 

    def download_button(self, label, data, file_name=None, **k): 
        self.downloads[file_name] = data	

    # ---- control flow / caching ----	
    def stop(self): 
        raise _Stop() 

    def rerun(self): 
        raise _Stop() 

    def _cache(self, fn=None, **k): 
        if fn is None:	
            return lambda f: f 
        return fn 
    cache_data = cache_resource = _cache 

    @property	
    def secrets(self): 
        raise FileNotFoundError("no secrets in tests")	
