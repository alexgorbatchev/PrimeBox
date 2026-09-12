#!/usr/bin/env python3
"""PrimeBox launcher setup and auto-start configuration tool for Denon Prime GO.

Configures on-screen touch boot menu (/data/launcher.conf), RetroGo installation,
and/or host udev rules for automatic Rekordbox standalone startup upon USB insertion.
"""

import argparse
import io
import os
from pathlib import Path
import shutil
import sys
import tarfile
from typing import Any, Dict, Optional
import urllib.request
import zipfile


DEFAULT_LAUNCHER_CONF = """# DJ Apps
ENGINE |
REKORDBOX (XDJ-RX3) | /data/start-rb.sh

# RetroGo Launcher
STREAM+ | bg/systemctl start enginestream.service
DOOM | /data/doomprimego

# Game Boy
TETRIS | /data/retrogo.sh /data/cores/gearboy_libretro.so "Tetris (World) (Rev 1).gb"
SUPER MARIO LAND | /data/retrogo.sh /data/cores/gearboy_libretro.so "Super Mario Land (World).gb"
POKEMON RED | /data/retrogo.sh /data/cores/gearboy_libretro.so "Pokemon - Red Version (USA, Europe) (SGB Enhanced).gb"

# SNES
SUPER MARIO WORLD | /data/retrogo.sh /data/cores/snes9x_libretro.so /data/roms/snes/Super\\ Mario\\ World\\ -\\ The\\ Definitive\\ Edition\\ v1.2.sfc
STREET FIGHTER II | /data/retrogo.sh /data/cores/snes9x_libretro.so /data/roms/snes/Street\\ Fighter\\ II\\ \\(USA\\).sfc
STREET FIGHTER II TURBO | /data/retrogo.sh /data/cores/snes9x_libretro.so /data/roms/snes/Street\\ Fighter\\ II\\ Turbo\\ \\(Europe\\).sfc

# PSX
TEKKEN 3 | /data/retrogo.sh /data/cores/pcsx_rearmed_libretro.so /data/roms/psx/Tekken\\ 3\\ \\(Europe\\,\\ Australia\\).cue

RETROARCH MENU | /data/retrogo.sh
"""


def is_agent_mode() -> bool:
    val = os.environ.get("AGENT", "").lower()
    return val in ("1", "true", "yes")


def update_launcher_conf(
    content: str,
    entry_title: str = "REKORDBOX (XDJ-RX3)",
    entry_cmd: str = "/data/start-rb.sh",
) -> str:
    """Idempotently insert or update Engine and Rekordbox entries in launcher.conf."""
    if not content.strip():
        return DEFAULT_LAUNCHER_CONF

    # Replace legacy "BACK TO ENGINE |"
    raw_lines = [
        line for line in content.splitlines()
        if line.strip() != "BACK TO ENGINE |" and line.strip() != "BACK TO ENGINE"
    ]

    # Check if both entries are already correctly in place
    has_engine = any(line.strip().startswith("ENGINE") and "|" in line for line in raw_lines)
    has_rb = entry_cmd in content or entry_title in content

    if has_engine and has_rb:
        return "\n".join(raw_lines) + "\n"

    lines = list(raw_lines)
    dj_idx = -1
    for i, line in enumerate(lines):
        if line.strip().lower().startswith("# dj apps") or line.strip().lower().startswith("# dj"):
            dj_idx = i
            break

    insert_entries = []
    if not has_engine:
        insert_entries.append("ENGINE |")
    if not has_rb:
        insert_entries.append(f"{entry_title} | {entry_cmd}")

    if dj_idx != -1:
        for offset, entry in enumerate(insert_entries):
            lines.insert(dj_idx + 1 + offset, entry)
    else:
        # Prepend DJ Apps section at top
        new_header = ["# DJ Apps"] + insert_entries
        if lines and lines[0].strip():
            new_header.append("")
        lines = new_header + lines

    return "\n".join(lines) + "\n"


def generate_udev_rule(script_path: str = "/data/check-and-launch-rb.sh") -> str:
    """Generate udev rule for detecting Rekordbox USB insertion."""
    return f'ACTION=="add", SUBSYSTEM=="block", KERNEL=="sd[a-z][0-9]", RUN+="{script_path} %k"\n'


def generate_soundswitch_override(launcher_path: str = "/data/launcher") -> str:
    """Generate systemd override for soundswitch.service to run touch launcher."""
    return f"""[Service]
ExecStart=
ExecStart={launcher_path}
"""


