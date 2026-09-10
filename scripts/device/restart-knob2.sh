#!/bin/sh
# restart rbp with knobshim2 (full Prime GO surface mapping + USB1 auto-detection)
# Clean native speed launcher (no strace, direct chroot execution)

# Stop Engine OS service and disk daemon (mandatory — releases audio, USB, controls)
systemctl stop engine.service edisksd.service 2>/dev/null
sleep 1

for p in $(ps w | awk '$0 ~ /[s]trace|[r]oot\/pdj\/[r]bp|[e]db_streamd|[g]dbserver/ {print $1}'); do
    kill -9 $p 2>/dev/null
done
sleep 1

# Ensure dev stubs, FIFOs, and blocked /dev/mem
sh /data/fix-dev.sh

# Deploy binary
cp /data/rbp-audio /data/rbx3-run/root/pdj/rbp
chmod 755 /data/rbx3-run/root/pdj/rbp

# Deploy updated knobshim2, audioshim, fbshim, and directfb fbdev module
cp /data/knobshim2.so /data/rbx3-run/root/pdj/knobshim.so
cp /data/knobshim2.so /data/rbx3-run/usr/lib/knobshim.so
chmod 755 /data/rbx3-run/usr/lib/knobshim.so /data/rbx3-run/root/pdj/knobshim.so

cp /data/audioshim.so /data/rbx3-run/root/pdj/audioshim.so
cp /data/audioshim.so /data/rbx3-run/usr/lib/audioshim.so
chmod 755 /data/rbx3-run/usr/lib/audioshim.so /data/rbx3-run/root/pdj/audioshim.so

cp /data/fbshim-tsc.so /data/rbx3-run/root/pdj/fbshim.so
cp /data/fbshim-tsc.so /data/rbx3-run/usr/lib/fbshim.so
chmod 755 /data/rbx3-run/usr/lib/fbshim.so /data/rbx3-run/root/pdj/fbshim.so

cp /data/libdirectfb_fbdev-rot16.so /data/rbx3-run/usr/lib/directfb-1.4-6/systems/libdirectfb_fbdev.so
chmod 755 /data/rbx3-run/usr/lib/directfb-1.4-6/systems/libdirectfb_fbdev.so

# Clean stale IPC/logs
rm -f /tmp/guard_LocalDBServer /tmp/req_LocalDBServer /tmp/knobshim.log /tmp/audioshim.log /tmp/dfbdig*.log /tmp/rot_surface.dump

# Ensure EDB daemon is running
export EDB_BIN=/usr/bin
nohup chroot /data/rbx3-run /lib/ld-linux.so.3 /usr/bin/edb_streamd > /data/edb_d.log 2>&1 &
sleep 1

# Stop USB watcher during startup
sh /data/usb-watch.sh stop

# Start rbp cleanly inside chroot with native environment (no strace)
rm -f /data/rbp-p.log
nohup chroot /data/rbx3-run env DFB_ROTATE=left JOG_VERBOSE=1 TEMPO_VERBOSE=1 LD_PRELOAD=/usr/lib/fbshim.so:/usr/lib/audioshim.so:/usr/lib/knobshim.so /lib/ld-linux.so.3 /root/pdj/rbp -a </dev/null >/data/rbp-p.log 2>&1 &

echo "launched rbp, waiting for initialization..."
for i in $(seq 1 30); do
  RBP=$(ps w | awk '/\/root\/pdj\/rbp/ && !/sh -c/ && !/strace/ && !/awk/ {print $1; exit}')
  if [ -n "$RBP" ] && ls -l /proc/$RBP/fd 2>/dev/null | grep -q udev_usb1; then
    echo "RBP=$RBP ready (udev_usb1 fd opened)"
    break
  fi
  sleep 0.5
done

# Start USB watcher once rbp is ready
sh /data/usb-watch.sh start
echo "--- knobshim log ---"
cat /tmp/knobshim.log 2>/dev/null
