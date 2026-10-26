//! Loader for the already-extracted Fantasy Life EU image.
//!
//! `exheader.bin` supplies the SCI segment table; `code.bin` is the
//! decompressed `.code` file from ExeFS, with the three segments page-aligned
//! exactly as the loader maps them.

use std::fs;
use std::io;
use std::path::{Path, PathBuf};

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Segment {
    pub addr: u32,
    pub size: u32,
    pub pages: u32,
    pub file_offset: u32,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct AddressRange {
    pub start: u32,
    pub end: u32,
}

#[allow(dead_code)]
#[derive(Clone, Debug)]
pub struct Image {
    pub code: Vec<u8>,
    pub text: Segment,
    pub rodata: Segment,
    pub data: Segment,
    pub bss_size: u32,
    pub stack_size: u32,
    pub entry: u32,
    pub exheader: Vec<u8>,
}

fn u32_at(bytes: &[u8], offset: usize) -> io::Result<u32> {
    if offset + 4 > bytes.len() {
        return Err(io::Error::new(io::ErrorKind::UnexpectedEof, "u32 outside input"));
    }
    Ok(u32::from_le_bytes(bytes[offset..offset + 4].try_into().unwrap()))
}

#[allow(dead_code)]
impl Image {
    pub fn load(dir: &Path) -> io::Result<Image> {
        let exheader_path = find_file(dir, "exheader.bin")?;
        let code_path = find_file(dir, "exefs/code.bin")?;
        let exheader = fs::read(&exheader_path)?;
        let code = fs::read(&code_path)?;
        if exheader.len() < 0x400 {
            return Err(io::Error::new(io::ErrorKind::InvalidData, "exheader shorter than 0x400"));
        }
        let mut segments = Vec::new();
        for pos in [0x10usize, 0x20, 0x30] {
            let addr = u32_at(&exheader, pos)?;
            let pages = u32_at(&exheader, pos + 4)?;
            let size = u32_at(&exheader, pos + 8)?;
            if size > pages.saturating_mul(0x1000) {
                return Err(io::Error::new(io::ErrorKind::InvalidData, "segment exceeds page allocation"));
            }
            segments.push(Segment { addr, size, pages, file_offset: 0 });
        }
        let mut file_offset = 0;
        for seg in &mut segments {
            seg.file_offset = file_offset;
            file_offset = file_offset.saturating_add(seg.pages.saturating_mul(0x1000));
        }
        if (file_offset as usize) > code.len() {
            return Err(io::Error::new(
                io::ErrorKind::InvalidData,
                format!("code.bin is {} bytes but segments require {}", code.len(), file_offset),
            ));
        }
        Ok(Image {
            code,
            text: segments[0],
            rodata: segments[1],
            data: segments[2],
            bss_size: u32_at(&exheader, 0x3C)?,
            stack_size: u32_at(&exheader, 0x1C)?,
            entry: segments[0].addr,
            exheader,
        })
    }

    pub fn text_start(&self) -> u32 {
        self.text.addr
    }

    pub fn text_end(&self) -> u32 {
        self.text.addr + self.text.size
    }

    pub fn text_slice(&self) -> &[u8] {
        let start = self.text.file_offset as usize;
        &self.code[start..start + self.text.size as usize]
    }

    pub fn contains(&self, addr: u32) -> bool {
        self.segment_for(addr).is_some()
    }

    pub fn segment_for(&self, addr: u32) -> Option<&Segment> {
        for seg in [&self.text, &self.rodata, &self.data] {
            if addr >= seg.addr && addr < seg.addr.saturating_add(seg.size) {
                return Some(seg);
            }
        }
        None
    }

    pub fn file_offset(&self, addr: u32) -> Option<usize> {
        let seg = self.segment_for(addr)?;
        Some(seg.file_offset as usize + (addr - seg.addr) as usize)
    }

    pub fn read_u8(&self, addr: u32) -> Option<u8> {
        self.file_offset(addr).map(|off| self.code[off])
    }

    pub fn read_u16(&self, addr: u32) -> Option<u16> {
        let off = self.file_offset(addr)?;
        if off + 2 > self.code.len() {
            return None;
        }
        Some(u16::from_le_bytes(self.code[off..off + 2].try_into().unwrap()))
    }

    pub fn read_u32(&self, addr: u32) -> Option<u32> {
        let off = self.file_offset(addr)?;
        if off + 4 > self.code.len() {
            return None;
        }
        Some(u32::from_le_bytes(self.code[off..off + 4].try_into().unwrap()))
    }

    pub fn read_insn(&self, addr: u32) -> Option<u32> {
        if addr < self.text.addr || addr + 4 > self.text.addr + self.text.size {
            return None;
        }
        self.read_u32(addr)
    }

    pub fn text_ranges(&self) -> AddressRange {
        AddressRange { start: self.text.addr, end: self.text.addr + self.text.size }
    }

    /// All mapped, non-text ranges that can legitimately contain pointers to
    /// code (rodata and initialised data).
    pub fn data_ranges(&self) -> [AddressRange; 2] {
        [
            AddressRange { start: self.rodata.addr, end: self.rodata.addr + self.rodata.size },
            AddressRange { start: self.data.addr, end: self.data.addr + self.data.size },
        ]
    }
}

fn find_file(dir: &Path, rel: &str) -> io::Result<PathBuf> {
    let direct = dir.join(rel);
    if direct.is_file() {
        return Ok(direct);
    }
    // Also accept being pointed at the ExeFS directory itself.
    let leaf = Path::new(rel).file_name().unwrap();
    let candidate = dir.join(leaf);
    if candidate.is_file() {
        return Ok(candidate);
    }
    Err(io::Error::new(
        io::ErrorKind::NotFound,
        format!("{} not found under {}", rel, dir.display()),
    ))
}
