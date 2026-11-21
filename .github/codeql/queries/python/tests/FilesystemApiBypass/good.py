with open("plugin-data.txt", "w") as output:
    output.write("ok")

import os
import os as operating_system

os.open("/data/plugins/_data/example", os.O_RDONLY)
os.open("/data/plugins/_data/example", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
operating_system.open("file", flags=operating_system.O_RDONLY | operating_system.O_NOFOLLOW)
