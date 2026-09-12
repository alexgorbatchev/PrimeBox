import os
from pathlib import Path
import struct
import tempfile
import unittest

from primebox.patch.patch_rbp import LOAD_BIAS, PATCHES, apply_patches, main


class PatchRbpTests(unittest.TestCase):
    def _create_synthetic_stock(self) -> bytearray:
        max_offset = max(va - LOAD_BIAS for va, _, _, _ in PATCHES) + 4
        buf = bytearray(max_offset)
        for va, stock_word, _, _ in PATCHES:
            off = va - LOAD_BIAS
            struct.pack_into("<I", buf, off, stock_word)
        return buf

    def test_apply_patches_full_stock(self):
        buf = self._create_synthetic_stock()
        patched_buf, applied, already = apply_patches(buf)

        self.assertEqual(applied, len(PATCHES))
        self.assertEqual(already, 0)

        for va, _, patched_word, _ in PATCHES:
            off = va - LOAD_BIAS
            val = struct.unpack_from("<I", patched_buf, off)[0]
            self.assertEqual(val, patched_word)

    def test_apply_patches_idempotent(self):
        buf = self._create_synthetic_stock()
        patched_buf, applied1, already1 = apply_patches(buf)
        self.assertEqual(applied1, len(PATCHES))

        re_patched_buf, applied2, already2 = apply_patches(patched_buf)
        self.assertEqual(applied2, 0)
        self.assertEqual(already2, len(PATCHES))

        for va, _, patched_word, _ in PATCHES:
            off = va - LOAD_BIAS
            val = struct.unpack_from("<I", re_patched_buf, off)[0]
            self.assertEqual(val, patched_word)

    def test_apply_patches_partial_already(self):
        buf = self._create_synthetic_stock()
        for va, _, patched_word, _ in PATCHES[:5]:
            off = va - LOAD_BIAS
            struct.pack_into("<I", buf, off, patched_word)

        patched_buf, applied, already = apply_patches(buf)
        self.assertEqual(applied, len(PATCHES) - 5)
        self.assertEqual(already, 5)

        for va, _, patched_word, _ in PATCHES:
            off = va - LOAD_BIAS
            val = struct.unpack_from("<I", patched_buf, off)[0]
            self.assertEqual(val, patched_word)

    def test_apply_patches_mismatch_error(self):
        buf = self._create_synthetic_stock()
        first_va, old_word, _, note = PATCHES[0]
        off = first_va - LOAD_BIAS
        struct.pack_into("<I", buf, off, 0x12345678)

        expected_msg = f"mismatch at VA 0x{first_va:06x}: expected 0x{old_word:08x}, found 0x12345678 ({note})"
        with self.assertRaises(ValueError) as ctx:
            apply_patches(buf)
        self.assertEqual(str(ctx.exception), expected_msg)

    def test_apply_patches_truncated_binary(self):
        buf = bytearray(128)
        first_va = PATCHES[0][0]
        expected_msg = f"VA 0x{first_va:06x} outside file bounds (offset {first_va - LOAD_BIAS})"
        with self.assertRaises(ValueError) as ctx:
            apply_patches(buf)
        self.assertEqual(str(ctx.exception), expected_msg)

    def test_cli_main_success_and_check(self):
        buf = self._create_synthetic_stock()
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            stock_path = tmp / "stock_rbp"
            out_path = tmp / "rbp_audio"
            stock_path.write_bytes(buf)

            # Test --check mode
            ret_check = main([str(stock_path), "--check"])
            self.assertEqual(ret_check, 0)
            self.assertFalse(out_path.exists())

            # Test standard patching
            ret_patch = main([str(stock_path), "-o", str(out_path)])
            self.assertEqual(ret_patch, 0)
            self.assertTrue(out_path.exists())

            patched_bytes = out_path.read_bytes()
            for va, _, patched_word, _ in PATCHES:
                off = va - LOAD_BIAS
                val = struct.unpack_from("<I", patched_bytes, off)[0]
                self.assertEqual(val, patched_word)

    def test_cli_main_mismatch_returns_2(self):
        buf = bytearray(b"NOT_A_VALID_BINARY_AT_ALL_SHORT")
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            corrupt_path = tmp / "corrupt_rbp"
            corrupt_path.write_bytes(buf)

            ret = main([str(corrupt_path)])
            self.assertEqual(ret, 2)
