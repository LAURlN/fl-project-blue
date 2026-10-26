# Phase 0: Fantasy Life DLC CIA inspection

## Result

This 92,480-byte CIA does **not** contain the actual Origin Island DLC data. It contains two very small NCCH-form contents totaling 76 KiB: a 56 KiB content at TMD index 0 and a 20 KiB optional content at index 1. Their SHA-256 digests match the TMD. The CIA index bitmap enables both indexes, so both are physically present; this is not an empty or truncated content section. The size and structure indicate a minimal content/metadata package, not the expansion's game data. The file alone cannot establish whether the DLC is owned or installed on the console.

The `NCCH` marker occurs at offset `0x100` in both contents. The TMD encrypted flag is clear for both (`type=0x0000` and `0x4000`), consistent with unencrypted NCCH data. This does not rely on the magic alone: the flag is read from each TMD content record. Both stored content hashes match their records.

## Parsed fields

- CIA header size `0x2020`, type `0`, version `0`; no meta section.
- Certificate-chain section: 2,560 bytes. The chain begins with an RSA-4096/SHA-256 signature record; its certificate records were not fully decoded by the lightweight parser.
- Ticket: RSA-2048/SHA-256 signature type (`0x00010004`), issuer `Root-CA00000003-XS0000000c`, title ID `0004008C00113100`, console ID `00000000`, ticket ID `0000000000000000`, license type `0`. The issuer/signature fields are consistent with a retail/standard ticket format. The script does not cryptographically validate the signature, so this is a structural classification, not proof of legitimacy or ownership. The encrypted title key is not all `0xFF`.
- CIA content-index bitmap: indexes 0 and 1 enabled. (Bits are numbered MSB-first.)
- TMD: RSA-2048/SHA-256 signature type (`0x00010004`), issuer `Root-CA00000003-CP0000000b`, matching title ID, two content records:

| Content ID | Index | Type | Encrypted | Size | SHA-256 |
|---|---:|---:|---|---:|---|
| `00000000` | 0 | `0x0000` | no | 57,344 bytes | `c6a76ce01f5628b46abff16543c47faae0e14fbbcb488516b2e656a3500727af` |
| `00000001` | 1 | `0x4000` (optional) | no | 20,480 bytes | `114cb116bff2f106c6208e895f0467d75e7cb332f6096f83f450441af3fc1399` |

Both contents are present in the content section at `0x3940` and `0x11940`, respectively. Each has `NCCH` at content offset `0x100`; both calculated hashes equal their TMD hashes. Combined content size is exactly the CIA's declared 77,824 bytes.

## Reproduction

Run with the system Python and isolated mode; it uses only the standard library and reads the CIA without changing it:

```sh
python3 -I tools/inspect_cia.py "dumps/0004008C00113100 Fantasy Life™ (CTR-M-AFLP-00) (UNK) (v0.0.0).standard.cia"
```

Format interpretation follows the [3DBrew CIA format](https://www.3dbrew.org/wiki/CIA) and [TMD format](https://www.3dbrew.org/wiki/TMD): CIA sections are 64-byte aligned, TMD records provide content IDs/indexes/type flags/sizes/hashes, and type flag bit 0 denotes encryption.

## Correction: the DLC is an unlock flag, not missing data

A string scan of content index 1 (20 KiB) shows a RomFS with exactly one file:
`ID_ECFlag_0000.dat`. Content index 0 is the usual DLC content-info content.
So this CIA **is** the complete Origin Island DLC title. The "DLC" only sets an
unlock flag, and all Origin Island assets must already be in the base game's
`_file_archive.bin`. No further dump is needed.

Port implication: the runtime has to expose this AOC content (the add-on content
archive through `fs:USER`, plus `am:app`/`nim:aoc` queries) with
`ID_ECFlag_0000.dat` present, or Origin Island stays locked. A custom DLC could
use the same mechanism, e.g. another flag file plus new archive content.
