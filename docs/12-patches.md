# rbp patch reference

Source of truth: `src/primebox/patch/patch_rbp.py`. Every entry is
`(VA, stock_word, patched_word, note)`; the patcher verifies the stock word
before writing and is idempotent. `VA = file_offset + 0x8000`.

* stock: md5 `4f2efcfc0c9e3f539289f863acfddcc6`
* patched (`rbp-audio`): md5 `3706c68f7242779d46afa09f35a39acf`

Words are shown as little-endian u32 hex. `E320F000` is `nop`,
`E1A00000` is `mov r0,r0` (also a nop), `E12FFF1E` is `bx lr`.

---

## 1. Startup / panel / USB base

| VA | stock | patched | purpose |
|---|---|---|---|
| `0x020af0` | `0A000022` | `E1000000` | short-circuit vendor startup branch |
| `0x020afc` | `EB0490F4` | `E1000000` | short-circuit vendor startup call |
| `0x020b08` | `0A000013` | `E1000000` | short-circuit vendor startup branch |
| `0x020c54` | `003FE218` | `64656D2F` | build `"/media/usb1/sda1"` (1/5) |
| `0x020c58` | `02435738` | `752F6169` | (2/5) |
| `0x020c5c` | `024355E8` | `2F316273` | (3/5) |
| `0x020c60` | `004E3054` | `31616473` | (4/5) |
| `0x020c64` | `004D52C0` | `004D5200` | (5/5) |
| `0x159ce8` | `E5C9300F` | `E320F000` | nop vendor status write |

## 2. Browse / USB routing code cave

| VA | stock | patched | purpose |
|---|---|---|---|
| `0x09b678` | `00000000` | `E3A01000` | cave: `mov r1,#0` |
| `0x09b67c` | `00000000` | `EA0B8337` | cave: branch to `setBrowseMode(12)` |

## 3. Panel comm deadlock & touch startup

| VA | stock | patched | purpose |
|---|---|---|---|
| `0x2bb87c` | `012FFF1E` | `E1A00000` | `IReceptionForMAIN::startUp` never early-returns on null global |
| `0x2d6cb0` | `18BD8038` | `E1A00000` | `TouchPanel::openDevice` never bails on `isThreadRunning` |
| `0x31ddb0` | `1A000014` | `E1A00000` | `startUp` never bails on panel flag |
| `0x31ddb8` | `0A00000E` | `EAFFFFFF` | `startUp` skips failing internal init |
| `0x3664b4` | `E0633000` | `E3A03000` | comm helper: `r3 = 0` |
| `0x366530` | `1A000004` | `EA000004` | `PanelComPeerLinux::postMessage` wait-for-panel loop removed (startup deadlock) |

## 4. Key dispatch / throw hardening ("fixthrow")

`rbp`'s key dispatcher throws when the front panel never registers keys, and
the exception is uncaught → `SIGABRT` / `SIGSEGV`. These make the dispatcher
never throw, returning clean status instead:

| VA | stock | patched | purpose |
|---|---|---|---|
| `0x2cf7a0` | `E3A00004` | `E8BD8070` | `UiTimer` throw path: clean pop/return |
| `0x366cd0` | `E3A01002` | `E3001802` | `socketpair()` opened `O_NONBLOCK` |
| `0x3779c0` | `E92D4FF8` | `E12FFF1E` | `UiTimer` callback immediate `bx lr` |
| `0x37ad90` | `0A00014B` | `0A000007` | `KeyInput` slot search bounded |
| `0x37ad94` | `E5900004` | `EA000019` | `KeyInput` slot search skip |
| `0x37adb0` | `1A000012` | `EA000012` | `KeyInput` slot search skip |
| `0x37b5d0` | `AA0002AB` | `E320F000` | `IKeyInput` bounds-check nop |
| `0x37bc30` | `AA0000CC` | `EAFFFFF8` | `FixedAddressArray::add` throw skip |
| `0x37bc38` | `DA0000CA` | `EAFFFFF6` | `FixedAddressArray::add` throw skip |
| `0x37bf34` | `DA00000B` | `EA000052` | `FixedAddressArray` bounds no-throw path |
| `0x37bf68` | `E3A00004` | `EAF47DC2` | return no-free-slot via cave |
| `0x37c048` | `AA00000D` | `E320F000` | key-target array bound nop |
| `0x37c050` | `DA00000B` | `E320F000` | key-target array bound nop |
| `0x37c084` | `E3A00004` | `EAF47D7B` | return no-free-slot via cave |
| `0x37c364` | `0AFFFF46` | `E320F000` | key-target removal guard nop |
| `0x37c710` | `E58450A4` | `E58480A4` | `KeyManager` pending-bitmask init |

