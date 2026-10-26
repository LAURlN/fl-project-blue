//! A32 (ARMv6K) decoder.
//!
//! Original implementation from the publicly documented ARMv6K/A32 encoding
//! rules. It decodes every instruction class the target can execute; genuinely
//! unallocated or privileged encodings become `Op::Unhandled` so coverage
//! reporting can name them instead of silently skipping bytes.

use crate::insn::*;

fn sx(value: u32, bits: u32) -> u32 {
    let shift = 32 - bits;
    ((value << shift) as i32 >> shift) as u32
}

fn r(word: u32, shift: u32) -> u8 {
    ((word >> shift) & 0xF) as u8
}

fn bit(word: u32, n: u32) -> bool {
    (word >> n) & 1 != 0
}

fn reg_shift(_word: u32, shift_type: u32, amount: u8) -> Shift {
    let kind = match shift_type & 3 {
        0 => ShiftKind::Lsl,
        1 => ShiftKind::Lsr,
        2 => ShiftKind::Asr,
        _ => ShiftKind::Ror,
    };
    Shift { kind, amount: ShiftAmount::Imm(amount) }
}

fn imm_shift(word: u32) -> Shift {
    let shift_type = (word >> 5) & 3;
    let amount = ((word >> 7) & 0x1F) as u8;
    match (shift_type, amount) {
        (0, 0) => Shift::NONE,
        (1, 0) => Shift { kind: ShiftKind::Lsr, amount: ShiftAmount::Imm(32) },
        (2, 0) => Shift { kind: ShiftKind::Asr, amount: ShiftAmount::Imm(32) },
        (3, 0) => Shift { kind: ShiftKind::Rrx, amount: ShiftAmount::Imm(0) },
        _ => reg_shift(word, shift_type, amount),
    }
}

fn rotate_right(value: u32, amount: u32) -> u32 {
    let n = amount & 31;
    if n == 0 {
        value
    } else {
        value.rotate_right(n)
    }
}

pub fn decode(addr: u32, word: u32) -> Insn {
    let cond = Cond::from_bits(word >> 28);
    let mut op = if cond == Cond::Nv { decode_unconditional(word) } else { decode_conditional(word) };
    if let Op::B { ref mut target, exchange, .. } = op {
        if cond == Cond::Nv {
            let h = (word >> 24) & 1;
            let off = (sx(word & 0xFF_FFFF, 24) << 2).wrapping_add(h << 1);
            *target = addr.wrapping_add(8).wrapping_add(off);
            debug_assert!(exchange);
        } else {
            let off = sx(word & 0xFF_FFFF, 24) << 2;
            *target = addr.wrapping_add(8).wrapping_add(off);
        }
    }
    Insn { addr, size: 4, cond, op, raw: word }
}

fn decode_conditional(word: u32) -> Op {
    match (word >> 25) & 7 {
        0b000 => decode_dp_reg_or_misc(word),
        0b001 => decode_dp_imm_or_hint(word),
        0b010 | 0b011 => {
            if let Some(op) = decode_media(word) {
                op
            } else {
                decode_single_transfer(word)
            }
        }
        0b100 => decode_block(word),
        0b101 => decode_branch(word),
        0b110 => decode_coproc_load_store(word),
        _ => {
            if (word >> 24) & 0xF == 0xF {
                Op::Svc { imm: word & 0xFF_FFFF }
            } else {
                decode_coproc_register(word)
            }
        }
    }
}

fn decode_unconditional(word: u32) -> Op {
    // CLREX
    if word == 0xF57F_F01F {
        return Op::Clrex;
    }
    // DMB/DSB/ISB and other CP15 barriers, all no-ops under the one-guest-thread model.
    let barrier = [
        0xF57F_F04F, // DSB
        0xF57F_F05F, // DMB
        0xF57F_F06F, // ISB
        0xF57F_F07F,
        0xF57F_F08F,
        0xF57F_F09F,
    ];
    if barrier.contains(&word) {
        return Op::Barrier;
    }
    // PLD [Rn, #imm]
    if (word & 0xFFF0_F000) == 0xF5D0_F000 || (word & 0xFFF0_F000) == 0xF550_F000 {
        let add = bit(word, 23);
        return Op::Pld {
            rn: r(word, 16),
            offset: MemOffset::Imm(word & 0xFFF),
            add,
        };
    }
    // PLD [Rn, Rm, shift]
    if (word & 0xFFF0_FFF0) == 0xF7D0_F000 || (word & 0xFFF0_FFF0) == 0xF750_F000 {
        let shift = imm_shift(word);
        return Op::Pld {
            rn: r(word, 16),
            offset: MemOffset::Reg { rm: r(word, 0), shift },
            add: bit(word, 23),
        };
    }
    // BLX <label> (target is made absolute by `decode`).
    if (word & 0xFE00_0000) == 0xFA00_0000 {
        return Op::B { target: 0, link: true, exchange: true };
    }
    // SETEND
    if (word & 0xFFFF_FDFF) == 0xF101_0000 {
        return Op::Setend { big: bit(word, 9) };
    }
    // CPS
    if (word & 0xFFF1_FFE0) == 0xF100_0000 {
        return Op::Cps {
            imod: (word >> 18) & 3,
            aif: (word >> 6) & 7,
            mode: word & 0x1F,
        };
    }
    Op::Unhandled { what: "unconditional A32 encoding" }
}

