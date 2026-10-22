#!/usr/bin/env python3
"""In UniXNU's bootstrap pass (empty placeholder archives) skip the archive qualification snippets."""
import re, sys
p = sys.argv[1]
s = open(p).read()
if 'UNIXNU_KERNEL_BOOTSTRAP' in s.split('PY_')[-1][:400] or s.count("_o.environ.get('UNIXNU_KERNEL_BOOTSTRAP')"):
    print('already guarded'); sys.exit(0)
guard = "import os as _o, sys as _s\nif _o.environ.get('UNIXNU_KERNEL_BOOTSTRAP') == '1': _s.exit(0)\n"
n = 0
def sub(m):
    global n; n += 1
    return m.group(0) + guard
# heredoc bodies that read an archive's build-report.json
s = re.sub(r"(<<'PY_(?!DATA_UUID)[A-Z_]+'\n)", lambda m: m.group(1) + guard, s)
open(p, 'w').write(s)
print("guarded", s.count("UNIXNU_KERNEL_BOOTSTRAP') == '1'"), "snippets")
