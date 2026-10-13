"""Platform adapters for curl discovery and nonblocking process locks."""
import os
from pathlib import Path
import shutil
import sys

def curl_executable():
    if sys.platform == 'win32':
        path = shutil.which('curl.exe')
    else:
        path = '/usr/bin/curl' if Path('/usr/bin/curl').is_file() else shutil.which('curl')
    if not path:
        raise RuntimeError('curl is unavailable; install curl and add it to PATH')
    return path

class FileLock:
    LOCK_EX = 1
    LOCK_NB = 2

    @staticmethod
    def flock(file, flags):
        if os.name == 'nt':
            import msvcrt
            # Windows locks a byte range; ensure byte zero exists and lock it.
            file.seek(0)
            if not file.read(1):
                file.write('0')
                file.flush()
            file.seek(0)
            msvcrt.locking(file.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(file, fcntl.LOCK_EX | fcntl.LOCK_NB)

fcntl = FileLock