fn decode_dp_imm_or_hint(word: u32) -> Op {
    // MSR (immediate) and architectural hints.
    if (word & 0x0FF0_0000) == 0x0320_0000 {
        let low = word & 0xFFFF;
        return match low {
            0xF000 => Op::Nop,
            0xF001..=0xF004 => Op::Nop,
            0xF0F0..=0xF0FF => Op::Nop,
            _ => Op::Unhandled { what: "MSR immediate" },
        };
    }
    let opcode = (word >> 21) & 0xF;
    let set_flags = bit(word, 20);
    let rn = r(word, 16);
    let rd = r(word, 12);
    let rotate = ((word >> 8) & 0xF) * 2;
    let imm = rotate_right(word & 0xFF, rotate);
    Op::Dp {
        op: DpOp::from_bits(opcode),
        rd,
        rn,
        op2: Operand2::Imm(imm),
        set_flags,
    }
}

fn decode_dp_reg_or_misc(word: u32) -> Op {
    // BKPT
    if (word & 0x0FF0_00F0) == 0x0120_0070 {
        return Op::Bkpt { imm: (((word >> 4) & 0xFFF0) | (word & 0xF)) };
    }
    // SWP / SWPB
    if (word & 0x0FB0_0FF0) == 0x0100_0090 {
        return Op::Swp { byte: bit(word, 22), rd: r(word, 12), rm: r(word, 0), rn: r(word, 16) };
    }
    // MUL / MLA
    if (word & 0x0FC0_00F0) == 0x0000_0090 {
        return Op::Mul {
            rd: r(word, 16),
            ra: r(word, 12),
            rm: r(word, 0),
            rs: r(word, 8),
            accumulate: bit(word, 21),
            set_flags: bit(word, 20),
        };
    }
    // UMULL / UMLAL / SMULL / SMLAL
    if (word & 0x0F80_00F0) == 0x0080_0090 {
        return Op::MulLong {
            signed: bit(word, 22),
            accumulate: bit(word, 21),
            set_flags: bit(word, 20),
            rd_lo: r(word, 12),
            rd_hi: r(word, 16),
            rm: r(word, 0),
            rs: r(word, 8),
        };
    }
    // Halfword multiply / multiply-accumulate (ARMv5TE).
    if (word & 0x0F80_0090) == 0x0100_0080 {
        return decode_halfword_mul(word);
    }
    // Synchronization primitives (LDREX/STREX family).
    if (word & 0x0F00_0FF0) == 0x0100_0F90 {
        return decode_sync(word);
    }
    // BX / BLX / BXJ
    if (word & 0x0FFF_FFF0) == 0x012F_FF10 {
        return Op::Bx { rm: r(word, 0), link: false, j: false };
    }
    if (word & 0x0FFF_FFF0) == 0x012F_FF30 {
        return Op::Bx { rm: r(word, 0), link: true, j: false };
    }
    if (word & 0x0FFF_FFF0) == 0x012F_FF20 {
        return Op::Bx { rm: r(word, 0), link: false, j: true };
    }
    // CLZ
    if (word & 0x0FFF_0FF0) == 0x016F_0F10 {
        return Op::Clz { rd: r(word, 12), rm: r(word, 0) };
    }
    // QADD/QSUB/QDADD/QDSUB
    if (word & 0x0F90_00F0) == 0x0100_0050 {
        let op = match (word >> 21) & 3 {
            0 => QAddOp::Qadd,
            1 => QAddOp::Qsub,
            2 => QAddOp::Qdadd,
            _ => QAddOp::Qdsub,
        };
        return Op::QAdd { op, rd: r(word, 12), rm: r(word, 16), rn: r(word, 0) };
    }
    // The remaining bit7=1, bit4=1 space is the extra load/store group.
    if bit(word, 7) && bit(word, 4) {
        return decode_extra_transfer(word);
    }
    // Data-processing (register-shifted register): bit4=1, bit7=0.
    if bit(word, 4) && !bit(word, 7) {
        let opcode = (word >> 21) & 0xF;
        return Op::Dp {
            op: DpOp::from_bits(opcode),
            rd: r(word, 12),
            rn: r(word, 16),
            op2: Operand2::Reg {
                rm: r(word, 0),
                shift: Shift {
                    kind: match (word >> 5) & 3 {
                        0 => ShiftKind::Lsl,
                        1 => ShiftKind::Lsr,
                        2 => ShiftKind::Asr,
                        _ => ShiftKind::Ror,
                    },
                    amount: ShiftAmount::Reg(r(word, 8)),
                },
            },
            set_flags: bit(word, 20),
        };
    }
    // Data-processing (register), including MOV/MVN and test operations.
    if !bit(word, 4) {
        return Op::Dp {
            op: DpOp::from_bits((word >> 21) & 0xF),
            rd: r(word, 12),
            rn: r(word, 16),
            op2: Operand2::Reg { rm: r(word, 0), shift: imm_shift(word) },
            set_flags: bit(word, 20),
        };
    }
    Op::Unhandled { what: "data-processing/misc A32 encoding" }
}

