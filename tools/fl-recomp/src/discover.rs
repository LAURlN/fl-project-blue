//! Deterministic function-entry discovery and CFG recovery.
//!
//! Entry sources, in priority order:
//!   1. the image's ARM entry point;
//!   2. the revision's explicit entry list (Thumb bit marks T16 entries);
//!   3. the revision's scheduler poll list;
//!   4. every direct BL/BLX immediate target found by a byte scan;
//!   5. aligned runs of code pointers in .rodata/.data;
//!   6. ARM/T16 prologue scanning in otherwise uncovered text.
//!
//! Each function's internal CFG is recovered recursively. Direct calls start a
//! new function; direct branches stay in the current function unless their
//! target is already a known entry, in which case they are treated as tail
//! calls. This is deterministic and does not depend on any third-party
//! recompiler's heuristics.

use std::collections::{BTreeMap, BTreeSet, VecDeque};
use std::fs;
use std::io;
use std::path::Path;

use crate::arm;
use crate::image::Image;
use crate::insn::*;
use crate::thumb;

#[allow(dead_code)]
#[derive(Clone, Debug)]
pub struct SwitchTable {
    pub site: u32,
    pub mode: Mode,
    pub register: u8,
    pub cases: Vec<(u32, u32)>,
    pub default: u32,
    pub table: Vec<u32>,
    pub table_addr: u32,
}

#[derive(Clone, Debug)]
pub struct Function {
    pub entry: u32,
    pub mode: Mode,
    pub insns: BTreeMap<u32, Insn>,
    pub literals: BTreeSet<u32>,
    pub switches: Vec<SwitchTable>,
}

#[derive(Clone, Debug)]
pub struct Rejected {
    pub addr: u32,
    pub mode: Mode,
    pub reason: String,
}

#[derive(Clone, Debug)]
pub struct Analysis {
    pub functions: BTreeMap<u32, Function>,
    pub entries: BTreeSet<(u32, Mode)>,
    pub rejected: Vec<Rejected>,
    pub unhandled: Vec<(u32, Mode, u32)>,
    pub indirect_sites: Vec<(u32, Mode)>,
    pub text_size: u32,
    pub code_bytes: u64,
    pub instruction_count: u64,
    pub literal_bytes: u64,
    pub switch_bytes: u64,
    pub gaps: Vec<(u32, u32)>,
    /// Functions with bytes outside ARMv6K/Thumb-1 (typically data embedded in
    /// the text segment). They are emitted as aborting stubs, never as wrong C.
    pub stubs: Vec<(u32, Mode)>,
}

#[derive(Clone, Debug, Default)]
pub struct EntryHints {
    pub entries: Vec<(u32, Mode)>,
    pub polls: Vec<(u32, Mode)>,
}

pub fn load_hints(entries: Option<&Path>, polls: Option<&Path>) -> io::Result<EntryHints> {
    let mut hints = EntryHints::default();
    if let Some(path) = entries {
        hints.entries = parse_hints(path)?;
    }
    if let Some(path) = polls {
        hints.polls = parse_hints(path)?;
    }
    Ok(hints)
}

fn parse_hints(path: &Path) -> io::Result<Vec<(u32, Mode)>> {
    let text = fs::read_to_string(path)?;
    let mut out = Vec::new();
    for line in text.lines() {
        let line = line.split('#').next().unwrap_or("").trim();
        if line.is_empty() {
            continue;
        }
        let token = line.split_whitespace().next().unwrap_or("");
        let value = u32::from_str_radix(token.trim_start_matches("0x"), 16).map_err(|_| {
            io::Error::new(io::ErrorKind::InvalidData, format!("bad address {token:?} in {}", path.display()))
        })?;
        let mode = if value & 1 != 0 { Mode::Thumb } else { Mode::Arm };
        out.push((value & !1, mode));
    }
    Ok(out)
}

