__builtins__["open"] = lambda *args, **kwargs: None
__builtins__.__import__ = lambda *args, **kwargs: None
setattr(__builtins__, "open", lambda *args, **kwargs: None)
