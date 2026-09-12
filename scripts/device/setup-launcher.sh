#!/bin/sh
# setup-launcher.sh — Pure POSIX /bin/sh launcher and auto-start configurator for Denon Prime GO
# Runs directly on device with zero Python runtime dependency.
set -e

echo "[PrimeBox] Setting up launcher and auto-start configuration..."

# 1. Setup /data/launcher.conf for RetroGo / Touch Launcher
if [ ! -f /data/launcher.conf ]; then
    cat << 'EOF' > /data/launcher.conf
# DJ Apps
ENGINE |
REKORDBOX (XDJ-RX3) | /data/start-rb.sh

# RetroGo Launcher
STREAM+ | bg/systemctl start enginestream.service
DOOM | /data/doomprimego

RETROARCH MENU | /data/retrogo.sh
EOF
    echo "  - Created /data/launcher.conf"
else
    # Remove obsolete BACK TO ENGINE lines
    sed -i '/BACK TO ENGINE/d' /data/launcher.conf

    # Add ENGINE and Rekordbox if missing
    if ! grep -q "start-rb.sh" /data/launcher.conf; then
        if grep -qi "# DJ Apps" /data/launcher.conf; then
            sed -i '/# DJ Apps/a REKORDBOX (XDJ-RX3) | /data/start-rb.sh' /data/launcher.conf
            if ! grep -q "^ENGINE |" /data/launcher.conf; then
                sed -i '/# DJ Apps/a ENGINE |' /data/launcher.conf
            fi
        else
            printf "# DJ Apps\nENGINE |\nREKORDBOX (XDJ-RX3) | /data/start-rb.sh\n\n%s" "$(cat /data/launcher.conf)" > /data/launcher.conf
        fi
    elif ! grep -q "^ENGINE |" /data/launcher.conf; then
        if grep -qi "# DJ Apps" /data/launcher.conf; then
            sed -i '/# DJ Apps/a ENGINE |' /data/launcher.conf
        else
            sed -i '1i ENGINE |' /data/launcher.conf
        fi
    fi
    echo "  - Updated /data/launcher.conf"
fi

# 2. Setup Udev Auto-Start for Rekordbox USB sticks
cat << 'EOF' > /data/check-and-launch-rb.sh
#!/bin/sh
# Auto-launch Rekordbox on Denon Prime GO when export.pdb is detected
DEV="/dev/$1"
TMPMNT="/tmp/check_usb"

mkdir -p "$TMPMNT"
mount -o ro "$DEV" "$TMPMNT" 2>/dev/null || exit 0

if [ -f "$TMPMNT/PIONEER/rekordbox/export.pdb" ]; then
    umount "$TMPMNT"
    systemctl stop edisksd.service engine.service 2>/dev/null
    /data/start-rb.sh &
else
    umount "$TMPMNT"
fi
EOF
chmod 755 /data/check-and-launch-rb.sh
echo "  - Created /data/check-and-launch-rb.sh"

mkdir -p /etc/udev/rules.d
cat << 'EOF' > /etc/udev/rules.d/99-primebox.rules
ACTION=="add", SUBSYSTEM=="block", KERNEL=="sd[a-z][0-9]", RUN+="/data/check-and-launch-rb.sh %k"
EOF
echo "  - Created /etc/udev/rules.d/99-primebox.rules"

udevadm control --reload-rules 2>/dev/null || true

# 3. Hook soundswitch.service if /data/launcher is present
if [ -f /data/launcher ]; then
    mkdir -p /etc/systemd/system/soundswitch.service.d
    cat << 'EOF' > /etc/systemd/system/soundswitch.service.d/override.conf
[Service]
ExecStart=
ExecStart=/data/launcher
EOF
    systemctl daemon-reload 2>/dev/null || true
    echo "  - Configured soundswitch.service override for /data/launcher"
fi

echo "[OK] PrimeBox launcher setup complete."
