//! Thumb-1 (T16) decoder plus the 32-bit BL/BLX immediate pair.
//!
//! Thumb-2 encodings are rejected: the ARM11 target implements Thumb-1 only.
//! Words that would be Thumb-2 are reported as `Op::Unhandled` and consume a
//! halfword, so they cannot silently shift the instruction stream.

use crate::insn::*;

fn sx(value: u32, bits: u32) -> u32 {
    let shift = 32 - bits;
    ((value << shift) as i32 >> shift) as u32
}

fn bit(hw: u32, n: u32) -> bool {
    (hw >> n) & 1 != 0
}

fn reg(hw: u32, shift: u32) -> u8 {
    ((hw >> shift) & 7) as u8
}

pub fn is_32bit_prefix(hw: u16) -> bool {
    // BL/BLX are the only 32-bit encodings available in Thumb-1. A Thumb-1
    // instruction stream can only start such a pair with the 11110 prefix.
    (hw & 0xF800) == 0xF000
}

pub fn decode(addr: u32, hw: u16) -> Insn {
    let h = hw as u32;
    // Conditional branches are the only T16 instructions with a condition;
    // everything else in Thumb-1 is unconditional.
    let cond = if (h >> 11) & 0x1F == 0b11010 {
        let bits = (h >> 8) & 0xF;
        if bits < 0xE { Cond::from_bits(bits) } else { Cond::Al }
    } else {
        Cond::Al
    };
    Insn { addr, size: 2, cond, op: decode16(addr, h), raw: h }
}

pub fn decode32(addr: u32, first: u16, second: u16) -> Insn {
    let h1 = first as u32;
    let h2 = second as u32;
    let raw = (h1 << 16) | h2;
    let (op, cond) = decode_thumb32(addr, h1, h2);
    Insn { addr, size: 4, cond, op, raw }
}

