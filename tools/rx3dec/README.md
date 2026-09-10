# tools/rx3dec

A small Rust decryptor for **XDJ-RX3 `.UPD`** firmware containers.

## Format

```
[ AES-256-CBC-encrypted ISO 9660 image, 512-byte aligned ]
[ 16-byte plaintext trailer: "MODELVER\0" + CRC32       ]

cipher : AES-256-CBC per 512-byte sector
IV     : little-endian u32 sector index + 12 zero bytes
key    : first 31 bytes of line 1 of the key file + NUL (32 bytes)
```

This is the classic Linux `cryptoloop` / `losetup -e aes -p 0` scheme used by
the RX3 updater (`pdj/decrypt_autoexec.sh`).

> Other Pioneer `.UPD` files (e.g. CDJ-3000) are genuine **LUKS1** containers
> and need a different tool. See `docs/01-firmware-extraction.md`.

## Build & run

```bash
cargo build --release
./target/release/rx3dec XDJRX3.UPD ../../keys/aes256.key XDJRX3.iso
```

On success it reports the derived key and verifies the ISO 9660 `CD001`
signature at sector 64.

## Dependencies

* [`RustCrypto/aes`](https://crates.io/crates/aes) 0.8
* [`RustCrypto/block-modes/cbc`](https://crates.io/crates/cbc) 0.1

Both MIT/Apache-2.0.
