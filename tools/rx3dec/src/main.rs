//! XDJ-RX3 .UPD decryptor: AES-256-CBC per 512-byte sector,
//! IV = LE32(sector index) + 12 zero bytes (cryptoloop / `losetup -e aes`),
//! key = first 31 bytes of the first line of the key file + one NUL byte
//! (matching the device's xgetpass + xstrncpy behaviour).
//!
//! The file layout is: [CBC-encrypted ISO 9660 image, 512-aligned]
//!                      [16-byte plaintext trailer: "MODELVER\0" + CRC32]
//!
//! usage: rx3dec <input.UPD> <keyfile> <output.img>
use aes::Aes256;
use cbc::cipher::{BlockDecryptMut, KeyIvInit};
use std::path::Path;

type Aes256CbcDec = cbc::Decryptor<Aes256>;

const SECTOR: usize = 512;
const TRAILER: usize = 16;

fn main() {
    let a: Vec<String> = std::env::args().collect();
    if a.len() != 4 {
        eprintln!("usage: rx3dec <input.UPD> <keyfile> <output.img>");
        std::process::exit(2);
    }
    let input = std::fs::read(&a[1]).unwrap_or_else(|e| {
        eprintln!("read {}: {e}", a[1]);
        std::process::exit(1);
    });
    let keyfile = std::fs::read(&a[2]).unwrap_or_else(|e| {
        eprintln!("read {}: {e}", a[2]);
        std::process::exit(1);
    });
    let out_path = Path::new(&a[3]);

    // Effective key: first line, first 31 bytes, NUL-padded to 32.
    let first_line = keyfile
        .split(|&b| b == b'\n')
        .next()
        .unwrap_or(&keyfile[..]);
    let mut key = [0u8; 32];
    let n = first_line.len().min(31);
    key[..n].copy_from_slice(&first_line[..n]);
    println!(
        "[+] key = {} ({} bytes -> 32)", 
        key[..n].escape_ascii(), n
    );

    if input.len() < TRAILER {
        eprintln!("input too small");
        std::process::exit(1);
    }
    let body = &input[..input.len() - TRAILER];
    if body.len() % SECTOR != 0 {
        eprintln!(
            "body size {} is not 512-aligned (input={}, trailer={}); not an RX3 .UPD?",
            body.len(), input.len(), TRAILER
        );
        std::process::exit(1);
    }
    println!(
        "[+] body: {} bytes ({} sectors), trailer: {:02x?}",
        body.len(),
        body.len() / SECTOR,
        &input[input.len() - TRAILER..]
    );

    let mut out = Vec::with_capacity(body.len());
    for (sector, chunk) in body.chunks(SECTOR).enumerate() {
        let mut iv = [0u8; 16];
        iv[..4].copy_from_slice(&(sector as u32).to_le_bytes());
        let cipher = Aes256CbcDec::new_from_slices(&key, &iv).expect("key/iv size");
        let mut block = chunk.to_vec();
        cipher
            .decrypt_padded_mut::<cbc::cipher::block_padding::NoPadding>(&mut block)
            .expect("sector is 512 bytes");
        out.extend_from_slice(&block);
    }

    // sanity: ISO 9660 PVD at sector 64
    if out.len() >= 65 * SECTOR && &out[64 * SECTOR + 1..64 * SECTOR + 6] == b"CD001" {
        println!("[+] OK: ISO 9660 signature CD001 found at sector 64");
    } else {
        eprintln!("[-] WARNING: CD001 not found at sector 64 - key or layout wrong?");
    }

    std::fs::write(out_path, &out).unwrap();
    println!("[+] wrote {} ({} bytes)", out_path.display(), out.len());
}
