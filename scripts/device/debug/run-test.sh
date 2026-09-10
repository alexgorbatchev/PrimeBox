#!/bin/sh
# precise cleanup: only actual strace/rbp processes (pattern won't match this script's cmdline)
for p in $(ps w | awk '$0 ~ /[s]trace -f|[r]oot\/pdj\/[r]bp/ {print $1}'); do kill -9 $p 2>/dev/null; done
sleep 1
export EDB_BIN=/usr/bin
rm -f /data/trc.log /data/rbp-out.log
LD_LIBRARY_PATH=/lib32 /lib32/ld-linux-armhf.so.3 /data/debian/usr/bin/strace -f -tt -s 128 -o /data/trc.log -- \
  /sbin/chroot /data/rbx3-run /lib/ld-linux.so.3 /root/pdj/rbp -a > /data/rbp-out.log 2>&1
echo "rc=$?"
echo "=== rbp log ==="
head -30 /data/rbp-out.log
echo "=== fb modeset results (last) ==="
grep -E "FBIOPUT_VSCREENINFO" /data/trc.log | grep -E "= -1|= [0-9]+" | tail -6
echo "=== SIGSEGV count ==="
grep -c SIGSEGV /data/trc.log
