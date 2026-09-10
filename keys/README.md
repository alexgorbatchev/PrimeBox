# keys/ — supply your own key

PrimeBox **does not ship the firmware decryption key**. You must obtain it
yourself and place it here as:

```
keys/aes256.key
```

This path is in `.gitignore`, so your copy is never committed.

## Where the key comes from

Pioneer DJ / AlphaTheta publish the GPL/LGPL source used in their products on
their official open-source page:

* <https://www.pioneerdj.com/en/support/open-source-code-distribution/gnu-open-source-license/>

The XDJ-RX3 source archives (`pioneerdj_xdj_rx3.tar.bz2.*`, plus the kernel /
buildroot archives) are listed there. In the original research, a file named
`aes256.key` was found inside that published distribution — i.e. AlphaTheta
themselves released it while satisfying their GPL obligations. It is the same
key the device's own updater uses; the extracted rootfs contains
`/usr/local/pdj/aes256.key`.

To obtain it:

1. Download the XDJ-RX3 archives from the page above (they are large).
2. Unpack them and search for the key file:

   ```sh
   # after unpacking the .tar.xz / .tar.bz2 parts
   find . -name 'aes256.key'
   # or, if the file is buried in a squashfs/cramfs image, search by name
   grep -rl 'aes256' . 2>/dev/null
   ```

3. Copy it to `keys/aes256.key`.

If you already have a decrypted XDJ-RX3 rootfs from another source, the key is
also at `usr/local/pdj/aes256.key` inside it — but that obviously requires you
to have decrypted it already, so the GPL archive is the independent source.

## Format

The file is 90 bytes: two base64-looking lines. The RX3 loader does
`xgetpass()` + `xstrncpy(dst, src, 32)`, so the **effective key** is the first
**31 bytes of the first line** plus a terminating NUL (32 bytes total).
`tools/rx3dec` derives the 32-byte effective key automatically.

## Verifying

`tools/rx3dec` prints the derived key prefix and checks for the ISO 9660
`CD001` signature at sector 64. If the signature is missing, the key or the
file layout is wrong.

## Legal note

Firmware decryption may be restricted where you live. The key comes from
AlphaTheta's own public GPL distribution, but you are responsible for how you
use it. See [`../NOTICE.md`](../NOTICE.md).
