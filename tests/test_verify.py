import io
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import primebox.verify.verify_links as links
import primebox.verify.verify_module as verify

ROOT = Path(__file__).resolve().parents[1]


class ModuleChecks(unittest.TestCase):
    header = 'Class: ELF32\nMachine: ARM\nFlags: 0x5000200, Version5 EABI, soft-float ABI'
    symbols = '''00001234 g DF .text 00000010 Base fstat
00001244 g DF .text 00000010 Base __fdelt_chk
00000000 DF *UND* 00000000 (GLIBC_2.4) __fxstat
'''
    dynamic = '\n'.join(f'(NEEDED) Shared library: [{lib}-1.4.so.0]' for lib in ('libdirect', 'libfusion', 'libdirectfb'))

    def check(self, symbols=None, attributes='', dynamic=None, header=None):
        return verify.validate(
            header if header is not None else self.header,
            attributes,
            symbols if symbols is not None else self.symbols,
            dynamic if dynamic is not None else self.dynamic
        )

    def test_actual_objdump_column_order(self):
        self.assertEqual(self.check(), [])
        self.assertNotRegex(self.symbols, r'__fxstat.*GLIBC_2.4')

    def test_missing_or_wrong_version_import_rejected(self):
        self.assertTrue(self.check(self.symbols.replace('__fxstat', '__fxstat64')))
        self.assertTrue(self.check(self.symbols.replace('GLIBC_2.4', 'GLIBC_2.34')))

    def test_missing_elf_markers_rejected(self):
        errors = self.check(header='Class: ELF64\nMachine: x86\nFlags: None')
        self.assertTrue(any('missing ELF target marker: ELF32' in e for e in errors))
        self.assertTrue(any('missing ELF target marker: ARM' in e for e in errors))
        self.assertTrue(any('missing ELF target marker: Version5 EABI' in e for e in errors))

    def test_no_glibc_info_rejected(self):
        errors = self.check(symbols='00001234 g DF .text 00000010 Base fstat\n')
        self.assertTrue(any('no GLIBC version information found' in e for e in errors))

    def test_missing_export_hardfloat_and_build_rpath_rejected(self):
        self.assertTrue(self.check(self.symbols.replace('Base fstat', 'Base other')))
        self.assertTrue(self.check(self.symbols.replace('Base __fdelt_chk', 'Base other')))
        self.assertTrue(self.check(attributes='Tag_ABI_VFP_args: VFP registers'))
        self.assertTrue(self.check(header=self.header + ', hard-float ABI'))
        self.assertTrue(self.check(dynamic=self.dynamic + '\n(RUNPATH) [/tmp/directfb]'))
        self.assertTrue(self.check(dynamic=self.dynamic + '\n(RPATH) [/tmp/directfb]'))
        self.assertTrue(self.check(dynamic=self.dynamic.replace('.so.0', '.so.6')))
        self.assertTrue(self.check(dynamic=''))

    def test_uint_symbol_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            dummy = Path(tmp) / 'dummy.so'
            dummy.write_bytes(b'not_elf')
            with patch.object(verify.subprocess, 'check_output', return_value=''):
                with self.assertRaisesRegex(ValueError, 'missing ABI metadata symbol'):
                    verify.uint_symbol(dummy, 'missing_sym')

            with patch.object(verify.subprocess, 'check_output', return_value='1: 00001000 4 OBJECT GLOBAL DEFAULT 1 my_sym'):
                with self.assertRaisesRegex(ValueError, 'expected ELF32 little endian'):
                    verify.uint_symbol(dummy, 'my_sym')

                # Valid ELF header but address outside segments
                data = bytearray(256)
                data[:6] = b'\x7fELF\x01\x01'
                struct.pack_into('<I', data, 28, 52)
                struct.pack_into('<HH', data, 42, 32, 1)
                struct.pack_into('<IIIII', data, 52, 1, 128, 0x5000, 0, 128)  # segment at 0x5000, sym at 0x1000
                dummy.write_bytes(data)
                with self.assertRaisesRegex(ValueError, 'ABI metadata outside file-backed segments'):
                    verify.uint_symbol(dummy, 'my_sym')

    def test_module_main_cli(self):
        with patch.object(verify.sys, 'argv', ['primebox-verify-module']):
            self.assertEqual(verify.main(), 1)

        with patch.object(verify.sys, 'argv', ['primebox-verify-module', 'test.so']), \
             patch.object(verify.subprocess, 'check_output') as mock_run:
            def side_effect(cmd, **kwargs):
                tool = cmd[0]
                if 'readelf' in tool and '-h' in cmd:
                    return self.header
                if 'readelf' in tool and '-A' in cmd:
                    return ''
                if 'readelf' in tool and '-d' in cmd:
                    return self.dynamic
                if 'objdump' in tool:
                    return self.symbols
                return ''
            mock_run.side_effect = side_effect
            self.assertEqual(verify.main(), 0)

        # Failure case with ABI check
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lib_dir = root / 'usr/lib'
            lib_dir.mkdir(parents=True)
            rx3_lib = lib_dir / 'libdirectfb-1.4.so.0'
            rx3_lib.touch()
            mod_file = root / 'test.so'
            mod_file.touch()

            with patch.object(verify.sys, 'argv', ['primebox-verify-module', str(mod_file), str(root)]), \
                 patch.object(verify.subprocess, 'check_output') as mock_run, \
                 patch.object(verify, 'uint_symbol', side_effect=[9, 8]):  # expected 9, actual 8
                def side_effect2(cmd, **kwargs):
                    tool = cmd[0]
                    if 'readelf' in tool and '-h' in cmd:
                        return self.header
                    if 'readelf' in tool and '-A' in cmd:
                        return ''
                    if 'readelf' in tool and '-d' in cmd:
                        return self.dynamic
                    if 'objdump' in tool:
                        return self.symbols
                    return ''
                mock_run.side_effect = side_effect2
                self.assertEqual(verify.main(), 1)