pub fn analyze(image: &Image, hints: &EntryHints) -> Analysis {
    let mut seeds: BTreeSet<(u32, Mode)> = BTreeSet::new();
    seeds.insert((image.entry, Mode::Arm));
    for &(addr, mode) in hints.entries.iter().chain(hints.polls.iter()) {
        if in_text(image, addr, mode) {
            seeds.insert((addr, mode));
        }
    }
    scan_direct_calls(image, &mut seeds);
    scan_pointer_runs(image, &mut seeds);

    // Drop seeds that do not begin with an instruction this translator can
    // execute. The byte scanner sees ARM branch encodings inside data and
    // arm/Thumb words at the wrong alignment; those would otherwise become
    // bogus functions and unhandled-instruction reports.
    let mut rejected = Vec::new();
    let mut plausible = BTreeSet::new();
    for &(addr, mode) in &seeds {
        match decode_at(image, addr, mode) {
            Ok(insn) if !matches!(insn.op, Op::Unhandled { .. }) => {
                plausible.insert((addr, mode));
            }
            Ok(_) => rejected.push(Rejected {
                addr,
                mode,
                reason: "seed begins with an undecodable instruction".to_string(),
            }),
            Err(reason) => rejected.push(Rejected { addr, mode, reason }),
        }
    }
    seeds = plausible;

    let mut functions: BTreeMap<u32, Function> = BTreeMap::new();
    let mut covered = BTreeSet::new();
    let mut arm_queue: VecDeque<u32> = VecDeque::new();
    let mut thumb_queue: VecDeque<u32> = VecDeque::new();
    for &(addr, mode) in &seeds {
        match mode {
            Mode::Arm => arm_queue.push_back(addr),
            Mode::Thumb => thumb_queue.push_back(addr),
        }
    }
    // ARM code is discovered first so that a spurious Thumb pointer into an
    // ARM function cannot pre-empt the real arm extent. The two queues are
    // then drained with ARM priority, which keeps the result deterministic.
    loop {
        let (addr, mode) = if let Some(addr) = arm_queue.pop_front() {
            (addr, Mode::Arm)
        } else if let Some(addr) = thumb_queue.pop_front() {
            (addr, Mode::Thumb)
        } else {
            break;
        };
        if functions.contains_key(&addr) || covered.contains(&addr) {
            continue;
        }
        match discover_function(image, addr, mode, &seeds, &covered) {
            Ok(func) => {
                // Calls found inside the function are new entry candidates.
                for insn in func.insns.values() {
                    if let Op::B { target, link: true, exchange, .. } = insn.op {
                        let target_mode = if exchange {
                            Mode::Thumb
                        } else {
                            mode
                        };
                        if image.text_ranges().start <= target && target < image.text_ranges().end {
                            if seeds.insert((target, target_mode)) {
                                match target_mode {
                                    Mode::Arm => arm_queue.push_back(target),
                                    Mode::Thumb => thumb_queue.push_back(target),
                                }
                            }
                        }
                    }
                }
                mark_coverage(&func, &mut covered);
                functions.insert(addr, func);
            }
            Err(reason) => rejected.push(Rejected { addr, mode, reason }),
        }
    }

    // Prologue recovery in text not yet attributed to any function.
    let mut extra: Vec<(u32, Mode)> = Vec::new();
    let text = image.text_ranges();
    let mut addr = text.start;
    while addr + 4 <= text.end {
        if !covered.contains(&addr) {
            let word = image.read_u32(addr).unwrap_or(0);
            if arm_prologue(word) {
                extra.push((addr, Mode::Arm));
            }
        }
        addr += 4;
    }
    // Thumb functions are not always reached by a direct BL: many are only
    // installed in vtables or callback slots. Scan every halfword boundary for
    // the two unambiguous T16 prologues (push with LR, or a stack allocation
    // followed by a push). False entries inside data are dropped below when
    // their walk hits bytes that are not Thumb-1.
    let mut addr = text.start;
    while addr + 4 <= text.end {
        if addr & 1 == 0 && !covered.contains(&addr) {
            let hw = image.read_u16(addr).unwrap_or(0);
            if thumb_prologue(image, addr, hw) {
                extra.push((addr, Mode::Thumb));
            }
        }
        addr += 2;
    }
    // Sequential recovery: the instruction after a return is very often the
    // next function. Try those addresses (and the starts of leftover gaps) and
    // keep walks that are entirely decodable and return. Without this, a chain
    // of leaf functions that never push LR stays invisible.
    let mut sequential: BTreeSet<(u32, Mode)> = BTreeSet::new();
    for func in functions.values() {
        for insn in func.insns.values() {
            let next = insn.addr.wrapping_add(insn.size as u32);
            let terminates = match insn.op {
                Op::Bx { .. } => true,
                Op::Block(ref b) => b.load && (b.regs & (1 << PC)) != 0,
                Op::Mem(ref m) => m.kind.is_load() && m.rd == PC,
                Op::Dp { rd: PC, .. } => true,
                Op::B { target, link: false, .. } => !func.insns.contains_key(&target),
                _ => false,
            };
            if terminates && next < text.end && !covered.contains(&next) {
                sequential.insert((next, func.mode));
            }
        }
    }
    let mut gap_addr = text.start;
    while gap_addr < text.end {
        if !covered.contains(&gap_addr) {
            let aligned = (gap_addr + 3) & !3;
            if aligned < text.end && !covered.contains(&aligned) {
                sequential.insert((aligned, Mode::Arm));
            }
        }
        gap_addr += 4;
    }
    let mut queue: VecDeque<(u32, Mode)> = sequential.into_iter().collect();
    let mut seq_steps = 0usize;
    while let Some((addr, mode)) = queue.pop_front() {
        seq_steps += 1;
        if seq_steps > 5_000_000 {
            break;
        }
        if functions.contains_key(&addr) || covered.contains(&addr) {
            continue;
        }
        if !in_text(image, addr, mode) {
            continue;
        }
        let Ok(func) = discover_function(image, addr, mode, &seeds, &covered) else {
            continue;
        };
        if func.insns.is_empty()
            || func.insns.values().any(|i| matches!(i.op, Op::Unhandled { .. }))
            || !has_terminator(&func)
        {
            continue;
        }
        for insn in func.insns.values() {
            let next = insn.addr.wrapping_add(insn.size as u32);
            if next < text.end && !covered.contains(&next) {
                queue.push_back((next, mode));
            }
        }
        mark_coverage(&func, &mut covered);
        functions.insert(addr, func);
    }

    for &(addr, mode) in &extra {
        if functions.contains_key(&addr) || covered.contains(&addr) {
            continue;
        }
        let Ok(func) = discover_function(image, addr, mode, &seeds, &covered) else {
            continue;
        };
        if func.insns.is_empty() {
            continue;
        }
        // A prologue scan can land in a literal pool or compressed data. Only
        // keep walks that stay entirely within the ARMv6K / Thumb-1 instruction
        // set and that actually leave the function: a real entry never needs
        // bytes this translator cannot decode.
        if func.insns.values().any(|i| matches!(i.op, Op::Unhandled { .. })) {
            continue;
        }
        if !has_terminator(&func) {
            continue;
        }
        mark_coverage(&func, &mut covered);
        functions.insert(addr, func);
    }

    // A function that walked into a literal pool, a switch table or another
    // mode's bytes cannot be emitted safely. Keep a stub for its address so an
    // indirect call still reports a precise guest address instead of falling
    // into unrelated code.
    let mut stubs = Vec::new();
    let bad: Vec<u32> = functions
        .iter()
        .filter(|(_, f)| f.insns.values().any(|i| matches!(i.op, Op::Unhandled { .. })))
        .map(|(&addr, _)| addr)
        .collect();
    for addr in bad {
        if let Some(func) = functions.remove(&addr) {
            rejected.push(Rejected {
                addr,
                mode: func.mode,
                reason: "function contains data or non-Thumb-1 bytes".to_string(),
            });
            stubs.push((addr, func.mode));
        }
    }

    let mut unhandled = Vec::new();
    let mut indirect_sites = Vec::new();
    let mut literal_bytes = 0u64;
    let mut switch_bytes = 0u64;
    let mut instruction_count = 0u64;
    let mut covered = BTreeSet::new();
    for func in functions.values() {
        for (&addr, insn) in &func.insns {
            instruction_count += 1;
            for i in 0..insn.size as u32 {
                covered.insert(addr + i);
            }
            if let Op::Unhandled { .. } = insn.op {
                unhandled.push((addr, func.mode, insn.raw));
            }
            match insn.op {
                Op::Bx { link: false, .. } => indirect_sites.push((addr, func.mode)),
                Op::Dp { rd: PC, .. } => indirect_sites.push((addr, func.mode)),
                Op::Mem(ref m) if m.kind.is_load() && m.rd == PC => {
                    indirect_sites.push((addr, func.mode))
                }
                Op::Block(ref b) if b.load && (b.regs & (1 << PC)) != 0 && b.rn != SP => {
                    indirect_sites.push((addr, func.mode))
                }
                _ => {}
            }
        }
        literal_bytes += func.literals.len() as u64 * 4;
        covered.extend(func.literals.iter().copied());
        for sw in &func.switches {
            switch_bytes += sw.table.len() as u64 * 4;
            for i in 0..(sw.table.len() as u32) * 4 {
                covered.insert(sw.table_addr + i);
            }
        }
    }

    let mut gaps = Vec::new();
    let mut gap_start: Option<u32> = None;
    let mut addr = text.start;
    while addr < text.end {
        let is_covered = covered.contains(&addr);
        match (is_covered, gap_start) {
            (false, None) => gap_start = Some(addr),
            (true, Some(start)) => {
                gaps.push((start, addr - start));
                gap_start = None;
            }
            _ => {}
        }
        addr += 1;
    }
    if let Some(start) = gap_start {
        gaps.push((start, text.end - start));
    }
    gaps.retain(|&(_, len)| len > 0);

    Analysis {
        functions,
        entries: seeds,
        rejected,
        unhandled,
        indirect_sites,
        text_size: text.end - text.start,
        code_bytes: covered.len() as u64,
        instruction_count,
        literal_bytes,
        switch_bytes,
        gaps,
        stubs,
    }
}

