import io
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import primebox.launcher.setup_launcher as launcher_mod


class SetupLauncherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.launcher = launcher_mod

    def test_update_launcher_conf_empty(self):
        result = self.launcher.update_launcher_conf("")
        self.assertEqual(result, self.launcher.DEFAULT_LAUNCHER_CONF)

    def test_update_launcher_conf_idempotent(self):
        initial = (
            "# DJ Apps\n"
            "ENGINE |\n"
            "REKORDBOX (XDJ-RX3) | /data/start-rb.sh\n\n"
            "# Other\n"
            "DOOM | /data/doom\n"
        )
        result = self.launcher.update_launcher_conf(initial)
        self.assertEqual(result, initial)

    def test_update_launcher_conf_preserves_existing_apps(self):
        initial = (
            "# RetroGo Launcher\n"
            "DOOM | /data/doomprimego\n"
            "TETRIS | /data/retrogo.sh\n"
        )
        expected = (
            "# DJ Apps\n"
            "ENGINE |\n"
            "REKORDBOX (XDJ-RX3) | /data/start-rb.sh\n\n"
            "# RetroGo Launcher\n"
            "DOOM | /data/doomprimego\n"
            "TETRIS | /data/retrogo.sh\n"
        )
        result = self.launcher.update_launcher_conf(initial)
        self.assertEqual(result, expected)

    def test_update_launcher_conf_with_dj_apps_header(self):
        initial = (
            "# DJ Apps\n"
            "MIXXX | /data/mixxx\n\n"
            "# RetroGo Launcher\n"
            "DOOM | /data/doom\n"
        )
        expected = (
            "# DJ Apps\n"
            "ENGINE |\n"
            "REKORDBOX (XDJ-RX3) | /data/start-rb.sh\n"
            "MIXXX | /data/mixxx\n\n"
            "# RetroGo Launcher\n"
            "DOOM | /data/doom\n"
        )
        result = self.launcher.update_launcher_conf(initial)
        self.assertEqual(result, expected)

    def test_generate_udev_rule_exact(self):
        rule = self.launcher.generate_udev_rule("/data/check-and-launch-rb.sh")
        expected = 'ACTION=="add", SUBSYSTEM=="block", KERNEL=="sd[a-z][0-9]", RUN+="/data/check-and-launch-rb.sh %k"\n'
        self.assertEqual(rule, expected)

    def test_generate_soundswitch_override_exact(self):
        override = self.launcher.generate_soundswitch_override("/data/launcher")
        expected = "[Service]\nExecStart=\nExecStart=/data/launcher\n"
        self.assertEqual(override, expected)

    def test_generate_usb_check_script_exact(self):
        script = self.launcher.generate_usb_check_script("/data/start-rb.sh")
        expected = (
            "#!/bin/sh\n"
            "# Auto-launch Rekordbox on Denon Prime GO when export.pdb is detected\n"
            'DEV="/dev/$1"\n'
            'TMPMNT="/tmp/check_usb"\n\n'
            'mkdir -p "$TMPMNT"\n'
            'mount -o ro "$DEV" "$TMPMNT" 2>/dev/null || exit 0\n\n'
            'if [ -f "$TMPMNT/PIONEER/rekordbox/export.pdb" ]; then\n'
            '    umount "$TMPMNT"\n'
            '    # Stop Denon daemons immediately to prevent edisksd bus-reset race\n'
            '    systemctl stop edisksd.service engine.service 2>/dev/null\n'
            '    /data/start-rb.sh &\n'
            'else\n'
            '    umount "$TMPMNT"\n'
            'fi\n'
        )
        self.assertEqual(script, expected)

    def test_setup_launcher_all_modes_full_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "data").mkdir(parents=True)
            (root / "etc/udev/rules.d").mkdir(parents=True)

            existing_conf = "# Games\nDOOM | /data/doom\n"
            (root / "data/launcher.conf").write_text(existing_conf, encoding="utf-8")

            res = self.launcher.setup_launcher(root, mode="all", dry_run=False)
            self.assertTrue(res["launcher_conf_updated"])
            self.assertTrue(res["udev_rule_created"])
            self.assertTrue(res["usb_script_created"])

            expected_conf = (
                "# DJ Apps\n"
                "ENGINE |\n"
                "REKORDBOX (XDJ-RX3) | /data/start-rb.sh\n\n"
                "# Games\n"
                "DOOM | /data/doom\n"
            )
            self.assertEqual((root / "data/launcher.conf").read_text(encoding="utf-8"), expected_conf)

            expected_udev = 'ACTION=="add", SUBSYSTEM=="block", KERNEL=="sd[a-z][0-9]", RUN+="/data/check-and-launch-rb.sh %k"\n'
            self.assertEqual((root / "etc/udev/rules.d/99-primebox.rules").read_text(encoding="utf-8"), expected_udev)

            script_path = root / "data/check-and-launch-rb.sh"
            self.assertTrue(script_path.exists())
            self.assertEqual(
                script_path.read_text(encoding="utf-8"),
                self.launcher.generate_usb_check_script("/data/start-rb.sh"),
            )
            # Check file permissions are exactly 0755
            self.assertEqual(oct(script_path.stat().st_mode & 0o777), oct(0o755))

    def test_setup_launcher_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "data").mkdir(parents=True)

            res = self.launcher.setup_launcher(root, mode="all", dry_run=True)
            self.assertTrue(res["launcher_conf_updated"])
            self.assertFalse((root / "data/launcher.conf").exists())
            self.assertFalse((root / "etc/udev/rules.d/99-primebox.rules").exists())

    def test_cli_execution_human_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            args = ['setup_launcher.py', '--root', str(root), '--mode', 'all']
            with patch.object(self.launcher.sys, 'argv', args), \
                 patch.dict(os.environ, {'AGENT': '0'}):
                ret = self.launcher.main()
                self.assertEqual(ret, 0)
                self.assertEqual(
                    (root / "data/launcher.conf").read_text(encoding="utf-8"),
                    self.launcher.DEFAULT_LAUNCHER_CONF,
                )

    def test_cli_execution_agent_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            args = ['setup_launcher.py', '--root', str(root), '--mode', 'retrogo']
            with patch.object(self.launcher.sys, 'argv', args), \
                 patch.dict(os.environ, {'AGENT': '1'}):
                ret = self.launcher.main()
                self.assertEqual(ret, 0)
                self.assertEqual(
                    (root / "data/launcher.conf").read_text(encoding="utf-8"),
                    self.launcher.DEFAULT_LAUNCHER_CONF,
                )
                self.assertFalse((root / "etc/udev/rules.d/99-primebox.rules").exists())

    def test_install_retrogo_from_zip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            root.mkdir(parents=True)
            pkg_path = Path(tmp) / "retrogo.zip"

            launcher_data = b"#!/bin/sh\n# Launcher binary\n"
            retrogo_data = b"#!/bin/sh\n# Retrogo helper\n"

            with zipfile.ZipFile(pkg_path, "w") as z:
                z.writestr("launcher", launcher_data)
                z.writestr("retrogo.sh", retrogo_data)

            res = self.launcher.install_retrogo(root, package_source=str(pkg_path))
            self.assertTrue(res["retrogo_installed"])

            launcher_file = root / "data/launcher"
            self.assertTrue(launcher_file.exists())
            self.assertEqual(launcher_file.read_bytes(), launcher_data)
            self.assertEqual(oct(launcher_file.stat().st_mode & 0o777), oct(0o755))

            override_file = root / "etc/systemd/system/soundswitch.service.d/override.conf"
            self.assertTrue(override_file.exists())
            self.assertEqual(
                override_file.read_text(encoding="utf-8"),
                self.launcher.generate_soundswitch_override("/data/launcher"),
            )

    def test_install_retrogo_already_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            launcher_bin = root / "data/launcher"
            launcher_bin.parent.mkdir(parents=True)
            launcher_bin.write_text("#!/bin/sh\n", encoding="utf-8")

            res = self.launcher.install_retrogo(root)
            self.assertFalse(res["retrogo_installed"])
            override_file = root / "etc/systemd/system/soundswitch.service.d/override.conf"
            self.assertTrue(override_file.exists())
            self.assertEqual(
                override_file.read_text(encoding="utf-8"),
                self.launcher.generate_soundswitch_override("/data/launcher"),
            )

    def test_cli_install_retrogo_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pkg_path = Path(tmp) / "mock_pkg.tar.gz"

            launcher_data = b"#!/bin/sh\n# Launcher\n"
            buf = io.BytesIO()
            with tarfile.open(fileobj=buf, mode="w:gz") as tar:
                info = tarfile.TarInfo(name="launcher")
                info.size = len(launcher_data)
                info.mode = 0o755
                tar.addfile(info, io.BytesIO(launcher_data))
            pkg_path.write_bytes(buf.getvalue())

            args = ['setup_launcher.py', '--root', str(root), '--install-retrogo', '--package', str(pkg_path)]
            with patch.object(self.launcher.sys, 'argv', args), \
                 patch.dict(os.environ, {'AGENT': '1'}):
                ret = self.launcher.main()
                self.assertEqual(ret, 0)
                self.assertEqual((root / "data/launcher").read_bytes(), launcher_data)

    def test_setup_launcher_remote_all_modes_exact(self):
        remote_state = {
            "/data/launcher.conf": "# RetroGo Launcher\nDOOM | /data/doom\n",
            "/data/launcher": True,
        }
        commands_run = []

        def mock_ssh_exec(target, cmd, input_data=None):
            commands_run.append((cmd, input_data))
            if "cat /data/launcher.conf" in cmd:
                if "/data/launcher.conf" in remote_state:
                    return 0, remote_state["/data/launcher.conf"], ""
                return 1, "", "No such file"
            elif "cat > /data/launcher.conf" in cmd:
                remote_state["/data/launcher.conf"] = input_data
                return 0, "", ""
            elif "test -f /data/launcher" in cmd:
                return 0 if remote_state.get("/data/launcher") else 1, "", ""
            elif "cat > /etc/udev/rules.d/99-primebox.rules" in cmd:
                remote_state["/etc/udev/rules.d/99-primebox.rules"] = input_data
                return 0, "", ""
            elif "cat > /data/check-and-launch-rb.sh" in cmd:
                remote_state["/data/check-and-launch-rb.sh"] = input_data
                return 0, "", ""
            return 0, "", ""

        res = self.launcher.setup_launcher_remote(
            target="root@192.168.1.100",
            mode="all",
            install_package=False,
            runner=mock_ssh_exec,
        )

        self.assertTrue(res["launcher_conf_updated"])
        self.assertTrue(res["udev_rule_created"])
        self.assertTrue(res["usb_script_created"])

        expected_conf = (
            "# DJ Apps\n"
            "ENGINE |\n"
            "REKORDBOX (XDJ-RX3) | /data/start-rb.sh\n\n"
            "# RetroGo Launcher\n"
            "DOOM | /data/doom\n"
        )
        self.assertEqual(remote_state["/data/launcher.conf"], expected_conf)
        self.assertEqual(
            remote_state["/etc/udev/rules.d/99-primebox.rules"],
            self.launcher.generate_udev_rule("/data/check-and-launch-rb.sh"),
        )
        self.assertEqual(
            remote_state["/data/check-and-launch-rb.sh"],
            self.launcher.generate_usb_check_script("/data/start-rb.sh"),
        )

    def test_setup_launcher_remote_dry_run(self):
        commands_run = []

        def mock_ssh_exec(target, cmd, input_data=None):
            commands_run.append((cmd, input_data))
            return 0, "", ""

        res = self.launcher.setup_launcher_remote(
            target="root@192.168.1.100",
            mode="all",
            dry_run=True,
            runner=mock_ssh_exec,
        )

        self.assertTrue(res["launcher_conf_updated"])
        write_cmds = [cmd for cmd, _ in commands_run if "cat >" in cmd]
        self.assertEqual(len(write_cmds), 0)

    def test_cli_remote_execution(self):
        def mock_ssh_exec(target, cmd, input_data=None):
            return 0, "", ""

        args = ['setup_launcher.py', '--remote', 'root@192.168.1.50', '--mode', 'all']
        with patch.object(self.launcher.sys, 'argv', args), \
             patch.object(self.launcher, 'ssh_run', side_effect=mock_ssh_exec), \
             patch.dict(os.environ, {'AGENT': '1'}):
            ret = self.launcher.main()
            self.assertEqual(ret, 0)

    def test_ssh_run_mocked(self):
        with patch('subprocess.run') as mock_sub:
            mock_sub.return_value.returncode = 0
            mock_sub.return_value.stdout = "output"
            mock_sub.return_value.stderr = ""
            code, out, err = self.launcher.ssh_run("root@192.168.1.1", "uname -a", input_data="test")
            self.assertEqual(code, 0)
            self.assertEqual(out, "output")
            self.assertEqual(err, "")
            self.assertTrue(mock_sub.called)

    def test_setup_launcher_remote_install_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            pkg_file = Path(tmp) / "retrogo.tar.gz"
            pkg_file.write_bytes(b"mock_archive_data")

            def mock_ssh_exec(target, cmd, input_data=None):
                if "test -f /data/launcher" in cmd:
                    return 1, "", ""
                return 0, "", ""

            res = self.launcher.setup_launcher_remote(
                target="root@192.168.1.100",
                mode="retrogo",
                install_package=True,
                package_source=str(pkg_file),
                runner=mock_ssh_exec,
            )
            self.assertTrue(res["retrogo_installed"])
            self.assertIn("root@192.168.1.100:/data/launcher", res["files_modified"])


if __name__ == '__main__':
    unittest.main()