fn decode_halfword_mul(word: u32) -> Op {
    let op1 = (word >> 21) & 3;
    let rd = r(word, 16);
    let ra = r(word, 12);
    let rm = r(word, 8);
    let rn = r(word, 0);
    let x = bit(word, 5);
    let y = bit(word, 6);
    match op1 {
        0 => Op::HalfMul { accumulate: true, rd, rn, rm, rs: ra, x, y },
        2 => Op::HalfMulLong { rd_lo: ra, rd_hi: rd, rm: rn, rs: rm, x, y },
        3 => Op::HalfMul { accumulate: false, rd, rn, rm, rs: 0, x, y },
        _ => {
            if bit(word, 5) {
                Op::WordHalfMul { accumulate: false, top: y, rd, rn, rm, rs: 0 }
            } else {
                Op::WordHalfMul { accumulate: true, top: y, rd, rn, rm, rs: ra }
            }
        }
    }
}

fn decode_sync(word: u32) -> Op {
    let op = (word >> 20) & 0xF;
    let rn = r(word, 16);
    let rd = r(word, 12);
    let rm = r(word, 0);
    match op {
        0x8 => Op::Strex { size: ExSize::W, rd, rm, rn },
        0x9 => Op::Ldrex { size: ExSize::W, rd, rn },
        0xA => Op::Strexd { rd, rm, rn },
        0xB => Op::Ldrexd { rd, rn },
        0xC => Op::Strex { size: ExSize::B, rd, rm, rn },
        0xD => Op::Ldrex { size: ExSize::B, rd, rn },
        0xE => Op::Strex { size: ExSize::H, rd, rm, rn },
        0xF => Op::Ldrex { size: ExSize::H, rd, rn },
        _ => Op::Unhandled { what: "synchronization primitive" },
    }
}

fn decode_single_transfer(word: u32) -> Op {
    // I == 0 selects an immediate offset; I == 1 selects a register offset.
    let immediate = !bit(word, 25);
    let pre = bit(word, 24);
    let add = bit(word, 23);
    let byte = bit(word, 22);
    let writeback = bit(word, 21);
    let load = bit(word, 20);
    let rn = r(word, 16);
    let rd = r(word, 12);
    let offset = if immediate {
        MemOffset::Imm(word & 0xFFF)
    } else {
        if bit(word, 4) {
            return Op::Unhandled { what: "single transfer with register offset bit4=1" };
        }
        MemOffset::Reg { rm: r(word, 0), shift: imm_shift(word) }
    };
    let kind = match (load, byte) {
        (true, false) => MemKind::Ldr,
        (false, false) => MemKind::Str,
        (true, true) => MemKind::LdrB,
        (false, true) => MemKind::StrB,
    };
    Op::Mem(Mem {
        kind,
        rd,
        rn,
        offset,
        add,
        pre_index: pre,
        writeback: writeback || !pre,
    })
}

