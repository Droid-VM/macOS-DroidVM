#!/usr/bin/env bash
# Print the panic text of the last smoke boot (it lives at guest PA 0x13fb80000).  kc-panic.sh [BYTES]
cd "$(dirname "$0")/.."
python3 scripts/rig-dmesg.py --peek 0x13fb80000 /tmp/xnu12377-serial.log ${1:-1500} 2>&1 | python3 -c "
import sys,re
b=bytearray()
for l in sys.stdin:
    m=re.match(r'0x[0-9a-f]+: ((?:[0-9a-f]{2} ?){1,16})',l)
    if m: b+=bytes.fromhex(m.group(1).replace(' ',''))
i=b.find(b'panic(')
print(b[i:i+int(sys.argv[1]) if len(sys.argv)>1 else i+600].decode(errors='replace') if i>=0 else 'no panic')
" ${1:-600}
