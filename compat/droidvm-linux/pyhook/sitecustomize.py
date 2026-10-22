"""Make Droid-VM's macOS-shaped scripts run on Linux without editing each of them.

Python subprocess calls are redirected here: compile records (-MJ) name the Apple clang inside Darling, which does not exist on the
host, and macOS-only tools get Linux stand-ins. Loaded automatically through PYTHONPATH by every python3 the build starts.
"""
import os
import subprocess

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
_BIN = os.environ.get('GUNYAH_LINUX_BIN', '')
_MAP = {
    '/Volumes/SystemRoot/opt/apple/Library/Developer/CommandLineTools/usr/bin/clang': 'target-clang',
    '/Volumes/SystemRoot/opt/apple/Library/Developer/CommandLineTools/usr/bin/clang++': 'target-clang++',
    '/usr/bin/compression_tool': None,
}


def _redirect(argv):
    if not isinstance(argv, (list, tuple)) or not argv:
        return argv
    first = os.fspath(argv[0]) if not isinstance(argv[0], (bytes,)) else argv[0].decode()
    if first in _MAP:
        target = _MAP[first]
        replacement = os.path.join(_BIN, target) if target else os.path.join(_ROOT, 'shims/compression_tool')
        return [replacement] + list(argv[1:])
    return argv


if _BIN:
    _init = subprocess.Popen.__init__

    def _patched(self, args, *a, **k):
        _init(self, _redirect(args), *a, **k)

    subprocess.Popen.__init__ = _patched
