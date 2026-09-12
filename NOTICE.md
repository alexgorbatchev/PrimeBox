# Notice, copyright and legal

PrimeBox is an independent interoperability/preservation project. It is **not
affiliated with, endorsed by, or sponsored by** Pioneer DJ, AlphaTheta
Corporation, Denon DJ, inMusic, or any of their subsidiaries.

## What this repository contains

* Original shell scripts, C sources, Python/Rust tooling and documentation
  written for this project. These are licensed MIT (see `LICENSE`).
* Interoperability **patch instructions** (addresses + replacement
  instructions) for the `rbp` binary. These are functional changes required to
  run the binary on different hardware — not a copy of the binary and not
  Pioneer source code.
* A **diff** against **DirectFB 1.4** (`tools/build-directfb/directfb-full.diff`).
  DirectFB is LGPL-2.1; that diff (and anything built from it) remains LGPL.
  No upstream DirectFB source files are shipped. The DirectFB author credits /
  license header remain in the fetched upstream tree.

## What this repository does **not** contain

* No XDJ-RX3/XDJ-AZ/CDJ firmware (`.UPD`), no decrypted firmware ISO, no
  `rootfs`, no `rbp`/`rb` executable, and no other Pioneer/AlphaTheta binaries.
* No Denon DJ / Engine OS files or binaries.
* No rekordbox music, playlists, analysis files or databases.
* No firmware decryption key. You obtain `keys/aes256.key` yourself from
  AlphaTheta's GPL distribution; the path is gitignored.

You must own/obtain the hardware and firmware yourself. The scripts here
operate on files **you** supply.

## Legal caveats

* Firmware decryption may be restricted in your jurisdiction. Check your local
  law before using the extraction tools. The key is published by AlphaTheta
  themselves, but reverse-engineering rules (e.g. DMCA §1201, EUCD) vary.
* Patching and running a vendor application on third-party hardware may violate
  the vendor's EULA. This project is offered for research, repair,
  preservation and personal interoperability only.
* Installing this on your device can brick it or void its warranty. **You do
  everything at your own risk.**

## Trademarks

*Pioneer DJ*, *AlphaTheta*, *rekordbox*, *XDJ-RX3*, *CDJ* and related marks are
trademarks of their respective owners. *Denon DJ*, *Prime GO* and *Engine OS*
are trademarks of inMusic Brands, Inc. All trademarks are used here in a
descriptive, nominative sense only.

## Acknowledgements

* **[nsaintot/cdj3k-emu](https://github.com/nsaintot/cdj3k-emu/tree/main)** —
  thanks to this project for demonstrating how Pioneer `.UPD` firmware images
  are decrypted (its `tools/upd-decrypt` LUKS keyfile + `losetup` helper). That
  work is the reference this project's `rx3dec` builds on.
* **[@silonelnilo](https://github.com/silonelnilo/PrimeBox_Prime2)** —
  thanks for contributing modern GLIBC 2.13 toolchain hardening (`legacy-scan.c`, 32-bit time/offset pinning),
  device chroot mountpoint safety guards (`fix-dev.sh`), ELF and DirectFB verification tooling
  (`verify-module.py`, `verify-rx3-links.py`), and the pure-Python staging pipeline (`prepare-rx3.py`).

## Third-party components

| Component | License | Used for |
|---|---|---|
| DirectFB 1.4 | LGPL-2.1 | display stack (patched fbdev driver) |
| JUCE | GPL / commercial | audio + UI framework inside `rbp` |
| ALSA / alsa-lib | LGPL | audio |
| glibc 2.13 (RX3 rootfs) | LGPL | soft-float runtime |
| RustCrypto `aes` / `cbc` | MIT/Apache-2.0 | `.UPD` decryptor |
| BusyBox | GPL-2.0 | runtime shell |

See each project for the full license text.