fn decode_extra_transfer(word: u32) -> Op {
    let pre = bit(word, 24);
    let add = bit(word, 23);
    let immediate = bit(word, 22);
    let writeback = bit(word, 21);
    let load = bit(word, 20);
    let rn = r(word, 16);
    let rd = r(word, 12);
    let op2 = (word >> 5) & 3;
    let offset = if immediate {
        MemOffset::Imm(((word >> 4) & 0xF0) | (word & 0xF))
    } else {
        MemOffset::Reg { rm: r(word, 0), shift: Shift::NONE }
    };
    let kind = match (op2, load) {
        (1, false) => MemKind::StrH,
        (1, true) => MemKind::LdrH,
        (2, false) => MemKind::LdrD,
        (2, true) => MemKind::LdrSb,
        (3, false) => MemKind::StrD,
        (3, true) => MemKind::LdrSh,
        _ => return Op::Unhandled { what: "extra transfer op2=0" },
    };
    Op::Mem(Mem {
        kind,
        rd,
        rn,
        offset,
        add,
        pre_index: pre,
        writeback: writeback || !pre,
    })
}

fn decode_block(word: u32) -> Op {
    Op::Block(Block {
        load: bit(word, 20),
        rn: r(word, 16),
        regs: (word & 0xFFFF) as u16,
        add: bit(word, 23),
        before: bit(word, 24),
        writeback: bit(word, 21),
        user: bit(word, 22),
    })
}

fn decode_branch(word: u32) -> Op {
    let link = bit(word, 24);
    let off = sx(word & 0xFF_FFFF, 24) << 2;
    // `target` is filled in relative to the instruction by the caller.
    Op::B { target: off, link, exchange: false }
}

fn decode_coproc_load_store(word: u32) -> Op {
    let cp = (word >> 8) & 0xF;
    // MRRC/MCRR (VMOV between two core registers and a double register).
    if cp == 11 && (word & 0x0FE0_0F00) == 0x0C40_0B00 && bit(word, 4) {
        let to_arm = bit(word, 20);
        let rt2 = r(word, 16);
        let rt = r(word, 12);
        let m = bit(word, 5);
        let vm = r(word, 0);
        let dm = ((m as u8) << 4) | vm;
        if dm >= 16 {
            return Op::Unhandled { what: "VFPv2 double register above d15" };
        }
        return if to_arm {
            Op::Vfp(VfpOp::ToTwoCore { dm, rt, rt2 })
        } else {
            Op::Vfp(VfpOp::FromTwoCore { dm, rt, rt2 })
        };
    }
    if cp == 10 || cp == 11 {
        return decode_vfp_load_store(word);
    }
    Op::Coproc { raw: word }
}

fn decode_coproc_register(word: u32) -> Op {
    let cp = (word >> 8) & 0xF;
    if cp == 10 || cp == 11 {
        if bit(word, 4) {
            decode_vfp_core(word)
        } else {
            decode_vfp_dp(word)
        }
    } else if cp == 15 && bit(word, 4) {
        decode_cp15(word)
    } else {
        Op::Coproc { raw: word }
    }
}

fn decode_cp15(word: u32) -> Op {
    let opc1 = (word >> 21) & 7;
    let mrc = bit(word, 20);
    let crn = (word >> 16) & 0xF;
    let rt = r(word, 12);
    let opc2 = (word >> 5) & 7;
    let crm = (word >> 0) & 0xF;
    // MRC p15, 0, Rt, c13, c0, 3 reads the user/thread ID register (TLS).
    if mrc && opc1 == 0 && crn == 13 && crm == 0 && opc2 == 3 {
        return Op::TlsRead { rd: rt };
    }
    // Cache/barrier maintenance operations: no-ops with one guest thread.
    if !mrc && opc1 == 0 && crn == 7 {
        return Op::Barrier;
    }
    Op::Coproc { raw: word }
}

