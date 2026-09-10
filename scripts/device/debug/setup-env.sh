#!/bin/sh
# careful env setup: mounts, stubs, engine off, daemon, frozen rbp
mountpoint -q /data/rbx3-run/dev  || mount --bind /dev  /data/rbx3-run/dev
mountpoint -q /data/rbx3-run/proc || mount --bind /proc /data/rbx3-run/proc
mountpoint -q /data/rbx3-run/sys  || mount --bind /sys  /data/rbx3-run/sys
mountpoint -q /data/rbx3-run/tmp  || mount --bind /tmp  /data/rbx3-run/tmp
for d in gpiodrv hidg0 paudiog0 printkdrv0 subucom_spi1.0 subucom_spi2.0 subucom_spi_rdy3.0 subucom_spi_rdy4.0 tsc2007_2-0048; do
  [ -e /data/rbx3-run/dev/$d ] || touch /data/rbx3-run/dev/$d
  chmod 666 /data/rbx3-run/dev/$d 2>/dev/null
done
systemctl stop engine.service 2>/dev/null
sleep 1
rm -f /tmp/guard_LocalDBServer /tmp/req_LocalDBServer
export EDB_BIN=/usr/bin
nohup chroot /data/rbx3-run /lib/ld-linux.so.3 /usr/bin/edb_streamd > /data/edb_daemon_out.log 2>&1 &
sleep 1
chroot /data/rbx3-run /lib/ld-linux.so.3 /root/pdj/rbp -a > /tmp/rbp-frozen.log 2>&1 &
RBP=$!
for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do
  kill -0 "$RBP" 2>/dev/null && { kill -STOP "$RBP" 2>/dev/null; break; }
  sleep 0.02
done
sleep 0.2
echo "$RBP" > /data/rbp.pid
cat /proc/$RBP/stat 2>/dev/null | awk "{print \"RBP_PID=$RBP state:\", \$3}"
