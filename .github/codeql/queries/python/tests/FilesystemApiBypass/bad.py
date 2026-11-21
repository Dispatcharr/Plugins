from pathlib import Path

Path("/tmp/plugin.txt").write_text("plugin data")

import os
from os import O_RDONLY as READ_ONLY

os.open("file", os.O_WRONLY | os.O_CREAT)
os.open("file", os.O_RDWR)
os.open("file", os.O_RDONLY | os.O_TRUNC)
os.open("file", flags=os.O_RDONLY | os.O_CREAT)
os.open("file", flags)
os.open("file", os.O_RDONLY | flags)
os.open("file", os.O_RDONLY | os.O_APPEND)
os.open("file", READ_ONLY)