def generate_usb_check_script(target_script: str = "/data/start-rb.sh") -> str:
    """Generate shell script that inspects newly inserted USB partition."""
    return f"""#!/bin/sh
# Auto-launch Rekordbox on Denon Prime GO when export.pdb is detected
DEV="/dev/$1"
TMPMNT="/tmp/check_usb"

mkdir -p "$TMPMNT"
mount -o ro "$DEV" "$TMPMNT" 2>/dev/null || exit 0

if [ -f "$TMPMNT/PIONEER/rekordbox/export.pdb" ]; then
    umount "$TMPMNT"
    # Stop Denon daemons immediately to prevent edisksd bus-reset race
    systemctl stop edisksd.service engine.service 2>/dev/null
    {target_script} &
else
    umount "$TMPMNT"
fi
"""


def install_retrogo(
    root_dir: Path,
    package_source: Optional[str] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Install RetroGo binary package and configure systemd soundswitch hook."""
    results: Dict[str, Any] = {
        "retrogo_installed": False,
        "soundswitch_hooked": False,
        "files_modified": [],
    }

    root_dir = Path(root_dir)
    data_dir = root_dir / "data"
    launcher_bin = data_dir / "launcher"

    if not launcher_bin.exists():
        if package_source:
            if package_source.startswith("http://") or package_source.startswith("https://"):
                req = urllib.request.urlopen(package_source)
                pkg_data = req.read()
            else:
                pkg_data = Path(package_source).read_bytes()

            if not dry_run:
                data_dir.mkdir(parents=True, exist_ok=True)
                # Try zip format
                try:
                    with zipfile.ZipFile(io.BytesIO(pkg_data)) as z:
                        z.extractall(data_dir)
                except zipfile.BadZipFile:
                    # Try tar format
                    try:
                        with tarfile.open(fileobj=io.BytesIO(pkg_data)) as t:
                            t.extractall(data_dir)
                    except tarfile.TarError:
                        # Fallback: single raw executable
                        launcher_bin.write_bytes(pkg_data)

                if launcher_bin.exists():
                    launcher_bin.chmod(0o755)

            results["retrogo_installed"] = True
            results["files_modified"].append(str(launcher_bin))

    # Configure soundswitch.service override
    override_path = root_dir / "etc/systemd/system/soundswitch.service.d/override.conf"
    override_content = generate_soundswitch_override()
    results["soundswitch_hooked"] = True
    results["files_modified"].append(str(override_path))
    if not dry_run:
        override_path.parent.mkdir(parents=True, exist_ok=True)
        override_path.write_text(override_content, encoding="utf-8")

    return results


def setup_launcher(
    root_dir: Path,
    mode: str = "all",
    install_package: bool = False,
    package_source: Optional[str] = None,
    dry_run: bool = False,
    agent_mode: bool = False,
) -> Dict[str, Any]:
    """Configure boot menu launcher, RetroGo, and/or udev rules under root_dir."""
    results: Dict[str, Any] = {
        "launcher_conf_updated": False,
        "retrogo_installed": False,
        "udev_rule_created": False,
        "usb_script_created": False,
        "files_modified": [],
    }

    root_dir = Path(root_dir)

    if install_package:
        ret_res = install_retrogo(root_dir, package_source=package_source, dry_run=dry_run)
        results["retrogo_installed"] = ret_res["retrogo_installed"]
        results["files_modified"].extend(ret_res["files_modified"])

    if mode in ("all", "retrogo"):
        conf_path = root_dir / "data/launcher.conf"
        existing = conf_path.read_text(encoding="utf-8") if conf_path.exists() else ""
        new_content = update_launcher_conf(existing)
        if new_content != existing or not conf_path.exists():
            results["launcher_conf_updated"] = True
            results["files_modified"].append(str(conf_path))
            if not dry_run:
                conf_path.parent.mkdir(parents=True, exist_ok=True)
                conf_path.write_text(new_content, encoding="utf-8")

    if mode in ("all", "udev"):
        udev_path = root_dir / "etc/udev/rules.d/99-primebox.rules"
        rule_content = generate_udev_rule()
        results["udev_rule_created"] = True
        results["files_modified"].append(str(udev_path))
        if not dry_run:
            udev_path.parent.mkdir(parents=True, exist_ok=True)
            udev_path.write_text(rule_content, encoding="utf-8")

        script_path = root_dir / "data/check-and-launch-rb.sh"
        script_content = generate_usb_check_script()
        results["usb_script_created"] = True
        results["files_modified"].append(str(script_path))
        if not dry_run:
            script_path.parent.mkdir(parents=True, exist_ok=True)
            script_path.write_text(script_content, encoding="utf-8")
            script_path.chmod(0o755)

    return results


def ssh_run(target: str, cmd: str, input_data: Optional[str] = None) -> Any:
    """Execute command over SSH."""
    import subprocess
    proc = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=no", target, cmd],
        input=input_data,
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout, proc.stderr


def setup_launcher_remote(
    target: str,
    mode: str = "all",
    install_package: bool = False,
    package_source: Optional[str] = None,
    dry_run: bool = False,
    agent_mode: bool = False,
    runner: Optional[Any] = None,
) -> Dict[str, Any]:
    """Configure boot menu launcher, RetroGo, and/or udev rules remotely over SSH."""
    run = runner or ssh_run
    results: Dict[str, Any] = {
        "launcher_conf_updated": False,
        "retrogo_installed": False,
        "udev_rule_created": False,
        "usb_script_created": False,
        "files_modified": [],
    }

    if install_package:
        code, _, _ = run(target, "test -f /data/launcher")
        if code != 0 and package_source:
            # Package extraction over SSH
            if not dry_run:
                if package_source.startswith("http://") or package_source.startswith("https://"):
                    req = urllib.request.urlopen(package_source)
                    pkg_data = req.read()
                else:
                    pkg_data = Path(package_source).read_bytes()

                # Upload archive and extract
                run(target, "mkdir -p /data && tar -xz -C /data/ 2>/dev/null || unzip -o -d /data/ - 2>/dev/null", input_data=pkg_data.decode("latin1", errors="ignore"))
                run(target, "chmod 755 /data/launcher 2>/dev/null || true")

            results["retrogo_installed"] = True
            results["files_modified"].append(f"{target}:/data/launcher")

        override_content = generate_soundswitch_override()
        results["files_modified"].append(f"{target}:/etc/systemd/system/soundswitch.service.d/override.conf")
        if not dry_run:
            run(target, "mkdir -p /etc/systemd/system/soundswitch.service.d && cat > /etc/systemd/system/soundswitch.service.d/override.conf", input_data=override_content)
            run(target, "systemctl daemon-reload 2>/dev/null || true")

    if mode in ("all", "retrogo"):
        code, stdout, _ = run(target, "cat /data/launcher.conf 2>/dev/null || true")
        new_content = update_launcher_conf(stdout)
        results["launcher_conf_updated"] = True
        results["files_modified"].append(f"{target}:/data/launcher.conf")
        if not dry_run and (new_content != stdout or code != 0):
            run(target, "cat > /data/launcher.conf", input_data=new_content)

    if mode in ("all", "udev"):
        rule_content = generate_udev_rule()
        results["udev_rule_created"] = True
        results["files_modified"].append(f"{target}:/etc/udev/rules.d/99-primebox.rules")
        if not dry_run:
            run(target, "mkdir -p /etc/udev/rules.d && cat > /etc/udev/rules.d/99-primebox.rules && udevadm control --reload-rules 2>/dev/null || true", input_data=rule_content)

        script_content = generate_usb_check_script()
        results["usb_script_created"] = True
        results["files_modified"].append(f"{target}:/data/check-and-launch-rb.sh")
        if not dry_run:
            run(target, "cat > /data/check-and-launch-rb.sh && chmod 755 /data/check-and-launch-rb.sh", input_data=script_content)

    return results


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Configure PrimeBox launcher, RetroGo, and auto-start on Denon Prime GO."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("/"),
        help="Target local root directory (default: /)",
    )
    parser.add_argument(
        "--remote",
        type=str,
        default=None,
        help="Target remote SSH host (e.g. root@192.168.1.100)",
    )
    parser.add_argument(
        "--mode",
        choices=["all", "retrogo", "udev"],
        default="all",
        help="Configuration target: retrogo (launcher.conf), udev (USB autostart), or all (default: all)",
    )
    parser.add_argument(
        "--install-retrogo",
        action="store_true",
        help="Install RetroGo package if /data/launcher is not present and hook soundswitch.service",
    )
    parser.add_argument(
        "--package",
        type=str,
        default=None,
        help="Path or URL to RetroGo package (.zip, .tar.gz, binary)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate actions without writing files to disk",
    )

    args = parser.parse_args()
    agent_mode = is_agent_mode()

    if args.remote:
        res = setup_launcher_remote(
            target=args.remote,
            mode=args.mode,
            install_package=args.install_retrogo,
            package_source=args.package,
            dry_run=args.dry_run,
            agent_mode=agent_mode,
        )
    else:
        res = setup_launcher(
            root_dir=args.root,
            mode=args.mode,
            install_package=args.install_retrogo,
            package_source=args.package,
            dry_run=args.dry_run,
            agent_mode=agent_mode,
        )

    if agent_mode:
        print(f"STATUS: SUCCESS")
        print(f"MODE: {args.mode}")
        print(f"DRY_RUN: {args.dry_run}")
        for f in res["files_modified"]:
            print(f"* MODIFIED: {f}")
    else:
        print("[OK] PrimeBox launcher setup complete")
        print(f"Mode: {args.mode}")
        if args.dry_run:
            print("Notice: Dry-run active (no files written)")
        print("Updated components:")
        for f in res["files_modified"]:
            print(f"  - {f}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
