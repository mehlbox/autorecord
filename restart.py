#!/usr/bin/env python3
import os
import subprocess
import sys
from time import sleep


pid = sys.argv[1]
os.system("kill " + sys.argv[1])
pid = int(pid)

# Continuously check if process is still running
while True:
    try:
        os.kill(pid, 0)
        sleep(0.1)
    except OSError: # OSError is raised if process is still running
        # If process has exited, start the new application
        subprocess.Popen(["/audio/autorecorder.py"])
        break