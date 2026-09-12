# tools/

Workstation-side build scripts and patches. Nothing here runs on the Prime GO.

| Asset | Language | Purpose |
|---|---|---|
| [`build-directfb/`](build-directfb/) | C / patch | Patched DirectFB 1.4 fbdev module diff and compatibility shim |
| [`get-firmware.sh`](get-firmware.sh) | shell | Download official XDJ-RX3 firmware and GPL sources |

## Python Tools

All PrimeBox Python host tools are installed as part of the `primebox` package via `uv`:

```bash
# 1. Staging & firmware decryption
uv run primebox-prepare --firmware XDJRX3.zip --gpl part00.zip part01.zip --output extracted/staging

# 2. Apply player patches
uv run primebox-patch extracted/stock-rbp -o extracted/rbp-audio

# 3. Setup device launcher & udev rules
uv run primebox-launcher --remote root@YOUR_PRIMEGO --mode all

# 4. Verify DirectFB module and ELF linkage
uv run primebox-verify-module <module.so> extracted/XDJRX3-rootfs
uv run primebox-verify-links extracted/XDJRX3-rootfs scripts/shims/*.so
```