fn scan_direct_calls(image: &Image, seeds: &mut BTreeSet<(u32, Mode)>) {
    let range = image.text_ranges();
    let mut addr = range.start;
    while addr + 4 <= range.end {
        let word = image.read_u32(addr).unwrap_or(0);
        let cond = (word >> 28) & 0xF;
        if cond != 0xF && (word >> 25) & 7 == 0b101 && (word >> 24) & 1 == 1 {
            let off = (((word & 0xFF_FFFF) << 8) as i32 >> 8) << 2;
            let target = (addr as i32).wrapping_add(8).wrapping_add(off) as u32;
            seed(seeds, image, target, Mode::Arm);
        }
        if (word & 0xFE00_0000) == 0xFA00_0000 {
            let h = (word >> 24) & 1;
            let off = ((((word & 0xFF_FFFF) << 8) as i32 >> 8) << 2).wrapping_add((h << 1) as i32);
            let target = (addr as i32).wrapping_add(8).wrapping_add(off) as u32;
            seed(seeds, image, target & !1, Mode::Thumb);
        }
        addr += 4;
    }
    // Thumb BL/BLX targets are collected while walking already-discovered
    // Thumb functions (see `analyze`). Scanning every halfword would turn
    // ARM instruction words into bogus Thumb call targets.
}

