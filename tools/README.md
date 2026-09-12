# tools/

Workstation-side tooling. Nothing here runs on the Prime GO.

| Tool | Language | Purpose |
|---|---|---|
| [`bundle/`](bundle/) | Python | pure-Python all-in-one staging pipeline (`prepare-rx3.py`) |
| [`patch-rbp/`](patch-rbp/) | Python | apply PrimeBox interoperability patches to `rbp` |
| [`build-directfb/`](build-directfb/) | C / patch / Python | patched DirectFB 1.4 fbdev module + verification tooling |
| [`get-firmware.sh`](get-firmware.sh) | shell | download official XDJ-RX3 firmware and GPL sources |

## Suggested order

```bash
# 1. get the firmware
./tools/get-firmware.sh                       # -> XDJ-RX3_v120.zip + GPL source parts

# 2. extract & stage rootfs (pure Python; see tools/bundle/README.md)
python3 tools/bundle/prepare-rx3.py \
    --firmware XDJ-RX3_v120.zip \
    --gpl pioneerdj_xdj_rx3.tar.bz2.00.zip pioneerdj_xdj_rx3.tar.bz2.01.zip \
    --output extracted/XDJRX3

# 3. patch rbp
python3 tools/patch-rbp/rbp_patch.py extracted/XDJRX3/pdj/rbp -o rbp-audio

# 4. build the patched DirectFB fbdev module (see tools/build-directfb/)
```

## `patch-rbp`

`rbp_patch.py` contains the complete, verified instruction table that turns the
stock v1.20 `rbp` (md5 `4f2efcfc0c9e3f539289f863acfddcc6`) into `rbp-audio`
(md5 `3706c68f7242779d46afa09f35a39acf`). It is idempotent and validates the
stock words before writing.

[`PATCHES.md`](patch-rbp/PATCHES.md) explains what each patch does.

## `build-directfb`

Contains `directfb-full.diff`, our complete patch against DirectFB 1.4.16.
No upstream DirectFB sources are shipped; you fetch them and apply the diff.
See the [README](build-directfb/README.md).

## Credit

The `.UPD` decryption approach (and the keyfile format used by the Pioneer
updaters) was learned from
[`nsaintot/cdj3k-emu`](https://github.com/nsaintot/cdj3k-emu/tree/main), whose
`tools/upd-decrypt` helper showed how the images are unwrapped. Thanks!