fn decode16(addr: u32, h: u32) -> Op {
    match (h >> 11) & 0x1F {
        0b00000 | 0b00001 | 0b00010 => {
            // LSL/LSR/ASR (immediate)
            let kind = match (h >> 11) & 3 {
                0 => ShiftKind::Lsl,
                1 => ShiftKind::Lsr,
                _ => ShiftKind::Asr,
            };
            let mut amount = ((h >> 6) & 0x1F) as u8;
            if amount == 0 && kind != ShiftKind::Lsl {
                amount = 32;
            }
            Op::Dp {
                op: DpOp::Mov,
                rd: reg(h, 0),
                rn: 0,
                op2: Operand2::Reg { rm: reg(h, 3), shift: Shift { kind, amount: ShiftAmount::Imm(amount) } },
                set_flags: true,
            }
        }
        0b00011 => match (h >> 9) & 3 {
            0 => Op::Dp {
                op: DpOp::Add,
                rd: reg(h, 0),
                rn: reg(h, 3),
                op2: Operand2::Reg { rm: reg(h, 6), shift: Shift::NONE },
                set_flags: true,
            },
            1 => Op::Dp {
                op: DpOp::Sub,
                rd: reg(h, 0),
                rn: reg(h, 3),
                op2: Operand2::Reg { rm: reg(h, 6), shift: Shift::NONE },
                set_flags: true,
            },
            2 => Op::Dp {
                op: DpOp::Add,
                rd: reg(h, 0),
                rn: reg(h, 3),
                op2: Operand2::Imm(((h >> 6) & 7) as u32),
                set_flags: true,
            },
            _ => Op::Dp {
                op: DpOp::Sub,
                rd: reg(h, 0),
                rn: reg(h, 3),
                op2: Operand2::Imm(((h >> 6) & 7) as u32),
                set_flags: true,
            },
        },
        0b00100..=0b00111 => {
            let imm = (h & 0xFF) as u32;
            let rd = ((h >> 8) & 7) as u8;
            let op = match (h >> 11) & 3 {
                0 => DpOp::Mov,
                1 => DpOp::Cmp,
                2 => DpOp::Add,
                _ => DpOp::Sub,
            };
            Op::Dp {
                op,
                rd,
                // CMP reads its source from Rd too; MOV/MVN ignore Rn.
                rn: if op.is_unary() { 0 } else { rd },
                op2: Operand2::Imm(imm),
                set_flags: true,
            }
        }
        0b01000 => {
            if bit(h, 10) {
                return decode_special(h);
            }
            // Data-processing register
            let opcode = (h >> 6) & 0xF;
            let rd = reg(h, 0);
            let rm = reg(h, 3);
            let op2 = Operand2::Reg { rm, shift: Shift::NONE };
            match opcode {
                0x0 => Op::Dp { op: DpOp::And, rd, rn: rd, op2, set_flags: true },
                0x1 => Op::Dp { op: DpOp::Eor, rd, rn: rd, op2, set_flags: true },
                0x2..=0x4 => {
                    let kind = match opcode {
                        0x2 => ShiftKind::Lsl,
                        0x3 => ShiftKind::Lsr,
                        _ => ShiftKind::Asr,
                    };
                    Op::Dp {
                        op: DpOp::Mov,
                        rd,
                        rn: 0,
                        op2: Operand2::Reg {
                            rm: rd,
                            shift: Shift { kind, amount: ShiftAmount::Reg(rm) },
                        },
                        set_flags: true,
                    }
                }
                0x5 => Op::Dp { op: DpOp::Adc, rd, rn: rd, op2, set_flags: true },
                0x6 => Op::Dp { op: DpOp::Sbc, rd, rn: rd, op2, set_flags: true },
                0x7 => Op::Dp {
                    op: DpOp::Mov,
                    rd,
                    rn: 0,
                    op2: Operand2::Reg {
                        rm: rd,
                        shift: Shift { kind: ShiftKind::Ror, amount: ShiftAmount::Reg(rm) },
                    },
                    set_flags: true,
                },
                0x8 => Op::Dp { op: DpOp::Tst, rd, rn: rd, op2, set_flags: true },
                0x9 => Op::Dp {
                    // Thumb RSBS Rd, Rm, #0 computes 0 - Rm.
                    op: DpOp::Rsb,
                    rd,
                    rn: rm,
                    op2: Operand2::Imm(0),
                    set_flags: true,
                },
                0xA => Op::Dp { op: DpOp::Cmp, rd, rn: rd, op2, set_flags: true },
                0xB => Op::Dp { op: DpOp::Cmn, rd, rn: rd, op2, set_flags: true },
                0xC => Op::Dp { op: DpOp::Orr, rd, rn: rd, op2, set_flags: true },
                0xD => Op::Mul { rd, ra: 15, rm, rs: rd, accumulate: false, set_flags: true },
                0xE => Op::Dp { op: DpOp::Bic, rd, rn: rd, op2, set_flags: true },
                _ => Op::Dp { op: DpOp::Mvn, rd, rn: 0, op2, set_flags: true },
            }
        }
        0b01001 => {
            // LDR (literal)
            let rd = ((h >> 8) & 7) as u8;
            let imm = ((h & 0xFF) as u32) << 2;
            Op::Mem(Mem {
                kind: MemKind::Ldr,
                rd,
                rn: PC,
                offset: MemOffset::Imm(imm),
                add: true,
                pre_index: true,
                writeback: false,
            })
        }
        0b01010 | 0b01011 | 0b01100 | 0b01101 | 0b01110 | 0b01111 | 0b10000 | 0b10001
        | 0b10010 | 0b10011 => decode_load_store(h),
        0b10100 => {
            // ADR
            let rd = ((h >> 8) & 7) as u8;
            let imm = ((h & 0xFF) as u32) << 2;
            Op::Dp { op: DpOp::Add, rd, rn: PC, op2: Operand2::Imm(imm), set_flags: false }
        }
        0b10101 => {
            // ADD rd, SP, #imm
            let rd = ((h >> 8) & 7) as u8;
            let imm = ((h & 0xFF) as u32) << 2;
            Op::Dp { op: DpOp::Add, rd, rn: SP, op2: Operand2::Imm(imm), set_flags: false }
        }
        0b10110 | 0b10111 => decode_misc(h),
        0b11000 => {
            // STMIA rn!, {reglist}
            Op::Block(Block {
                load: false,
                rn: ((h >> 8) & 7) as u8,
                regs: (h & 0xFF) as u16,
                add: true,
                before: false,
                writeback: true,
                user: false,
            })
        }
        0b11001 => {
            // LDMIA rn!, {reglist}
            Op::Block(Block {
                load: true,
                rn: ((h >> 8) & 7) as u8,
                regs: (h & 0xFF) as u16,
                add: true,
                before: false,
                writeback: true,
                user: false,
            })
        }
        0b11010 | 0b11011 => {
            let cond_bits = (h >> 8) & 0xF;
            if cond_bits == 0xE {
                Op::Unhandled { what: "Thumb UDF encoding" }
            } else if cond_bits == 0xF {
                Op::Svc { imm: h & 0xFF }
            } else {
                let cond = Cond::from_bits(cond_bits);
                let off = sx((h & 0xFF) << 1, 9);
                let mut insn = Insn {
                    addr,
                    size: 2,
                    cond,
                    op: Op::B {
                        target: addr.wrapping_add(4).wrapping_add(off),
                        link: false,
                        exchange: false,
                    },
                    raw: h,
                };
                // `decode` normally fixes up direct-branch targets; keep the
                // field here since this function returns only the operation.
                if let Op::B { ref mut target, .. } = insn.op {
                    *target = addr.wrapping_add(4).wrapping_add(off);
                }
                insn.op
            }
        }
        0b11100 => {
            let off = sx((h & 0x7FF) << 1, 12);
            Op::B {
                target: addr.wrapping_add(4).wrapping_add(off),
                link: false,
                exchange: false,
            }
        }
        _ => Op::Unhandled { what: "Thumb-2 instruction" },
    }
}

