# tools/

Workstation-side tooling. Nothing here runs on the Prime GO.

| Tool | Language | Purpose |
|---|---|---|
| [`rx3dec/`](rx3dec/) | Rust | decrypt XDJ-RX3 `.UPD` → ISO 9660 image |
| [`patch-rbp/`](patch-rbp/) | Python | apply PrimeBox interoperability patches to `rbp` |
| [`build-directfb/`](build-directfb/) | C / patch | patched DirectFB 1.4 fbdev module for the Rockchip fb |
| [`get-firmware.sh`](get-firmware.sh) | shell | download the official XDJ-RX3 v1.20 firmware |

## Suggested order

```bash
# 1. get the firmware
./tools/get-firmware.sh                       # -> XDJ-RX3_v120.zip

# 2. decrypt (needs Rust; see tools/rx3dec/README.md)
cd tools/rx3dec && cargo build --release
./target/release/rx3dec ~/XDJ-RX3_v120/XDJ-RX3.UPD ../../keys/aes256.key XDJRX3.iso
cd ../..

# 3. extract the ISO (see docs/01-firmware-extraction.md)

# 4. patch rbp
python3 tools/patch-rbp/rbp_patch.py extracted/XDJRX3/pdj/rbp -o rbp-audio

# 5. build the patched DirectFB fbdev module (see tools/build-directfb/)
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