fn in_text(image: &Image, addr: u32, mode: Mode) -> bool {
    let range = image.text_ranges();
    if addr < range.start || addr >= range.end {
        return false;
    }
    match mode {
        Mode::Arm => addr & 3 == 0,
        Mode::Thumb => addr & 1 == 0,
    }
}

fn seed(seeds: &mut BTreeSet<(u32, Mode)>, image: &Image, addr: u32, mode: Mode) {
    if in_text(image, addr, mode) {
        seeds.insert((addr, mode));
    }
}

fn scan_pointer_runs(image: &Image, seeds: &mut BTreeSet<(u32, Mode)>) {
    let range = image.text_ranges();
    for seg in image.data_ranges() {
        let mut addr = seg.start;
        let mut run: Vec<u32> = Vec::new();
        while addr + 4 <= seg.end {
            let value = image.read_u32(addr).unwrap_or(0);
            let base = value & !1;
            if base >= range.start && base < range.end {
                run.push(value);
            } else {
                if run.len() >= 3 {
                    for v in &run {
                        let mode = if v & 1 != 0 { Mode::Thumb } else { Mode::Arm };
                        seed(seeds, image, v & !1, mode);
                    }
                }
                run.clear();
            }
            addr += 4;
        }
        if run.len() >= 3 {
            for v in &run {
                let mode = if v & 1 != 0 { Mode::Thumb } else { Mode::Arm };
                seed(seeds, image, v & !1, mode);
            }
        }
    }
}