fn decode_vfp_load_store(word: u32) -> Op {
    let pre = bit(word, 24);
    let add = bit(word, 23);
    let d_high = bit(word, 22);
    let writeback = bit(word, 21);
    let load = bit(word, 20);
    let rn = r(word, 16);
    let vd_field = r(word, 12);
    let size = if bit(word, 8) { VfpSize::Double } else { VfpSize::Single };
    let imm8 = (word & 0xFF) as u32;
    let vd = vfp_reg(vd_field, d_high, size);
    if size == VfpSize::Double && vd >= 16 {
        return Op::Unhandled { what: "VFPv2 double register above d15" };
    }
    // VLDR/VSTR: P=1, W=0.
    if pre && !writeback {
        return Op::Vfp(VfpOp::Mem {
            load,
            size,
            vd,
            rn,
            offset: imm8 << 2,
            add,
            pre_index: true,
            writeback: false,
        });
    }
    // LDM/STM forms. P=0,W=0 is increment-after without writeback, P=0,W=1 is
    // increment-after with writeback, P=1,W=1 is decrement-before with writeback.
    if !pre && !writeback {
        let count = match size {
            VfpSize::Single => imm8 as u8,
            VfpSize::Double => {
                if imm8 & 1 != 0 {
                    return Op::Unhandled { what: "FLDMX/FSTMX odd double-register list" };
                }
                (imm8 / 2) as u8
            }
        };
        if !vfp_list_fits(vd, count, size) {
            return Op::Unhandled { what: "VFPv2 register list past the register file" };
        }
        return Op::Vfp(VfpOp::MemMulti {
            load,
            size,
            vd,
            rn,
            count,
            add: true,
            pre_index: false,
            writeback: false,
        });
    }
    if !pre && writeback {
        let count = match size {
            VfpSize::Single => imm8 as u8,
            VfpSize::Double => {
                if imm8 & 1 != 0 {
                    return Op::Unhandled { what: "FLDMX/FSTMX odd double-register list" };
                }
                (imm8 / 2) as u8
            }
        };
        if !vfp_list_fits(vd, count, size) {
            return Op::Unhandled { what: "VFPv2 register list past the register file" };
        }
        return Op::Vfp(VfpOp::MemMulti {
            load,
            size,
            vd,
            rn,
            count,
            add: true,
            pre_index: false,
            writeback: true,
        });
    }
    if pre && writeback {
        let count = match size {
            VfpSize::Single => imm8 as u8,
            VfpSize::Double => {
                if imm8 & 1 != 0 {
                    return Op::Unhandled { what: "FLDMX/FSTMX odd double-register list" };
                }
                (imm8 / 2) as u8
            }
        };
        if !vfp_list_fits(vd, count, size) {
            return Op::Unhandled { what: "VFPv2 register list past the register file" };
        }
        return Op::Vfp(VfpOp::MemMulti {
            load,
            size,
            vd,
            rn,
            count,
            add: false,
            pre_index: true,
            writeback: true,
        });
    }
    Op::Unhandled { what: "VFP load/store encoding" }
}

fn vfp_reg(field: u8, high: bool, size: VfpSize) -> u8 {
    match size {
        VfpSize::Single => (field << 1) | (high as u8),
        VfpSize::Double => (high as u8) << 4 | field,
    }
}

/// VFPv2 exposes 32 single or 16 double registers; a list may not run past
/// the end of that file.
fn vfp_list_fits(first: u8, count: u8, size: VfpSize) -> bool {
    let limit = if size == VfpSize::Double { 16 } else { 32 };
    first as u32 + count as u32 <= limit
}

fn decode_vfp_core(word: u32) -> Op {
    let op = bit(word, 20);
    let vn = r(word, 16);
    let rt = r(word, 12);
    let n = bit(word, 7);
    let cp = (word >> 8) & 0xF;
    // VMOV between one core register and one single-precision register:
    // cond 1110 000 op Vn Rt 1010 N 00 1 0000
    if cp == 10
        && ((word >> 21) & 7) == 0
        && ((word >> 5) & 3) == 0
        && bit(word, 4)
        && (word & 0xF) == 0
    {
        let sn = (vn << 1) | (n as u8);
        return if op {
            Op::Vfp(VfpOp::ToCore { sn, rt })
        } else {
            Op::Vfp(VfpOp::FromCore { sn, rt })
        };
    }
    // VMRS / VMSR: cond 1110 111x 0001 Rt 1010 0001 0000. Bit 20 selects
    // the direction (1 = read FPSCR into Rt).
    if cp == 10
        && ((word & 0x0FFF_0FF0) == 0x0EF1_0A10 || (word & 0x0FFF_0FF0) == 0x0EE1_0A10)
        && (word & 0xF) == 0
    {
        return if op {
            Op::Vfp(VfpOp::Vmrs { rt })
        } else {
            Op::Vfp(VfpOp::Vmsr { rt })
        };
    }
    Op::Unhandled { what: "VFP core-register transfer" }
}

