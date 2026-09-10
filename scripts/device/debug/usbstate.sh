#!/bin/sh
# usbstate.sh — quick rbp USB state probe
RBP=$(ps w | awk '$0 ~ /\/root\/pdj\/rbp/ && !/strace/ {print $1; exit}')
echo "RBP=$RBP"
/data/debian/usr/bin/python3 - "$RBP" <<'PYEOF'
import struct, sys
pid = int(sys.argv[1])
def rd32(a):
    with open("/proc/%d/mem"%pid,"rb") as f:
        f.seek(a); return struct.unpack("<I",f.read(4))[0]
p = rd32(rd32(0x31dfec) + 272)
arr = rd32(p + 196)
for i in range(2):
    m = rd32(arr + i*4)
    if m:
        print("ch%d: mgr=%#x state=%d flags_148=%d flags_152=%d" % (i+1, m, rd32(m+136), rd32(m+148), rd32(m+152)))
# caution manager
cm = rd32(0x26871a0)
print("caution: lastcode1=%d lastcode2=%d" % (rd32(cm+136), rd32(cm+140)))
PYEOF
echo "--- running threads ---"
for t in /proc/$RBP/task/*; do
  tid=$(basename $t)
  st=$(awk '{print $3}' $t/stat 2>/dev/null)
  [ "$st" = "R" ] && echo "RUNNING: $tid $(cat $t/comm 2>/dev/null)"
done
echo "--- export.pdb count ---"
grep -ac "export" /data/trc-p.log 2>/dev/null
