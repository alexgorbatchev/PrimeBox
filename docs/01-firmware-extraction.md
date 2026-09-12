# 01 — Firmware extraction

Everything starts with the XDJ-RX3 firmware update file. This document explains
the container format, the decryption key, and how to get from the official
`.zip` to the files PrimeBox needs (`rbp`, libs, fonts, `edb_streamd`).

## 1. Get the firmware

Official download (AlphaTheta):

```
https://downloads.support.alphatheta.com/firmwares/all-in-one-dj-systems/XDJ-RX3/XDJ-RX3_v120.zip
```

Use [`tools/get-firmware.sh`](../tools/get-firmware.sh) or download manually.
Unzip to get `XDJ-RX3_v120/XDJ-RX3.UPD` (**69,171,216 bytes**, v1.20).

> PrimeBox is developed against **v1.20**. Other versions may work but the
> patch addresses in `src/primebox/patch/` are specific to the v1.20 binary
> (md5 `4f2efcfc0c9e3f539289f863acfddcc6`).

## 2. The key

PrimeBox does **not** ship the key. Obtain it from AlphaTheta's own GPL
source distribution and place it at `keys/aes256.key` (gitignored). See
[`keys/README.md`](../keys/README.md) for how to find it.

The RX3 updater uses:

```sh
cat $aeskey | losetup -e aes $NOHASH -p 0 $dev $filename
```

which means the effective AES-256 key is the **first 31 bytes of the first
line** of the key file plus a NUL (32 bytes total). `tools/rx3dec` performs
that derivation itself.

## 3. Container formats

Pioneer `.UPD` files come in (at least) two container flavours:

### 3a. XDJ-RX3 — AES-256-CBC "cryptoloop" (this device)

The XDJ-RX3 v1.20 `.UPD` is **not** LUKS. It is a raw, sector-wise
AES-256-CBC image in the classic Linux `cryptoloop` / `losetup -e aes -p 0`
format:

```
[ AES-256-CBC-encrypted ISO 9660 image, 512-byte aligned ]
[ 16-byte plaintext trailer: "MODELVER\0" + CRC32       ]

Cipher : AES-256-CBC, applied independently to each 512-byte sector
IV     : little-endian u32 sector index + 12 zero bytes
Key    : first 31 bytes of key file line 1 + NUL (32 bytes)
```

The 16-byte trailer identifies the model/version and a CRC32. `cryptsetup
luksDump` rejects the file — that is expected.

The decryption approach here was inspired by
[`nsaintot/cdj3k-emu`](https://github.com/nsaintot/cdj3k-emu/tree/main).

### 3b. CDJ-3000 / other players — LUKS1

Other models (e.g. `CDJ3Kv322.UPD`) are genuine **LUKS1** containers at offset
0 (`LUKS\xba\xbe`, `aes-xts-plain64`, sha256, 512-bit master key). Those need
`cryptsetup` + `losetup` (see the [`cdj3k-emu` `tools/upd-decrypt`
helper](https://github.com/nsaintot/cdj3k-emu/tree/main/tools/upd-decrypt)) or a
pure-Rust LUKS decryptor. The `aes256.key` supplied for the RX3 is **not** the
CDJ-3000 key.

> **Credit:** the [`cdj3k-emu`](https://github.com/nsaintot/cdj3k-emu) project
> (nsaintot) is what showed us how Pioneer `.UPD` images are decrypted in the
> first place — its `tools/upd-decrypt` helper (LUKS keyfile + `losetup`)
> was the reference that led to the XDJ-RX3 cryptoloop analysis above. Many
> thanks to them.

## 4. Extract and stage with `primebox-prepare`

PrimeBox provides a single pure-Python staging command (`uv run primebox-prepare`) that handles key recovery, AES-256-CBC decryption, ISO parsing, and userland decompression in one command without requiring root, Docker, or external tools:

```bash
uv run primebox-prepare \
    --firmware /path/to/XDJ-RX3_v120.zip \
    --gpl /path/to/pioneerdj_xdj_rx3.tar.bz2.00.zip /path/to/pioneerdj_xdj_rx3.tar.bz2.01.zip \
    --output extracted/XDJRX3
```

### Staging results:

* `extracted/XDJRX3/pdj/` — contains `rbp` (the player binary), launch scripts.
* `extracted/XDJRX3/gui/` — contains mandatory fonts (`system/fontdata/*.ttf`) and bitmaps.
* `extracted/XDJRX3/rootfs/` — base Linux rootfs (`glibc 2.13`, DirectFB libraries, `edb_streamd`).
* `extracted/XDJRX3/settings/` — default configuration files.

Copy the stock player binary to the staging folder:

```bash
cp extracted/XDJRX3/pdj/rbp extracted/stock-rbp
```

### The `gui` partition (fonts are essential)

`rbp` cannot start without its NS bitmap fonts and `imagedata.dat`. They are in
`images/gui.tar.gz`:

```bash
mkdir -p extracted/XDJRX3-gui
tar xzf extracted/XDJRX3/images/gui.tar.gz -C extracted/XDJRX3-gui
ls extracted/XDJRX3-gui/pset/fontdata/   # NS_FONT_ID_*.bin
ls extracted/XDJRX3-gui/system/fontdata/ # *.ttf
```

## 5. What you should end up with

```
extracted/
├── XDJRX3/
│   ├── pdj/           # player binary & launch scripts
│   ├── gui/           # fonts (system/fontdata/*.ttf) and bitmaps
│   ├── rootfs/        # glibc 2.13 runtime, DirectFB libs, edb_streamd
│   └── settings/      # default settings
└── stock-rbp          # pdj/rbp, md5 4f2efcfc0c9e3f539289f863acfddcc6
```

Verify the stock binary hash before patching:

```bash
md5sum extracted/stock-rbp
# 4f2efcfc0c9e3f539289f863acfddcc6  extracted/stock-rbp
```

## 7. Next step

Patch the binary:

```bash
uv run primebox-patch stock-rbp -o rbp-audio
md5sum rbp-audio
# 3706c68f7242779d46afa09f35a39acf  rbp-audio
```

See [10 — Memory map](10-memory-map.md) and
[12 — Patches](12-patches.md) for what each
patch does.
