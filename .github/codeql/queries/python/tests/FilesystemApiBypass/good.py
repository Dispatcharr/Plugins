with open("plugin-data.txt", "w") as output:
    output.write("ok")

import os
import os as operating_system

os.open("/data/plugins/_data/example", os.O_RDONLY)
os.open("/data/plugins/_data/example", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
operating_system.open("file", flags=operating_system.O_RDONLY | operating_system.O_NOFOLLOW)

# Ordinary file management is not treated as a sandbox-bypass finding.
import shutil
from pathlib import Path

shutil.copy("source", "target")
shutil.copy2("source", "target")
shutil.copyfile("source", "target")
shutil.copytree("source", "target")
shutil.move("source", "target")
shutil.rmtree("target")
Path("target").mkdir()
Path("target").touch()
Path("target").unlink()
Path("target").rename("other")
Path("target").replace("other")
