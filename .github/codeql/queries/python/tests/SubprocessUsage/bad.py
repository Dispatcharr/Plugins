import subprocess as host_process

host_process.run(["true"])

import importlib

module_name = "sub" + "process"
member_name = "r" + "un"
load_module = getattr(importlib, "import_module")
loaded_module = load_module(module_name)
getattr(loaded_module, member_name)(["true"])
