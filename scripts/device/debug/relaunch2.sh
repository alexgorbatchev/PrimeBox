#!/bin/sh
for p in $(ps w | awk '$0 ~ /[r]oot\/pdj|[g]dbserver/ {print $1}'); do kill -9 $p 2>/dev/null; done
sleep 1
export EDB_BIN=/usr/bin
nohup env LD_LIBRARY_PATH=/lib32:/data/debian/usr/lib/arm-linux-gnueabihf \
  /lib32/ld-linux-armhf.so.3 /data/debian/usr/bin/gdbserver --multi 0.0.0.0:1234 > /data/gdbserver.log 2>&1 < /dev/null &
sleep 1
nohup chroot /data/rbx3-run /lib/ld-linux.so.3 /usr/bin/edb_streamd > /data/edb_daemon_out.log 2>&1 &
sleep 1
chroot /data/rbx3-run /lib/ld-linux.so.3 /root/pdj/rbp -a > /tmp/rbp-frozen.log 2>&1 &
RBP=$!
sleep 0.4
kill -STOP $RBP 2>/dev/null
sleep 0.2
echo "$RBP" > /data/rbp.pid
echo "RBP_PID=$RBP state=$(cat /proc/$RBP/stat 2>/dev/null | awk '{print $3}')"
echo "gdbserver_log: $(cat /data/gdbserver.log)"