fn arm_prologue(word: u32) -> bool {
    // STMDB sp!, {...} (the AAPCS push), with any condition code and any
    // register list. Leaf functions that save no LR are still functions.
    if ((word >> 16) & 0x0FFF) == 0x092D {
        return true;
    }
    // SUB sp, sp, #imm: the large-frame form used when the saved range is not
    // encodable in one STMDB.
    (word & 0x0FFF_0000) == 0x024D_0000 && ((word >> 12) & 0xF) == SP as u32
}

fn thumb_prologue(image: &Image, addr: u32, hw: u16) -> bool {
    // PUSH {reglist}, with or without LR.
    if (hw & 0xFE00) == 0xB400 {
        return true;
    }
    // SUB SP, #imm7*4 followed by a push (or by the frame setup itself).
    if (hw & 0xFF80) == 0xB080 {
        let next = image.read_u16(addr.wrapping_add(2)).unwrap_or(0);
        return (next & 0xFE00) == 0xB400 || (next & 0xFF80) == 0xB080;
    }
    false
}

/// A recovered instruction stream only counts as a function if control
/// actually leaves it: a return, an indirect branch, or a tail call. This
/// rejects walks that start inside literal pools and simply run to the end of
/// the text segment.
fn has_terminator(func: &Function) -> bool {
    func.insns.values().any(|i| match i.op {
        Op::Bx { link: false, .. } => true,
        Op::Block(ref b) => b.load && (b.regs & (1 << PC)) != 0,
        Op::Mem(ref m) => m.kind.is_load() && m.rd == PC,
        Op::Dp { rd: PC, .. } => true,
        Op::B { target, link: false, .. } => !func.insns.contains_key(&target),
        _ => false,
    })
}

fn decode_at(image: &Image, addr: u32, mode: Mode) -> Result<Insn, String> {
    let range = image.text_ranges();
    match mode {
        Mode::Arm => {
            if addr < range.start || addr + 4 > range.end || addr & 3 != 0 {
                return Err(format!("ARM address {addr:08x} outside aligned text"));
            }
            let word = image.read_u32(addr).ok_or_else(|| format!("unreadable word at {addr:08x}"))?;
            Ok(arm::decode(addr, word))
        }
        Mode::Thumb => {
            if addr < range.start || addr + 2 > range.end || addr & 1 != 0 {
                return Err(format!("Thumb address {addr:08x} outside aligned text"));
            }
            let hw = image.read_u16(addr).ok_or_else(|| format!("unreadable halfword at {addr:08x}"))?;
            if thumb::is_32bit_prefix(hw) {
                if addr + 4 > range.end {
                    return Err(format!("truncated 32-bit Thumb instruction at {addr:08x}"));
                }
                let second = image.read_u16(addr + 2).ok_or_else(|| "unreadable second halfword".to_string())?;
                Ok(thumb::decode32(addr, hw, second))
            } else {
                Ok(thumb::decode(addr, hw))
            }
        }
    }
}

fn mark_coverage(func: &Function, covered: &mut BTreeSet<u32>) {
    for (&addr, insn) in &func.insns {
        for i in 0..insn.size as u32 {
            covered.insert(addr + i);
        }
    }
    covered.extend(func.literals.iter().copied());
    for sw in &func.switches {
        for i in 0..(sw.table.len() as u32) * 4 {
            covered.insert(sw.table_addr + i);
        }
    }
}