fn decode_vfp_dp(word: u32) -> Op {
    let opc1 = (((word >> 23) & 1) << 2) | (((word >> 21) & 1) << 1) | ((word >> 20) & 1);
    let d_high = bit(word, 22);
    let vd_field = r(word, 12);
    let vn_field = r(word, 16);
    let n = bit(word, 7);
    let m = bit(word, 5);
    let vm_field = r(word, 0);
    let size = if bit(word, 8) { VfpSize::Double } else { VfpSize::Single };
    let opc3 = bit(word, 6);
    let vd = vfp_reg(vd_field, d_high, size);
    let vn = vfp_reg(vn_field, n, size);
    let vm = vfp_reg(vm_field, m, size);
    // opc1 0..4 are the three-register arithmetic forms and read all three
    // registers. VFPv2 only has D0-D15, so reject encodings that address the
    // VFPv3 extension registers rather than letting them index past `Ctx::s`.
    if opc1 <= 4 && size == VfpSize::Double && (vd >= 16 || vn >= 16 || vm >= 16) {
        return Op::Unhandled { what: "VFPv2 double register above d15" };
    }

    match opc1 {
        0 | 1 => {
            // VMLA/VMLS/VNMLA/VNMLS
            let subtract = opc3;
            let negate = opc1 == 1;
            Op::Vfp(VfpOp::Mla { size, vd, vn, vm, subtract, negate })
        }
        2 => Op::Vfp(VfpOp::Mul { size, vd, vn, vm, negate: opc3 }),
        3 => {
            if opc3 {
                Op::Vfp(VfpOp::Sub { size, vd, vn, vm })
            } else {
                Op::Vfp(VfpOp::Add { size, vd, vn, vm })
            }
        }
        4 => {
            if opc3 {
                Op::Unhandled { what: "VFP VDIV with opc3=1" }
            } else {
                Op::Vfp(VfpOp::Div { size, vd, vn, vm })
            }
        }
        5 | 6 => Op::Unhandled { what: "VFP data-processing opc1 5/6" },
        _ => decode_vfp_two(word, size, vd_field, d_high, vn_field, n, vm_field, m, opc3),
    }
}