## 5. Power-manager NULL-this guards

Prime GO has no Pioneer PM MCU; callbacks get called with `this == NULL`:

| VA | stock | patched | purpose |
|---|---|---|---|
| `0x121d9c` | `E92D41F0` | `E3A00000` | PM helper: `r0 = 0` |
| `0x121da0` | `EB01955A` | `E12FFF1E` | PM helper: `bx lr` |
| `0x12203c` | `E92D4038` | `E3A00000` | PM helper: `r0 = 0` |
| `0x122040` | `EB0194B2` | `E12FFF1E` | PM helper: `bx lr` |
| `0x122078` | `E92D45F0` | `E3A00000` | PM helper: `r0 = 0` |
| `0x12207c` | `E24DD00C` | `E12FFF1E` | PM helper: `bx lr` |
| `0x2c6bf0` | `E92D4038` | `E12FFF1E` | `notifyPermissionChanged` `bx lr` on NULL |
| `0x2c7004` | `E92D4070` | `E12FFF1E` | `notifyPreparedToStandby` `bx lr` on NULL |
| `0x32e728` | `E92D45F8` | `E12FFF1E` | USB/power notification helper `bx lr` |
| `0x3871d0` | `E1A00006` | `E3A00000` | notification helper: `r0 = 0` |

## 6. Display waveform gate

Middle scrolling waveform enabled unconditionally (stock gates it on a panel
caution id that never arrives):

| VA | stock | patched | purpose |
|---|---|---|---|
| `0x24fc88` | `1A000004` | `E1A07004` | waveform gate (1/2) |
| `0x24fc8c` | `E5943070` | `EA00007E` | waveform gate -> always render |

## 7. Touch fixes

| VA | stock | patched | purpose |
|---|---|---|---|
| `0x2dc228` | `E1A07000` | `E3A07000` | `solveCoordToKey` ignores caution id |
| `0x2dc46c` | `0A000008` | `EA000008` | `touchOn` bypasses caution check |
| `0x363774` | `E5943030` | `EA000028` | playlist drag -> always scroll |
| `0x363794` | `E5845030` | `E320F000` | drag-scroll counter nop |

## 8. Audio device scanning

Force the RX3 device list on non-i.MX6 CPUs:

| VA | stock | patched | purpose |
|---|---|---|---|
| `0x3c665c` | `1A000054` | `EA000054` | `ALSAAudioIODeviceType::scanForDevices` force list |

## 9. udev FIFO paths (`/proc/udev_*` -> `/tmp/udev_*`)

Move udev FIFOs to the writable `/tmp` tmpfs:

| VA | stock | patched | purpose |
|---|---|---|---|
| `0x4dede4`..`0x4dedf0` | `"/proc/udev_usb1"` | `"/tmp/udev_usb1"` | USB 1 FIFO path |
| `0x4dedf4`..`0x4dee00` | `"/proc/udev_usb2"` | `"/tmp/udev_usb2"` | USB 2 FIFO path |
| `0x4e0e54`..`0x4e0e64` | `"/proc/udev_usbctn1"` | `"/tmp/udev_usbctn1"` | USB container 1 FIFO |
| `0x4e0e68`..`0x4e0e78` | `"/proc/udev_usbctn2"` | `"/tmp/udev_usbctn2"` | USB container 2 FIFO |