fn discover_function(
    image: &Image,
    entry: u32,
    mode: Mode,
    entries: &BTreeSet<(u32, Mode)>,
    covered: &BTreeSet<u32>,
) -> Result<Function, String> {
    let range = image.text_ranges();
    let mut insns = BTreeMap::new();
    let mut literals = BTreeSet::new();
    let mut switches = Vec::new();
    let mut visited = BTreeSet::new();
    let mut work: Vec<u32> = vec![entry];
    let mut steps = 0usize;
    while let Some(start) = work.pop() {
        if !visited.insert(start) {
            continue;
        }
        // A branch target belonging to another recovered function is a tail
        // call. Linear fallthrough is allowed to pass such an address: knowing
        // that a *call* starts there does not make the preceding bytes a new
        // function.
        if start != entry && (entries.contains(&(start, mode)) || covered.contains(&start)) {
            continue;
        }
        let mut addr = start;
        loop {
            if addr < range.start || addr >= range.end {
                break;
            }
            if addr != entry && covered.contains(&addr) {
                break;
            }
            let insn = match decode_at(image, addr, mode) {
                Ok(i) => i,
                Err(e) => return Err(e),
            };
            let size = insn.size as u32;
            steps += 1;
            if steps > 250_000 {
                return Err(format!("function at {entry:08x} exceeded instruction budget"));
            }
            if insns.insert(addr, insn).is_some() {
                break;
            }
            // Literal pool / data referenced by this instruction.
            collect_literals(image, &insn, mode, &mut literals);
            let mut terminate = false;
            match insn.op {
                Op::B { target, link, exchange, .. } => {
                    if link {
                        if target < range.start || target >= range.end {
                            return Err(format!("call from {addr:08x} to outside text {target:08x}"));
                        }
                    } else {
                        if target < range.start || target >= range.end {
                            return Err(format!("branch from {addr:08x} to outside text {target:08x}"));
                        }
                        if exchange && mode != Mode::Thumb {
                            return Err(format!("mode-changing branch from {addr:08x}"));
                        }
                        let conditional = insn.cond != Cond::Al;
                        let target_mode = if exchange { Mode::Thumb } else { mode };
                        let external = target != entry && entries.contains(&(target, target_mode));
                        if conditional {
                            // A conditional branch always falls through, so keep
                            // decoding the linear extent even when the taken edge
                            // leaves this function. The target is queued only for
                            // internal edges; `entries`/`covered` prune the rest.
                            if !external {
                                work.push(target);
                            }
                        } else if external {
                            terminate = true;
                        } else {
                            work.push(target);
                            terminate = true;
                        }
                    }
                }
                Op::Bx { link, rm, .. } => {
                    if rm == LR {
                        terminate = true;
                    } else if link {
                        // BLX register: execution continues after the call.
                    } else {
                        terminate = true;
                    }
                }
                Op::Block(ref b) if b.load && (b.regs & (1 << PC)) != 0 => {
                    terminate = true;
                }
                Op::Mem(ref m) if m.kind.is_load() && m.rd == PC => {
                    if let Some(case) = try_load_switch(image, &insn, mode, &mut work, &mut literals) {
                        switches.push(case);
                    }
                    terminate = true;
                }
                Op::Dp { rd: PC, .. } => {
                    if let Some(case) = try_switch(image, &insn, mode, &mut work, &mut literals) {
                        switches.push(case);
                    }
                    terminate = true;
                }
                Op::Unhandled { what } => {
                    if what.starts_with("Thumb-2") {
                        terminate = true;
                    }
                }
                _ => {}
            }
            if terminate {
                break;
            }
            if let Op::B { link: true, .. } = insn.op {
                // A call with a link to a discovered function returns here.
            }
            addr = addr.wrapping_add(size);
        }
    }
    if insns.is_empty() {
        return Err(format!("no instructions decoded at {entry:08x}"));
    }
    Ok(Function { entry, mode, insns, literals, switches })
}

fn collect_literals(image: &Image, insn: &Insn, mode: Mode, out: &mut BTreeSet<u32>) {
    let pc_base = match mode {
        Mode::Arm => insn.addr.wrapping_add(8),
        Mode::Thumb => insn.addr.wrapping_add(4) & !3,
    };
    if let Op::Mem(ref m) = insn.op {
        if m.rn == PC {
            if let MemOffset::Imm(off) = m.offset {
                let addr = if m.add { pc_base.wrapping_add(off) } else { pc_base.wrapping_sub(off) };
                let bytes = if m.kind.is_double() { 8 } else { 4 };
                if image.contains(addr) {
                    for i in 0..(bytes / 4) {
                        out.insert(addr + i * 4);
                    }
                }
            }
        }
    }
    if let Op::Vfp(VfpOp::Mem { rn: PC, offset, add, size, .. }) = insn.op {
        let addr = if add { pc_base.wrapping_add(offset) } else { pc_base.wrapping_sub(offset) };
        let bytes = if size == VfpSize::Double { 8 } else { 4 };
        if image.contains(addr) {
            for i in 0..(bytes / 4) {
                out.insert(addr + i * 4);
            }
        }
    }
}