#[allow(clippy::too_many_arguments)]
fn decode_vfp_two(
    word: u32,
    size: VfpSize,
    vd_field: u8,
    d_high: bool,
    vn_field: u8,
    _n: bool,
    vm_field: u8,
    m: bool,
    opc3: bool,
) -> Op {
    let bit7 = bit(word, 7);
    let bit6 = opc3;
    let d = match size {
        VfpSize::Single => (vd_field << 1) | (d_high as u8),
        VfpSize::Double => (d_high as u8) << 4 | vd_field,
    };
    let mreg = vfp_reg(vm_field, m, size);
    let bad_d = size == VfpSize::Double && d >= 16;
    let bad_m = size == VfpSize::Double && mreg >= 16;
    // VMOV immediate is a VFPv3 encoding. ARM11 implements VFPv2, so reject
    // it instead of inventing a value for an instruction the guest CPU could
    // not execute.
    if vn_field == 0 && !bit6 {
        return Op::Unhandled { what: "VFPv3 VMOV immediate on VFPv2" };
    }
    match vn_field {
        0 => {
            if bad_d || bad_m {
                return Op::Unhandled { what: "VFPv2 double register above d15" };
            }
            if !bit6 {
                return Op::Unhandled { what: "VFP VMOV with opc3=0" };
            }
            if bit7 {
                Op::Vfp(VfpOp::Abs { size, vd: d, vm: mreg })
            } else {
                Op::Vfp(VfpOp::MovReg { size, vd: d, vm: mreg })
            }
        }
        1 => {
            if !bit6 {
                return Op::Unhandled { what: "VFP unary with opc3=0" };
            }
            if bad_d || bad_m {
                return Op::Unhandled { what: "VFPv2 double register above d15" };
            }
            if bit7 {
                Op::Vfp(VfpOp::Sqrt { size, vd: d, vm: mreg })
            } else {
                Op::Vfp(VfpOp::Neg { size, vd: d, vm: mreg })
            }
        }
        4 => {
            if !bit6 {
                return Op::Unhandled { what: "VFP compare with opc3=0" };
            }
            if bad_d || bad_m {
                return Op::Unhandled { what: "VFPv2 double register above d15" };
            }
            // opc2=4 compares against a register; opc2=5 compares against +0.0.
            Op::Vfp(VfpOp::Cmp { size, vd: d, vm: mreg, with_zero: false })
        }
        5 => {
            if !bit6 {
                return Op::Unhandled { what: "VFP compare-with-zero with opc3=0" };
            }
            if bad_d {
                return Op::Unhandled { what: "VFPv2 double register above d15" };
            }
            Op::Vfp(VfpOp::Cmp { size, vd: d, vm: 0, with_zero: true })
        }
        7 => {
            // VCVT between single and double.
            if !bit6 {
                return Op::Unhandled { what: "VFP VCVT with opc3=0" };
            }
            let to_single = bit(word, 8);
            let (vd, vm) = if to_single {
                // Sd = Vd:D, Dm = M:Vm
                let sd = (vd_field << 1) | (d_high as u8);
                let dm = ((m as u8) << 4) | vm_field;
                (sd, dm)
            } else {
                let dd = ((d_high as u8) << 4) | vd_field;
                let sm = (vm_field << 1) | (m as u8);
                (dd, sm)
            };
            if (to_single && vm >= 16) || (!to_single && vd >= 16) {
                return Op::Unhandled { what: "VFPv2 double register above d15" };
            }
            Op::Vfp(VfpOp::CvtSingleDouble { to_single, vd, vm })
        }
        8..=15 => {
            if !bit6 {
                return Op::Unhandled { what: "VFP integer convert with opc3=0" };
            }
            let opc2 = vn_field & 7;
            let to_integer = (opc2 & 4) != 0;
            let round_zero = bit7;
            if to_integer {
                let unsigned = (opc2 & 1) == 0;
                let d = (vd_field << 1) | (d_high as u8);
                let mreg = match size {
                    VfpSize::Single => (vm_field << 1) | (m as u8),
                    VfpSize::Double => ((m as u8) << 4) | vm_field,
                };
                if size == VfpSize::Double && mreg >= 16 {
                    return Op::Unhandled { what: "VFPv2 double register above d15" };
                }
                Op::Vfp(VfpOp::CvtFloatToInt { size, unsigned, round_zero, vd: d, vm: mreg })
            } else {
                let unsigned = !bit7;
                let d = match size {
                    VfpSize::Single => (vd_field << 1) | (d_high as u8),
                    VfpSize::Double => ((d_high as u8) << 4) | vd_field,
                };
                if size == VfpSize::Double && d >= 16 {
                    return Op::Unhandled { what: "VFPv2 double register above d15" };
                }
                let mreg = (vm_field << 1) | (m as u8);
                Op::Vfp(VfpOp::CvtIntToFloat { size, unsigned, vd: d, vm: mreg })
            }
        }
        _ => Op::Unhandled { what: "VFP two-register encoding" },
    }
}

/// Media instruction decoder. Called before the generic single-transfer decoder
/// because the architecture allocates some encodings in this space to media.
fn decode_media(word: u32) -> Option<Op> {
    if (word >> 25) & 7 != 0b011 {
        return None;
    }
    // Packing, unpacking, saturation, reversal and extension share this
    // space; try them first because their bit patterns overlap the parallel
    // operations below.
    if (word >> 23) & 0x1F == 0b01101 {
        if let Some(op) = decode_media_pack(word) {
            return Some(op);
        }
    }
    // Parallel addition/subtraction, signed and unsigned. Bits 27:24 are
    // 0110, bits 11:8 are 1111, bit 4 is 1; bit 22 selects unsigned, bits
    // 21:20 select plain/saturating/halving, bit 7 selects 8-bit lanes and
    // bits 6:5 select the lane operation.
    if (word & 0x0F00_0F10) == 0x0600_0F10 && ((word >> 20) & 0xF) != 0 {
        let signed = !bit(word, 22);
        let width8 = bit(word, 7);
        let op2 = (word >> 5) & 3;
        let op = if width8 {
            match op2 {
                0 => ParallelOp::Add8,
                3 => ParallelOp::Sub8,
                _ => return None,
            }
        } else {
            match op2 {
                0 => ParallelOp::Add16,
                1 => ParallelOp::Asx,
                2 => ParallelOp::Sax,
                _ => ParallelOp::Sub16,
            }
        };
        let (saturating, halving) = match (word >> 20) & 3 {
            1 => (false, false),
            2 => (true, false),
            3 => (false, true),
            _ => return None,
        };
        return Some(Op::Parallel {
            signed,
            saturating,
            halving,
            op,
            rd: r(word, 12),
            rn: r(word, 16),
            rm: r(word, 0),
        });
    }

    // Signed/dual multiplies.
    if (word >> 23) & 0x1F == 0b01110 {
        return decode_media_mul(word);
    }
    if (word >> 23) & 0x1F == 0b01111 {
        // USAD8/USADA8
        let op1 = (word >> 20) & 7;
        if op1 == 0 {
            let ra = r(word, 12);
            return Some(Op::Usad {
                accumulate: ra != 15,
                rd: r(word, 16),
                ra,
                rn: r(word, 0),
                rm: r(word, 8),
            });
        }
    }
    None
}