class LinkChecks(unittest.TestCase):
    def test_unversioned_modern_import_is_rejected(self):
        with patch.object(links, 'inspect', return_value=([], set(), {'__isoc23_strtol'})), patch.object(links.sys, 'argv', ['verify', '/tmp', '/tmp/module.so']):
            with self.assertRaisesRegex(SystemExit, '__isoc23_strtol'):
                links.main()

    def test_inspect_function(self):
        fake_dyn = '(NEEDED) Shared library: [libfoo.so]\n(NEEDED) Shared library: [libbar.so]'
        fake_syms = '''
Symbol table '.dynsym' contains 3 entries:
   Num:    Value  Size Type    Bind   Vis      Ndx Name
     0: 00000000     0 NOTYPE  LOCAL  DEFAULT  UND 
     1: 00001000    20 FUNC    GLOBAL DEFAULT    1 my_export@GLIBC_2.4
     2: 00000000     0 FUNC    GLOBAL DEFAULT  UND my_import@GLIBC_2.4
     3: 00002000    10 FUNC    WEAK   DEFAULT    1 weak_export
'''
        with patch.object(links.subprocess, 'check_output', side_effect=[fake_dyn, fake_syms]):
            needed, exports, imports = links.inspect(Path('/tmp/test.so'))
            self.assertEqual(needed, ['libfoo.so', 'libbar.so'])
            self.assertEqual(exports, {'my_export', 'weak_export'})
            self.assertEqual(imports, {'my_import'})

    def test_private_abi_is_read_from_elf_segment(self):
        data = bytearray(256)
        data[:6] = b'\x7fELF\x01\x01'
        struct.pack_into('<I', data, 28, 52)
        struct.pack_into('<HH', data, 42, 32, 1)
        struct.pack_into('<IIIII', data, 52, 1, 128, 0x1000, 0, 128)
        struct.pack_into('<I', data, 156, 9)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'lib.so'
            path.write_bytes(data)
            with patch.object(verify.subprocess, 'check_output', return_value='1: 00001000 40 OBJECT GLOBAL DEFAULT 1 dfb_core_systems'):
                self.assertEqual(verify.uint_symbol(path, 'dfb_core_systems', 28), 9)

    def test_links_main_cli(self):
        with patch.object(links.sys, 'argv', ['primebox-verify-links']):
            self.assertEqual(links.main(), 1)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'rootfs'
            root_lib = root / 'lib'
            root_lib.mkdir(parents=True)
            lib_dep = root_lib / 'libdep.so'
            lib_dep.touch()

            target_so = Path(tmp) / 'mod.so'
            target_so.touch()

            # Successful resolution
            with patch.object(links.sys, 'argv', ['primebox-verify-links', str(root), str(target_so)]), \
                 patch.object(links, 'inspect', side_effect=[
                     (['libdep.so'], set(), {'dep_func'}),
                     ([], {'dep_func'}, set())
                 ]):
                self.assertEqual(links.main(), 0)

            # Missing dependency library
            with patch.object(links.sys, 'argv', ['primebox-verify-links', str(root), str(target_so)]), \
                 patch.object(links, 'inspect', return_value=(['libmissing.so'], set(), set())):
                with self.assertRaisesRegex(SystemExit, 'requires missing RX3 library libmissing.so'):
                    links.main()


class RuntimeSafetyChecks(unittest.TestCase):
    def test_failed_device_unmount_never_deletes_dev(self):
        source = (ROOT / 'scripts/device/fix-dev.sh').read_text()
        prefix = 'mountpoint() { return 0; }\numount() { return 12; }\nrm() { echo DELETE; }\n'
        result = subprocess.run(['sh', '-c', prefix + source], capture_output=True, text=True)
        self.assertEqual(result.returncode, 12)
        self.assertNotIn('DELETE', result.stdout)


if __name__ == '__main__':
    unittest.main()
