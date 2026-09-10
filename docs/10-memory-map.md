# 10 — Memory map & patch reference

All addresses are for the **stock XDJ-RX3 v1.20 `rbp`** (non-PIE, load bias
`0x8000`, so `file offset = VA − 0x8000`). Treat this as a quick lookup; the
full instruction-level table is
[`tools/patch-rbp/PATCHES.md`](../tools/patch-rbp/PATCHES.md) and is
executable via [`tools/patch-rbp/rbp_patch.py`](../tools/patch-rbp/rbp_patch.py).

## 1. Binary patches (by feature)

| Feature | VA(s) | What |
|---|---|---|
| USB/mount/panel base fixes | `0x020af0`, `0x020afc`, `0x020b08`, `0x020c54–64`, `0x159ce8` | startup short-circuits + `/media/usb1/sda1` path |
| Browse/USB routing cave | `0x09b678`, `0x09b67c` | code cave → `setBrowseMode(12)` |
| Key dispatch / throw hardening | `0x2cf7a0`, `0x366cd0`, `0x3779c0`, `0x37ad90–adb0`, `0x37b5d0`, `0x37bc30–bc38`, `0x37bf34–bf68`, `0x37c048–c364`, `0x37c710` | makes `IKeyManager` survive `FixedAddressArray` throws / bounds |
| Power-manager NULL-`this` guards | `0x121d9c`, `0x12203c`, `0x122078`, `0x2c6bf0`, `0x2c7004`, `0x32e728`, `0x3871d0` | no Pioneer PM hardware |
| Display waveform gate | `0x24fc88`, `0x24fc8c` | always create/render scrolling waveform |
| Touch caution gate | `0x2dc228`, `0x2dc46c` | ignore browse caution id |
| Touch drag-scroll | `0x363774`, `0x363794` | fix list-scroll deadlock |
| Panel/comm helper | `0x3664b4` | startup |
| Touch startup (A/B/D/E/G) | `0x2bb87c`, `0x2d6cb0`, `0x31ddb0`, `0x31ddb8`, `0x366530` | start UI, break `postMessage` deadlock |
| Audio device list | `0x3c665c` | force RX3 device list on Rockchip |
| udev paths | `0x4dede4–4e0e78` | `/proc/udev_*` → `/tmp/udev_*` |

Resulting binary: md5 `3706c68f7242779d46afa09f35a39acf`. The patcher is
verified to reproduce it byte-for-byte from the stock binary.

## 2. Runtime globals (live memory)

| Address | Type | Meaning | Correct value on Prime GO |
|---|---|---|---|
| `0x2685f2c` | `void*` | `uiObjectManager` global → object | heap ptr |
| `*(0x2685f2c)+100` | `void*` | `ui::KeyManager` | heap ptr |
| `0x03256888` | u32 | drive 0 **Kind 2** (USB 1) detect flag | `2` |
| `0x0325688c` | 168 B | `DevicePropertyInfo` (USB 1) | populated natively |
| `0x03256944` | u32 | drive 0 **Kind 3** (USB 2) detect flag | `0` (suppressed) |
| `0x03256a00` | u32 | drive 0 Kind 4 (LINK) | — |
| `0x0326f8b4` | u32 | `uiConnectedMedia` bitmask | `0x2` (USB 1) |
| `0x0326f8b8` | u32 | `browseMode` | `5` list, `12` source, `1` decks |
| `0x0326f8bc` | u32 | `browseDevice` | `3` (USB 1) |
| `0x0326e128` | u32 | display refresh flag | `1` |
| `0x05a191fc` | u32 | browse caution message id | `0` (cleared) |
| `0x0114ca10` | u32[4] | `sDbDeviceCheckFlg` | `[1,0,0,0]` |
| `0x0114c2d0` | `void*` | `BrowseUiIf` singleton | ptr |
| `0x01149f50` | u32 | mixer ch 1 route | `0x01149f08` (deck 1) |
| `0x01149f54` | u32 | mixer ch 2 route | `0x01149f10` (deck 2) |
| `0x0551ab28` | struct | `ui_ListDispData` | list state |
| `0x0327488c` | table | `BrowseKeyTable` (16 B stride) | slot 3 = `UiKey_Usb1` |

### `DevicePropertyInfo` (`0x0325688c`)

| Offset | Type | Meaning |
|---|---|---|
| +0 | UTF-16LE | volume label |
| +120 | u32 | song count |
| +124 | u8 | colour |
| +126 | u8 | DB ready (must be 1) |
| +128 | u32 | playlist count |
| +132 / +136 | u32 / u32 | total capacity high / low word |
| +140 / +144 | u32 / u32 | free space high / low word |

## 3. Function reference (used while reverse-engineering)

| VA | Symbol |
|---|---|
| `0x00320a28` | `ui::UsbMountManager::run` |
| `0x00321a98` | `ui::UsbStorageManager::notify_usb_mount` |
| `0x0033ba30` | `ui::DbProxy::reqAttach` |
| `0x00141d9c` | `db::DbIF::mount` |
| `0x000f93e4` | `Total_MainUsbMessageProc` |
| `0x0027d374` | `compConnectedMedia` |
| `0x0011a3cc` | `UiKey_Usb1` |
| `0x000cfc58` | `BrowseUiIf::InputKey` |
| `0x00363a74` | `TouchAdValueHysteresis::procAdaptValue` |
| `0x002dc104` | `solveCoordToKey` |
| `0x002dc440` | `TouchPanelHandler::touchOn` |
| `0x002d734c` | `commRxDataProc` |
| `0x00363730` | `TouchAreaProc_ListScroll::holdTouch` |
| `0x001a40c0` | `DS_HW_Core_Surface_Create` |
| `0x003c665c` | `ALSAAudioIODeviceType::scanForDevices` + `0x54` |
| `0x000104d0` | audio-init branch (stock already enabled) |
| `0x003064cc` | `ui::PlayerInnards::onPhysicalKey` |
| `0x00302a30` | `ui::PlayerInnards::onKey_TempoSlider` |
| `0x002cfd5c` | `ui::Mixer::asEventCode` |
| `0x00250e54` | `djengine::c_str(EnBeatEffectSelectChannel)` |

## 4. Screen geometry constants

| Value | Where |
|---|---|
| logical UI | 1280 × 800 |
| physical fb | 800 × 1280 × 32, `yres_virtual` 3840, pitch 3200 |
| RGB565 pitch | 2560 (1280 × 2) |
| DirectFB RGB16 | `0x00200801` |
| DirectFB RGB32 | `0x00400c03` |

## 5. Reading live memory

No debugger is needed; root can read `/proc/<pid>/mem`:

```sh
RBP=$(pgrep -f '/root/pdj/rbp' | head -1)
# read 32-bit at VA 0x03256888
python3 - <<'PY'
import struct, subprocess
pid = int(subprocess.check_output(['pgrep','-f','/root/pdj/rbp']).split()[0])
with open(f'/proc/{pid}/mem','rb') as f:
    f.seek(0x03256888); print(struct.unpack('<I', f.read(4))[0])
PY
```

Writing (used only for diagnostics, never in the shipped runtime) works the
same way with `open(...,'r+b')`.
