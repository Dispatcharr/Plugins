import sys

sys.modules["harmless"] = object()
sys.modules.pop("harmless")