fn try_switch(
    image: &Image,
    insn: &Insn,
    mode: Mode,
    work: &mut Vec<u32>,
    literals: &mut BTreeSet<u32>,
) -> Option<SwitchTable> {
    if mode != Mode::Arm {
        return None;
    }
    // `add pc, pc, rm, lsl #2` with a preceding `cmp rm, #N`.
    let Op::Dp { op: DpOp::Add, rd: PC, rn: PC, op2: Operand2::Reg { rm, shift }, .. } = insn.op
    else {
        return None;
    };
    if !(shift.kind == ShiftKind::Lsl && shift.amount == ShiftAmount::Imm(2)) {
        return None;
    }
    let bound = find_bound(image, insn.addr, rm);
    let table_addr = insn.addr.wrapping_add(8);
    let limit = bound.map(|b| b + 1).unwrap_or(64);
    let mut cases = Vec::new();
    for i in 0..limit {
        let slot = table_addr.wrapping_add(i * 4);
        if !image.contains(slot) {
            break;
        }
        // The `add` lands directly on the table slot, so every slot is itself
        // a case entry (normally a B instruction, but any instruction is legal).
        let word = image.read_u32(slot)?;
        if bound.is_none() && (word >> 25) & 7 != 0b101 {
            // Without a preceding `cmp` we have no reliable extent. Only trust
            // a contiguous run of B instructions, which is the canonical form.
            break;
        }
        cases.push((i, slot));
        work.push(slot);
        literals.insert(slot);
    }
    if cases.is_empty() {
        return None;
    }
    Some(SwitchTable {
        site: insn.addr,
        mode,
        register: rm,
        cases,
        default: insn.addr.wrapping_add(4),
        table: Vec::new(),
        table_addr,
    })
}

fn try_load_switch(
    image: &Image,
    insn: &Insn,
    mode: Mode,
    work: &mut Vec<u32>,
    literals: &mut BTreeSet<u32>,
) -> Option<SwitchTable> {
    if mode != Mode::Arm {
        return None;
    }
    let Op::Mem(ref m) = insn.op else { return None };
    if m.kind != MemKind::Ldr || m.rd != PC || m.rn != PC || !m.pre_index {
        return None;
    }
    let MemOffset::Reg { rm, shift } = m.offset else { return None };
    if !(shift.kind == ShiftKind::Lsl && shift.amount == ShiftAmount::Imm(2)) {
        return None;
    }
    let bound = find_bound(image, insn.addr, rm);
    let table_addr = insn.addr.wrapping_add(8);
    let limit = bound.map(|b| b + 1).unwrap_or(64);
    let mut cases = Vec::new();
    let mut table = Vec::new();
    for i in 0..limit {
        let slot = table_addr.wrapping_add(i * 4);
        let value = image.read_u32(slot)?;
        let target = value & !1;
        let in_text = target >= image.text_ranges().start && target < image.text_ranges().end;
        if !in_text && bound.is_none() {
            break;
        }
        table.push(value);
        literals.insert(slot);
        if in_text {
            cases.push((i, target));
            work.push(target);
        }
    }
    if cases.is_empty() {
        return None;
    }
    Some(SwitchTable {
        site: insn.addr,
        mode,
        register: rm,
        cases,
        default: insn.addr.wrapping_add(4),
        table,
        table_addr,
    })
}

fn find_bound(image: &Image, site: u32, rm: u8) -> Option<u32> {
    let mut addr = site;
    for _ in 0..8 {
        if addr < image.text_ranges().start + 4 {
            break;
        }
        addr -= 4;
        let word = image.read_u32(addr)?;
        let insn = arm::decode(addr, word);
        if let Op::Dp { op: DpOp::Cmp, rn, op2: Operand2::Imm(imm), .. } = insn.op {
            if rn == rm {
                return Some(imm);
            }
        }
    }
    None
}