fn decode_special(h: u32) -> Op {
    let h1 = ((h >> 3) & 7) as u8;
    let low = (h & 7) as u8;
    let h2 = ((h >> 6) & 1) as u8;
    let h1_bit = ((h >> 7) & 1) as u8;
    let rm = h1 | (h2 << 3);
    let rd = low | (h1_bit << 3);
    match (h >> 8) & 0xF {
        0x4 => Op::Dp {
            op: DpOp::Add,
            rd,
            rn: rd,
            op2: Operand2::Reg { rm, shift: Shift::NONE },
            set_flags: false,
        },
        0x5 => Op::Dp {
            op: DpOp::Cmp,
            rd,
            rn: rd,
            op2: Operand2::Reg { rm, shift: Shift::NONE },
            set_flags: true,
        },
        0x6 => Op::Dp {
            op: DpOp::Mov,
            rd,
            rn: 0,
            op2: Operand2::Reg { rm, shift: Shift::NONE },
            set_flags: false,
        },
        0x7 => Op::Bx { rm, link: bit(h, 7), j: false },
        _ => Op::Unhandled { what: "Thumb special data encoding" },
    }
}

fn decode_load_store(h: u32) -> Op {
    let top = (h >> 12) & 0xF;
    let rd = reg(h, 0);
    let rn = reg(h, 3);
    let rm = reg(h, 6);
    match top {
        0x5 => {
            let kind = match (h >> 9) & 7 {
                0 => MemKind::Str,
                1 => MemKind::StrH,
                2 => MemKind::StrB,
                3 => MemKind::LdrSb,
                4 => MemKind::Ldr,
                5 => MemKind::LdrH,
                6 => MemKind::LdrB,
                _ => MemKind::LdrSh,
            };
            Op::Mem(Mem {
                kind,
                rd,
                rn,
                offset: MemOffset::Reg { rm, shift: Shift::NONE },
                add: true,
                pre_index: true,
                writeback: false,
            })
        }
        0x6 | 0x7 => {
            let byte = top == 0x7;
            let load = bit(h, 11);
            let imm = ((h >> 6) & 0x1F) as u32;
            let scale = if byte { 1 } else { 4 };
            Op::Mem(Mem {
                kind: match (load, byte) {
                    (true, false) => MemKind::Ldr,
                    (false, false) => MemKind::Str,
                    (true, true) => MemKind::LdrB,
                    (false, true) => MemKind::StrB,
                },
                rd,
                rn,
                offset: MemOffset::Imm(imm * scale),
                add: true,
                pre_index: true,
                writeback: false,
            })
        }
        0x8 => {
            let load = bit(h, 11);
            let imm = ((h >> 6) & 0x1F) as u32;
            Op::Mem(Mem {
                kind: if load { MemKind::LdrH } else { MemKind::StrH },
                rd,
                rn,
                offset: MemOffset::Imm(imm * 2),
                add: true,
                pre_index: true,
                writeback: false,
            })
        }
        0x9 => {
            let load = bit(h, 11);
            let imm = ((h & 0xFF) as u32) << 2;
            Op::Mem(Mem {
                kind: if load { MemKind::Ldr } else { MemKind::Str },
                rd: ((h >> 8) & 7) as u8,
                rn: SP,
                offset: MemOffset::Imm(imm),
                add: true,
                pre_index: true,
                writeback: false,
            })
        }
        _ => Op::Unhandled { what: "Thumb load/store encoding" },
    }
}

