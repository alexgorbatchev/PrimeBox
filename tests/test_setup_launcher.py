import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
LAUNCHER_TOOL = ROOT / 'tools/launcher/setup_launcher.py'


def load_launcher_module():
    spec = importlib.util.spec_from_file_location('setup_launcher', LAUNCHER_TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class SetupLauncherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.launcher = load_launcher_module()

    def test_update_launcher_conf_empty(self):
        result = self.launcher.update_launcher_conf("")
        self.assertIn("ENGINE |", result)
        self.assertIn("REKORDBOX (XDJ-RX3) | /data/start-rb.sh", result)
        lines = [line.strip() for line in result.splitlines() if line.strip()]
        self.assertEqual(lines[0], "# DJ Apps")
        self.assertEqual(lines[1], "ENGINE |")
        self.assertEqual(lines[2], "REKORDBOX (XDJ-RX3) | /data/start-rb.sh")

    def test_update_launcher_conf_idempotent(self):
        initial = "# DJ Apps\nENGINE |\nREKORDBOX (XDJ-RX3) | /data/start-rb.sh\n\n# Other\nDOOM | /data/doom\n"
        result = self.launcher.update_launcher_conf(initial)
        self.assertEqual(result.strip(), initial.strip())

    def test_update_launcher_conf_preserves_existing_apps(self):
        initial = "# RetroGo Launcher\nDOOM | /data/doomprimego\nTETRIS | /data/retrogo.sh\n"
        result = self.launcher.update_launcher_conf(initial)
        self.assertIn("ENGINE |", result)
        self.assertIn("REKORDBOX (XDJ-RX3) | /data/start-rb.sh", result)
        self.assertIn("DOOM | /data/doomprimego", result)
        self.assertIn("TETRIS | /data/retrogo.sh", result)
        lines = [line.strip() for line in result.splitlines() if line.strip()]
        self.assertEqual(lines[0], "# DJ Apps")
        self.assertEqual(lines[1], "ENGINE |")
        self.assertEqual(lines[2], "REKORDBOX (XDJ-RX3) | /data/start-rb.sh")

    def test_update_launcher_conf_with_dj_apps_header(self):
        initial = "# DJ Apps\nMIXXX | /data/mixxx\n\n# RetroGo Launcher\nDOOM | /data/doom\n"
        result = self.launcher.update_launcher_conf(initial)
        self.assertIn("ENGINE |", result)
        self.assertIn("REKORDBOX (XDJ-RX3) | /data/start-rb.sh", result)
        self.assertIn("MIXXX | /data/mixxx", result)
        lines = [line.strip() for line in result.splitlines() if line.strip()]
        self.assertEqual(lines[0], "# DJ Apps")
        self.assertEqual(lines[1], "ENGINE |")
        self.assertEqual(lines[2], "REKORDBOX (XDJ-RX3) | /data/start-rb.sh")

    def test_generate_udev_rule(self):
        rule = self.launcher.generate_udev_rule("/data/check-and-launch-rb.sh")
        self.assertIn('ACTION=="add"', rule)
        self.assertIn('SUBSYSTEM=="block"', rule)
        self.assertIn('KERNEL=="sd[a-z][0-9]"', rule)
        self.assertIn('RUN+="/data/check-and-launch-rb.sh %k"', rule)

    def test_generate_usb_check_script(self):
        script = self.launcher.generate_usb_check_script("/data/start-rb.sh")
        self.assertTrue(script.startswith("#!/bin/sh"))
        self.assertIn("PIONEER/rekordbox/export.pdb", script)
        self.assertIn("systemctl stop edisksd.service engine.service", script)
        self.assertIn("/data/start-rb.sh &", script)

    def test_setup_launcher_all_modes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "data").mkdir(parents=True)
            (root / "etc/udev/rules.d").mkdir(parents=True)

            existing_conf = "# Games\nDOOM | /data/doom\n"
            (root / "data/launcher.conf").write_text(existing_conf)

            res = self.launcher.setup_launcher(root, mode="all", dry_run=False)
            self.assertTrue(res["launcher_conf_updated"])
            self.assertTrue(res["udev_rule_created"])
            self.assertTrue(res["usb_script_created"])

            conf_content = (root / "data/launcher.conf").read_text()
            self.assertIn("REKORDBOX (XDJ-RX3) | /data/start-rb.sh", conf_content)
            self.assertIn("DOOM | /data/doom", conf_content)

            udev_content = (root / "etc/udev/rules.d/99-primebox.rules").read_text()
            self.assertIn("check-and-launch-rb.sh", udev_content)

            script_path = root / "data/check-and-launch-rb.sh"
            self.assertTrue(script_path.exists())
            self.assertTrue(os.access(script_path, os.X_OK))

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
                self.assertTrue((root / "data/launcher.conf").exists())

    def test_cli_execution_agent_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            args = ['setup_launcher.py', '--root', str(root), '--mode', 'retrogo']
            with patch.object(self.launcher.sys, 'argv', args), \
                 patch.dict(os.environ, {'AGENT': '1'}):
                ret = self.launcher.main()
                self.assertEqual(ret, 0)
                self.assertTrue((root / "data/launcher.conf").exists())
                self.assertFalse((root / "etc/udev/rules.d/99-primebox.rules").exists())


    def test_generate_soundswitch_override(self):
        override = self.launcher.generate_soundswitch_override("/data/launcher")
        self.assertIn("[Service]", override)
        self.assertIn("ExecStart=", override)
        self.assertIn("ExecStart=/data/launcher", override)

    def test_install_retrogo_from_zip(self):
        import zipfile
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            root.mkdir(parents=True)
            pkg_path = Path(tmp) / "retrogo.zip"

            # Create mock retrogo zip containing launcher and retrogo.sh
            with zipfile.ZipFile(pkg_path, "w") as z:
                z.writestr("launcher", b"#!/bin/sh\necho launcher\n")
                z.writestr("retrogo.sh", b"#!/bin/sh\necho retrogo\n")

            res = self.launcher.install_retrogo(root, package_source=str(pkg_path))
            self.assertTrue(res["retrogo_installed"])
            self.assertTrue((root / "data/launcher").exists())
            self.assertTrue(os.access(root / "data/launcher", os.X_OK))
            self.assertTrue((root / "etc/systemd/system/soundswitch.service.d/override.conf").exists())

    def test_install_retrogo_already_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            launcher_bin = root / "data/launcher"
            launcher_bin.parent.mkdir(parents=True)
            launcher_bin.write_text("#!/bin/sh\n")

            res = self.launcher.install_retrogo(root)
            self.assertFalse(res["retrogo_installed"])  # Already present, skipped re-install
            self.assertTrue((root / "etc/systemd/system/soundswitch.service.d/override.conf").exists())

    def test_cli_install_retrogo_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pkg_path = Path(tmp) / "mock_pkg.tar.gz"
            import tarfile, io
            buf = io.BytesIO()
            with tarfile.open(fileobj=buf, mode="w:gz") as tar:
                info = tarfile.TarInfo(name="launcher")
                info.size = 10
                info.mode = 0o755
                tar.addfile(info, io.BytesIO(b"#!/bin/sh\n"))
            pkg_path.write_bytes(buf.getvalue())

            args = ['setup_launcher.py', '--root', str(root), '--install-retrogo', '--package', str(pkg_path)]
            with patch.object(self.launcher.sys, 'argv', args), \
                 patch.dict(os.environ, {'AGENT': '1'}):
                ret = self.launcher.main()
                self.assertEqual(ret, 0)
                self.assertTrue((root / "data/launcher").exists())


    def test_sh_script_syntax_and_execution(self):
        import subprocess
        script_path = ROOT / 'scripts/device/setup-launcher.sh'
        # Check syntax using sh -n
        res = subprocess.run(['sh', '-n', str(script_path)], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"Syntax error in setup-launcher.sh: {res.stderr}")


if __name__ == '__main__':
    unittest.main()
