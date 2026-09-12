# Firmware Staging Tools (`tools/bundle/`)

This directory contains standalone automation for extracting and staging the Pioneer XDJ-RX3 firmware and userland filesystem without requiring Docker, root permissions, or kernel loopback mounts.

Contributed by [@silonelnilo (PrimeBox_Prime2)](https://github.com/silonelnilo/PrimeBox_Prime2).

---

## Prerequisites

The staging script is pure Python 3 and requires:

1. **Python Dependencies**:
   - `pycryptodome` (for AES-256-CBC cryptoloop sector decryption)
   - `pycdlib` (for ISO 9660 filesystem parsing)

   Install via `uv`:
   ```bash
   uv pip install pycryptodome pycdlib
   ```

2. **System Utilities**:
   - `unzip` (supporting Deflate64 compression used in AlphaTheta source archives)

---

## Usage

Provide the official XDJ-RX3 firmware `.zip` and both GPL source parts:

```bash
python3 tools/bundle/prepare-rx3.py \
    --firmware /path/to/XDJ-RX3_v120.zip \
    --gpl /path/to/part00.zip /path/to/part01.zip \
    --output extracted/staging
```

### What it does:

1. **Extracts AES Key**: Unpacks the GPL source archive parts to locate `aes256.key` from `initramfs`.
2. **Decrypts Firmware**: Performs sector-by-sector AES-256-CBC decryption of `XDJRX3.UPD` to memory.
3. **Parses ISO**: Reads the decrypted ISO 9660 volume in memory via `pycdlib`.
4. **Unpacks Cramfs**: Unpacks `rootfs.cramfs` directly in Python, translating absolute chroot symlinks into confined relative links.
5. **Extracts Subsystems**: Unpacks `pdj.tar.gz` (`rbp` binary), `gui.tar.gz` (bitmap & TTF fonts), and `settings.tar.gz`.
6. **Cleans Up**: Deletes temporary key material and concatenated source archives to maintain a clean staging area.
