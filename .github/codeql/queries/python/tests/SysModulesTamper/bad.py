import sys

sys.modules["subprocess"] = object()
sys.modules.pop("socket")