fn decode_misc(h: u32) -> Op {
    match (h >> 8) & 0xF {
        0x0 => {
            // ADD/SUB SP, #imm7*4
            let sub = bit(h, 7);
            let imm = ((h & 0x7F) as u32) << 2;
            Op::Dp {
                op: if sub { DpOp::Sub } else { DpOp::Add },
                rd: SP,
                rn: SP,
                op2: Operand2::Imm(imm),
                set_flags: false,
            }
        }
        0x1 => Op::Unhandled { what: "Thumb CBZ/CBNZ (Thumb-2)" },
        0x2 => {
            let op = (h >> 6) & 3;
            let (signed, width) = match op {
                0 => (true, ExtWidth::H),
                1 => (true, ExtWidth::B),
                2 => (false, ExtWidth::H),
                _ => (false, ExtWidth::B),
            };
            Op::Extend {
                signed,
                width,
                rd: reg(h, 0),
                rn: 15,
                rm: Some(reg(h, 3)),
                rotate: 0,
            }
        }
        0x3 => Op::Unhandled { what: "Thumb CBZ/CBNZ (Thumb-2)" },
        0x4 | 0x5 => {
            // PUSH {reglist, LR}; bit8 is the LR flag and is part of the
            // 0xB4xx/0xB5xx encoding.
            let regs = ((h & 0xFF) as u16) | if bit(h, 8) { 1 << 14 } else { 0 };
            Op::Block(Block {
                load: false,
                rn: SP,
                regs,
                add: false,
                before: true,
                writeback: true,
                user: false,
            })
        }
        0x6 => {
            // SETEND / CPS
            if (h & 0xFFF7) == 0xB650 {
                return Op::Setend { big: bit(h, 3) };
            }
            if (h & 0xFFE7) == 0xB662 || (h & 0xFFE7) == 0xB672 {
                return Op::Cps {
                    imod: if bit(h, 4) { 2 } else { 0 },
                    aif: if bit(h, 3) { 4 } else { 0 },
                    mode: 0,
                };
            }
            Op::Unhandled { what: "Thumb miscellaneous encoding" }
        }
        0x9 => Op::Unhandled { what: "Thumb CBZ/CBNZ (Thumb-2)" },
        0xA => {
            let kind = match (h >> 6) & 3 {
                0 => RevKind::Rev,
                1 => RevKind::Rev16,
                3 => RevKind::RevSh,
                _ => return Op::Unhandled { what: "Thumb reverse encoding" },
            };
            Op::Rev { kind, rd: reg(h, 0), rm: reg(h, 3) }
        }
        0xB => Op::Unhandled { what: "Thumb CBZ/CBNZ (Thumb-2)" },
        0xC | 0xD => {
            // POP {reglist, PC}
            let regs = ((h & 0xFF) as u16) | if bit(h, 8) { 1 << 15 } else { 0 };
            Op::Block(Block {
                load: true,
                rn: SP,
                regs,
                add: true,
                before: false,
                writeback: true,
                user: false,
            })
        }
        0xE => Op::Bkpt { imm: h & 0xFF },
        0xF => Op::Nop,
        _ => Op::Unhandled { what: "Thumb miscellaneous encoding" },
    }
}

fn decode_thumb32(addr: u32, h1: u32, h2: u32) -> (Op, Cond) {
    let first = (h1 >> 11) & 0x1F;
    let second = (h2 >> 11) & 0x1F;
    // Thumb-1 only has BL/BLX here. Everything else in this space is Thumb-2.
    if first == 0b11110 && (second == 0b11111 || second == 0b11101) {
        let s = (h1 >> 10) & 1;
        let j1 = (h2 >> 13) & 1;
        let j2 = (h2 >> 11) & 1;
        let i1 = 1 ^ (j1 ^ s);
        let i2 = 1 ^ (j2 ^ s);
        let imm10 = h1 & 0x3FF;
        let imm11 = h2 & 0x7FF;
        let offset = (s << 24) | (i1 << 23) | (i2 << 22) | (imm10 << 12) | (imm11 << 1);
        let offset = sx(offset, 25);
        let exchange = second == 0b11101;
        let base = if exchange { addr.wrapping_add(4) & !3 } else { addr.wrapping_add(4) };
        let target = base.wrapping_add(offset);
        return (Op::B { target, link: true, exchange }, Cond::Al);
    }
    (Op::Unhandled { what: "Thumb-2 instruction" }, Cond::Al)
}
