import importlib.util
import io
import os
from pathlib import Path, PurePosixPath
import struct
import tarfile
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import zipfile
import zlib

ROOT = Path(__file__).resolve().parents[1]
spec_prep = importlib.util.spec_from_file_location('prepare_rx3', ROOT / 'tools/bundle/prepare-rx3.py')
prep = importlib.util.module_from_spec(spec_prep)
spec_prep.loader.exec_module(prep)


class PrepareRx3Tests(unittest.TestCase):
    def test_is_relative_to(self):
        p1 = Path('/tmp/foo/bar')
        p2 = Path('/tmp/foo')
        p3 = Path('/var/other')
        self.assertTrue(prep.is_relative_to(p1, p2))
        self.assertFalse(prep.is_relative_to(p3, p2))

    def test_confined_name(self):
        self.assertEqual(prep.confined_name('foo/bar'), PurePosixPath('foo/bar'))
        with self.assertRaises(ValueError):
            prep.confined_name('/absolute/path')
        with self.assertRaises(ValueError):
            prep.confined_name('../relative/escape')

    def test_extract_regular_tar(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / 'out'
            out_dir.mkdir()

            buf = io.BytesIO()
            with tarfile.open(fileobj=buf, mode='w:gz') as tar:
                # Add directory
                dir_info = tarfile.TarInfo(name='subdir')
                dir_info.type = tarfile.DIRTYPE
                tar.addfile(dir_info)

                # Add file
                data = b'hello world'
                file_info = tarfile.TarInfo(name='subdir/test.txt')
                file_info.size = len(data)
                file_info.mode = 0o644
                tar.addfile(file_info, io.BytesIO(data))

            prep.extract_regular_tar(buf.getvalue(), out_dir)
            self.assertEqual((out_dir / 'subdir/test.txt').read_bytes(), b'hello world')

    def test_extract_regular_tar_unsupported_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / 'out'
            out_dir.mkdir()

            buf = io.BytesIO()
            with tarfile.open(fileobj=buf, mode='w:gz') as tar:
                fifo_info = tarfile.TarInfo(name='myfifo')
                fifo_info.type = tarfile.FIFOTYPE
                tar.addfile(fifo_info)

            with self.assertRaisesRegex(ValueError, 'unsupported tar entry'):
                prep.extract_regular_tar(buf.getvalue(), out_dir)

    def test_unpack_cramfs_corrupt_magic(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, 'unsupported cramfs'):
                prep.unpack_cramfs(b'invalid_cramfs_magic_data', Path(tmp))

    def test_unpack_cramfs_truncated(self):
        with tempfile.TemporaryDirectory() as tmp:
            header = struct.pack('<III', 0x28cd3d45, 1000000, 0)
            with self.assertRaisesRegex(ValueError, 'truncated cramfs'):
                prep.unpack_cramfs(header + bytes(64), Path(tmp))

    def test_unpack_cramfs_valid_minimal(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / 'extracted'
            dest.mkdir()

            comp = zlib.compress(b'hello')
            file_data_start = 192 + 4
            file_data_end = file_data_start + len(comp)

            buf = bytearray(256)
            struct.pack_into('<III', buf, 0, 0x28cd3d45, 256, 0)
            # Root inode at 64
            struct.pack_into('<III', buf, 64, 16877, 16, 2048)

            # Child entry at 128
            struct.pack_into('<III', buf, 128, 33188, 5, 3073)
            buf[140:144] = b'test'

            # File block pointer at 192
            struct.pack_into('<I', buf, 192, file_data_end)
            buf[file_data_start:file_data_end] = comp

            count = prep.unpack_cramfs(bytes(buf), dest)
            self.assertEqual(count, 2)
            self.assertEqual((dest / 'test').read_bytes(), b'hello')

    def test_unpack_cramfs_with_symlinks(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / 'extracted'
            dest.mkdir()

            # Inode with symlink: mode=0120777 = 41471
            link_target = b'test'
            comp = zlib.compress(link_target)
            file_data_start = 224 + 4
            file_data_end = file_data_start + len(comp)

            buf = bytearray(300)
            struct.pack_into('<III', buf, 0, 0x28cd3d45, 300, 0)
            # Root inode at 64, size 32 (2 entries of 16 bytes)
            struct.pack_into('<III', buf, 64, 16877, 32, 2048)

            # Entry 1 at 128: regular file "test" (size 5, offset 192)
            struct.pack_into('<III', buf, 128, 33188, 5, 3073)
            buf[140:144] = b'test'

            # Entry 2 at 144: symlink "link" (size 4, offset 224 >> 2 = 56, namelen 4 >> 2 = 1)
            struct.pack_into('<III', buf, 144, 41471, 4, 3585)
            buf[156:160] = b'link'

            # File 1 data
            comp1 = zlib.compress(b'hello')
            struct.pack_into('<I', buf, 192, 196 + len(comp1))
            buf[196:196 + len(comp1)] = comp1

            # Link data
            struct.pack_into('<I', buf, 224, file_data_end)
            buf[file_data_start:file_data_end] = comp

            count = prep.unpack_cramfs(bytes(buf), dest)
            self.assertEqual(count, 3)
            self.assertTrue((dest / 'link').is_symlink())

    def test_main_cli_pipeline(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out_dir = root / 'staging_out'
            fw_zip = root / 'fw.zip'
            gpl0 = root / 'gpl0.zip'
            gpl1 = root / 'gpl1.zip'

            # Create mock GPL zip 0
            with zipfile.ZipFile(gpl0, 'w') as z:
                z.writestr('pioneerdj_xdj_rx3.tar.bz2.00', b'fake_part00')
            with zipfile.ZipFile(gpl1, 'w') as z:
                z.writestr('pioneerdj_xdj_rx3.tar.bz2.01', b'fake_part01')

            # Create mock firmware zip
            with zipfile.ZipFile(fw_zip, 'w') as z:
                z.writestr('XDJRX3.UPD', bytes(69171216))

            out_dir_fail = root / 'staging_fail'
            out_dir_success = root / 'staging_success'

            # Test invalid gpl parts
            with patch.object(prep.sys, 'argv', ['prepare-rx3.py', '--firmware', str(fw_zip), '--gpl', str(gpl0), str(gpl0), '--output', str(out_dir_fail)]):
                with self.assertRaisesRegex(ValueError, 'both GPL source parts are required'):
                    prep.main()

            # Create real bz2 tar with initramfs
            initramfs_buf = io.BytesIO()
            with tarfile.open(fileobj=initramfs_buf, mode='w:gz') as itar:
                key_info = tarfile.TarInfo(name='initramfs/usr/local/pdj/aes256.key')
                key_bytes = b'01234567890123456789012345678901\n'
                key_info.size = len(key_bytes)
                itar.addfile(key_info, io.BytesIO(key_bytes))

            source_tar_buf = io.BytesIO()
            with tarfile.open(fileobj=source_tar_buf, mode='w:bz2') as star:
                init_info = tarfile.TarInfo(name='pioneerdj_xdj_rx3/initramfs.tar.gz')
                init_bytes = initramfs_buf.getvalue()
                init_info.size = len(init_bytes)
                star.addfile(init_info, io.BytesIO(init_bytes))

            def mock_unzip(cmd, stdout=None, **kwargs):
                stdout.write(source_tar_buf.getvalue())
                return MagicMock(returncode=0)

            # Test full mock execution
            with patch.object(prep.sys, 'argv', ['prepare-rx3.py', '--firmware', str(fw_zip), '--gpl', str(gpl0), str(gpl1), '--output', str(out_dir_success)]), \
                 patch('subprocess.run', side_effect=mock_unzip), \
                 patch.object(prep.AES, 'new') as mock_aes, \
                 patch('pycdlib.PyCdlib') as mock_pycdlib, \
                 patch.object(prep, 'unpack_cramfs', return_value=42), \
                 patch.object(prep, 'extract_regular_tar'):

                # Mock AES decryption returning CD001 ISO header at sector 64
                mock_cipher = MagicMock()
                mock_dec = bytearray(69171200)
                mock_dec[32769:32774] = b'CD001'
                mock_cipher.decrypt.return_value = bytes(512)
                mock_aes.return_value = mock_cipher

                # Mock pycdlib
                mock_iso = MagicMock()
                mock_iso.walk.return_value = [('/', [], ['rootfs.cramfs', 'pdj.tar.gz', 'gui.tar.gz', 'settings.tar.gz'])]
                mock_pycdlib.return_value = mock_iso

                with patch('builtins.bytearray', return_value=mock_dec):
                    prep.main()

                self.assertTrue(out_dir_success.exists())


if __name__ == '__main__':
    unittest.main()