fn decode_media_pack(word: u32) -> Option<Op> {
    // Bits 23:20 select the family, and bits 7:4 (or the PKH low bits)
    // select the operation within that family.
    let family = (word >> 20) & 0xF;
    let ra = r(word, 16);
    let rd = r(word, 12);
    let rm = r(word, 0);
    let low = (word >> 4) & 0xF;
    let sat_shift = || {
        if bit(word, 6) {
            Shift { kind: ShiftKind::Asr, amount: ShiftAmount::Imm(((word >> 7) & 0x1F) as u8) }
        } else {
            Shift { kind: ShiftKind::Lsl, amount: ShiftAmount::Imm(((word >> 7) & 0x1F) as u8) }
        }
    };
    let extend = |signed: bool, width: ExtWidth| Op::Extend {
        signed,
        width,
        rd,
        rn: ra,
        rm: Some(rm),
        rotate: ((word >> 10) & 3) as u8 * 8,
    };
    match family {
        0x8 if low == 0xB => Some(Op::Sel { rd, rn: ra, rm }),
        0x8 if (word & 0x30) == 0x10 => Some(Op::Pkh {
            tb: bit(word, 6),
            rd,
            rn: ra,
            rm,
            shift: ((word >> 7) & 0x1F) as u8,
        }),
        0x8 if low == 0x7 => Some(extend(true, ExtWidth::B16)),
        0xC if low == 0x7 => Some(extend(false, ExtWidth::B16)),
        0xA if (word & 0x30) == 0x10 => Some(Op::Sat {
            signed: true,
            rd,
            rn: rm,
            imm: ra + 1,
            shift: sat_shift(),
        }),
        0xA if (word & 0xF0) == 0x30 => Some(Op::Sat16 { signed: true, rd, rn: rm, imm: ra + 1 }),
        0xA if low == 0x7 => Some(extend(true, ExtWidth::B)),
        0xE if (word & 0x30) == 0x10 => Some(Op::Sat {
            signed: false,
            rd,
            rn: rm,
            imm: ra,
            shift: sat_shift(),
        }),
        0xE if (word & 0xF0) == 0x30 => Some(Op::Sat16 { signed: false, rd, rn: rm, imm: ra }),
        0xE if low == 0x7 => Some(extend(false, ExtWidth::B)),
        0xB if low == 0x3 => Some(Op::Rev { kind: RevKind::Rev, rd, rm }),
        0xB if low == 0xB => Some(Op::Rev { kind: RevKind::Rev16, rd, rm }),
        0xB if low == 0x7 => Some(extend(true, ExtWidth::H)),
        0xF if low == 0xB => Some(Op::Rev { kind: RevKind::RevSh, rd, rm }),
        0xF if low == 0x7 => Some(extend(false, ExtWidth::H)),
        _ => None,
    }
}

fn decode_media_mul(word: u32) -> Option<Op> {
    let op1 = (word >> 20) & 7;
    let rd = r(word, 16);
    let ra = r(word, 12);
    let rm = r(word, 8);
    let rn = r(word, 0);
    let op2 = (word >> 5) & 7;
    match op1 {
        0 => Some(Op::DualMul {
            subtract: (op2 & 2) != 0,
            exchange: (op2 & 1) != 0,
            accumulate: ra != 15,
            rd,
            ra,
            rn,
            rm,
        }),
        4 => Some(Op::DualMulLong {
            subtract: (op2 & 2) != 0,
            exchange: (op2 & 1) != 0,
            rd_lo: ra,
            rd_hi: rd,
            rn,
            rm,
        }),
        _ => None,
    }
}
