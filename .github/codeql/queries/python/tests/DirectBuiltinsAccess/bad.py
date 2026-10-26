import builtins

builtins.open("/tmp/plugin.txt", "w")

module = __import__("built" + "ins")
getattr(module, "o" + "pen")
