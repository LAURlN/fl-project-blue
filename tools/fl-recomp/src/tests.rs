//! Ground-truth decode and discovery tests.
//!
//! Encodings are produced by an independent assembler (clang's integrated
//! ARMv6K assembler) and paired with the fields the ARM ARM specifies. The
//! switch tests build tiny synthetic images, so they do not need the game.

use crate::arm;
use crate::discover;
use crate::emit;
use crate::image::{Image, Segment};
use crate::insn::*;
use crate::thumb;
use std::path::{Path, PathBuf};
use std::process::Command;

fn arm_op(word: u32) -> Op {
    arm::decode(0x0010_0000, word).op
}

fn thumb_op(hw: u16) -> Op {
    thumb::decode(0x0010_0000, hw).op
}

#[test]
fn arm_data_processing() {
    // mov r0, #1
    assert!(matches!(
        arm_op(0xE3A0_0001),
        Op::Dp { op: DpOp::Mov, rd: 0, rn: 0, op2: Operand2::Imm(1), set_flags: false }
    ));
    // movs r1, r2, lsl #3
    assert!(matches!(
        arm_op(0xE1B0_1182),
        Op::Dp {
            op: DpOp::Mov,
            rd: 1,
            op2: Operand2::Reg { rm: 2, shift: Shift { kind: ShiftKind::Lsl, amount: ShiftAmount::Imm(3) } },
            set_flags: true,
            ..
        }
    ));
    // adds r3, r4, r5, lsr #7
    assert!(matches!(
        arm_op(0xE094_33A5),
        Op::Dp {
            op: DpOp::Add,
            rd: 3,
            rn: 4,
            op2: Operand2::Reg { rm: 5, shift: Shift { kind: ShiftKind::Lsr, amount: ShiftAmount::Imm(7) } },
            set_flags: true
        }
    ));
    // subs r6, r7, r8, asr #2
    assert!(matches!(
        arm_op(0xE057_6148),
        Op::Dp {
            op: DpOp::Sub,
            rd: 6,
            rn: 7,
            op2: Operand2::Reg { rm: 8, shift: Shift { kind: ShiftKind::Asr, amount: ShiftAmount::Imm(2) } },
            set_flags: true
        }
    ));
    // cmp r0, #0
    assert!(matches!(
        arm_op(0xE350_0000),
        Op::Dp { op: DpOp::Cmp, rn: 0, op2: Operand2::Imm(0), set_flags: true, .. }
    ));
    // cmn r1, r2
    assert!(matches!(
        arm_op(0xE171_0002),
        Op::Dp { op: DpOp::Cmn, rn: 1, op2: Operand2::Reg { rm: 2, .. }, set_flags: true, .. }
    ));
    // ands r9, r10, #0xff00 (rotated immediate)
    assert!(matches!(
        arm_op(0xE21A_9CFF),
        Op::Dp { op: DpOp::And, rd: 9, rn: 10, op2: Operand2::Imm(0x0000_FF00), set_flags: true }
    ));
    // orr r0, r1, r2, ror #5
    assert!(matches!(
        arm_op(0xE181_02E2),
        Op::Dp {
            op: DpOp::Orr,
            rd: 0,
            rn: 1,
            op2: Operand2::Reg { rm: 2, shift: Shift { kind: ShiftKind::Ror, amount: ShiftAmount::Imm(5) } },
            set_flags: false
        }
    ));
    // eor r0, r0, r0, rrx
    assert!(matches!(
        arm_op(0xE020_0060),
        Op::Dp {
            op: DpOp::Eor,
            rd: 0,
            rn: 0,
            op2: Operand2::Reg { rm: 0, shift: Shift { kind: ShiftKind::Rrx, amount: ShiftAmount::Imm(0) } },
            set_flags: false
        }
    ));
    // mvn r0, r1, lsl #16
    assert!(matches!(
        arm_op(0xE1E0_0801),
        Op::Dp {
            op: DpOp::Mvn,
            rd: 0,
            op2: Operand2::Reg { rm: 1, shift: Shift { kind: ShiftKind::Lsl, amount: ShiftAmount::Imm(16) } },
            set_flags: false,
            ..
        }
    ));
}

#[test]
fn arm_memory_and_blocks() {
    // ldr r0, [r1, #4]!
    assert!(matches!(
        arm_op(0xE5B1_0004),
        Op::Mem(Mem {
            kind: MemKind::Ldr,
            rd: 0,
            rn: 1,
            offset: MemOffset::Imm(4),
            add: true,
            pre_index: true,
            writeback: true
        })
    ));
    // strb r2, [r3], #-1
    assert!(matches!(
        arm_op(0xE443_2001),
        Op::Mem(Mem {
            kind: MemKind::StrB,
            rd: 2,
            rn: 3,
            offset: MemOffset::Imm(1),
            add: false,
            pre_index: false,
            writeback: true
        })
    ));
    // ldrsh r4, [r5, r6]
    assert!(matches!(
        arm_op(0xE195_40F6),
        Op::Mem(Mem { kind: MemKind::LdrSh, rd: 4, rn: 5, offset: MemOffset::Reg { rm: 6, .. }, .. })
    ));
    // ldrd r0, [r1, #8]
    assert!(matches!(
        arm_op(0xE1C1_00D8),
        Op::Mem(Mem {
            kind: MemKind::LdrD,
            rd: 0,
            rn: 1,
            offset: MemOffset::Imm(8),
            add: true,
            pre_index: true,
            writeback: false
        })
    ));
    // strd r2, [r3, #-8]
    assert!(matches!(
        arm_op(0xE143_20F8),
        Op::Mem(Mem { kind: MemKind::StrD, rd: 2, rn: 3, offset: MemOffset::Imm(8), add: false, .. })
    ));
    // ldmia r0!, {r1, r2, r3, pc}
    assert!(matches!(
        arm_op(0xE8B0_800E),
        Op::Block(Block {
            load: true,
            rn: 0,
            regs: 0x800E,
            add: true,
            before: false,
            writeback: true,
            user: false
        })
    ));
    // stmdb sp!, {r4-r11, lr}
    assert!(matches!(
        arm_op(0xE92D_4FF0),
        Op::Block(Block {
            load: false,
            rn: 13,
            regs: 0x4FF0,
            add: false,
            before: true,
            writeback: true,
            user: false
        })
    ));
}

#[test]
fn arm_multiply_media_and_barriers() {
    // mul r0, r1, r2
    assert!(matches!(
        arm_op(0xE000_0291),
        Op::Mul { rd: 0, rm: 1, rs: 2, accumulate: false, set_flags: false, .. }
    ));
    // mla r0, r1, r2, r3
    assert!(matches!(
        arm_op(0xE020_3291),
        Op::Mul { rd: 0, ra: 3, rm: 1, rs: 2, accumulate: true, set_flags: false }
    ));
    // umull r0, r1, r2, r3
    assert!(matches!(
        arm_op(0xE081_0392),
        Op::MulLong { signed: false, rd_lo: 0, rd_hi: 1, rm: 2, rs: 3, accumulate: false, set_flags: false }
    ));
    // smull r4, r5, r6, r7
    assert!(matches!(
        arm_op(0xE0C5_4796),
        Op::MulLong { signed: true, rd_lo: 4, rd_hi: 5, rm: 6, rs: 7, accumulate: false, set_flags: false }
    ));
    // clz r0, r1
    assert!(matches!(arm_op(0xE16F_0F11), Op::Clz { rd: 0, rm: 1 }));
    // rev r2, r3
    assert!(matches!(arm_op(0xE6BF_2F33), Op::Rev { kind: RevKind::Rev, rd: 2, rm: 3 }));
    // rev16 r4, r5
    assert!(matches!(arm_op(0xE6BF_4FB5), Op::Rev { kind: RevKind::Rev16, rd: 4, rm: 5 }));
    // revsh r6, r7
    assert!(matches!(arm_op(0xE6FF_6FB7), Op::Rev { kind: RevKind::RevSh, rd: 6, rm: 7 }));
    // qadd r0, r1, r2
    assert!(matches!(arm_op(0xE102_0051), Op::QAdd { op: QAddOp::Qadd, rd: 0, rn: 1, rm: 2 }));
    // qsub r0, r1, r2
    assert!(matches!(arm_op(0xE122_0051), Op::QAdd { op: QAddOp::Qsub, rd: 0, rn: 1, rm: 2 }));
    // uadd8 r0, r1, r2
    assert!(matches!(
        arm_op(0xE651_0F92),
        Op::Parallel { signed: false, saturating: false, halving: false, op: ParallelOp::Add8, rd: 0, rn: 1, rm: 2 }
    ));
    // qadd16 r0, r1, r2
    assert!(matches!(
        arm_op(0xE621_0F12),
        Op::Parallel { signed: true, saturating: true, halving: false, op: ParallelOp::Add16, .. }
    ));
    // shsub16 r0, r1, r2
    assert!(matches!(
        arm_op(0xE631_0F72),
        Op::Parallel { signed: true, saturating: false, halving: true, op: ParallelOp::Sub16, .. }
    ));
    // usat r0, #8, r1
    assert!(matches!(
        arm_op(0xE6E8_0011),
        Op::Sat { signed: false, rd: 0, rn: 1, imm: 8, shift: Shift { kind: ShiftKind::Lsl, amount: ShiftAmount::Imm(0) } }
    ));
    // ssat r0, #12, r1, asr #3
    assert!(matches!(
        arm_op(0xE6AB_01D1),
        Op::Sat {
            signed: true,
            rd: 0,
            rn: 1,
            imm: 12,
            shift: Shift { kind: ShiftKind::Asr, amount: ShiftAmount::Imm(3) }
        }
    ));
    // sel r0, r1, r2
    assert!(matches!(arm_op(0xE681_0FB2), Op::Sel { rd: 0, rn: 1, rm: 2 }));
    // pkhbt r0, r1, r2, lsl #4
    // pkhbt: tb == false; pkh tb (bit 6 set) would be PKHTB.
    assert!(matches!(arm_op(0xE681_0212), Op::Pkh { tb: false, rd: 0, rn: 1, rm: 2, shift: 4 }));
    // sxtab16 r0, r1, r2, ror #8
    assert!(matches!(
        arm_op(0xE681_0472),
        Op::Extend { signed: true, width: ExtWidth::B16, rd: 0, rn: 1, rm: Some(2), rotate: 8 }
    ));
    // uxtb r0, r1, ror #16
    assert!(matches!(
        arm_op(0xE6EF_0871),
        Op::Extend { signed: false, width: ExtWidth::B, rd: 0, rn: 15, rm: Some(1), rotate: 16 }
    ));
    // usad8 r0, r1, r2
    assert!(matches!(
        arm_op(0xE780_F211),
        Op::Usad { accumulate: false, rd: 0, ra: 15, rn: 1, rm: 2 }
    ));
    // ldrex r0, [r1]
    assert!(matches!(arm_op(0xE191_0F9F), Op::Ldrex { size: ExSize::W, rd: 0, rn: 1 }));
    // strex r0, r2, [r1]
    assert!(matches!(arm_op(0xE181_0F92), Op::Strex { size: ExSize::W, rd: 0, rm: 2, rn: 1 }));
    // ldrexd r0, r1, [r2]
    assert!(matches!(arm_op(0xE1B2_0F9F), Op::Ldrexd { rd: 0, rn: 2 }));
    // strexd r0, r2, r3, [r4]
    assert!(matches!(arm_op(0xE1A4_0F92), Op::Strexd { rd: 0, rm: 2, rn: 4 }));
    // swp r0, r1, [r2]
    assert!(matches!(arm_op(0xE102_0091), Op::Swp { byte: false, rd: 0, rm: 1, rn: 2 }));
    // mrc p15, 0, r0, c13, c0, 3
    assert!(matches!(arm_op(0xEE1D_0F70), Op::TlsRead { rd: 0 }));
    // svc #0x12
    assert!(matches!(arm_op(0xEF00_0012), Op::Svc { imm: 0x12 }));
    // bx lr
    assert!(matches!(arm_op(0xE12F_FF1E), Op::Bx { rm: 14, link: false, j: false }));
    // blx r3
    assert!(matches!(arm_op(0xE12F_FF33), Op::Bx { rm: 3, link: true, j: false }));
}

#[test]
fn arm_vfp() {
    // vadd.f32 s0, s1, s2
    assert!(matches!(
        arm_op(0xEE30_0A81),
        Op::Vfp(VfpOp::Add { size: VfpSize::Single, vd: 0, vn: 1, vm: 2 })
    ));
    // vadd.f64 d0, d1, d2
    assert!(matches!(
        arm_op(0xEE31_0B02),
        Op::Vfp(VfpOp::Add { size: VfpSize::Double, vd: 0, vn: 1, vm: 2 })
    ));
    // vsub.f32 s3, s4, s5
    assert!(matches!(
        arm_op(0xEE72_1A62),
        Op::Vfp(VfpOp::Sub { size: VfpSize::Single, vd: 3, vn: 4, vm: 5 })
    ));
    // vmul.f64 d3, d4, d5
    assert!(matches!(
        arm_op(0xEE24_3B05),
        Op::Vfp(VfpOp::Mul { size: VfpSize::Double, vd: 3, vn: 4, vm: 5, negate: false })
    ));
    // vdiv.f32 s6, s7, s8
    assert!(matches!(
        arm_op(0xEE83_3A84),
        Op::Vfp(VfpOp::Div { size: VfpSize::Single, vd: 6, vn: 7, vm: 8 })
    ));
    // vmla.f32 s0, s1, s2
    assert!(matches!(
        arm_op(0xEE00_0A81),
        Op::Vfp(VfpOp::Mla { size: VfpSize::Single, vd: 0, vn: 1, vm: 2, subtract: false, negate: false })
    ));
    // vmls.f64 d0, d1, d2
    assert!(matches!(
        arm_op(0xEE01_0B42),
        Op::Vfp(VfpOp::Mla { size: VfpSize::Double, vd: 0, vn: 1, vm: 2, subtract: true, negate: false })
    ));
    // vneg.f32 s0, s1
    assert!(matches!(
        arm_op(0xEEB1_0A60),
        Op::Vfp(VfpOp::Neg { size: VfpSize::Single, vd: 0, vm: 1 })
    ));
    // vabs.f64 d0, d1
    assert!(matches!(
        arm_op(0xEEB0_0BC1),
        Op::Vfp(VfpOp::Abs { size: VfpSize::Double, vd: 0, vm: 1 })
    ));
    // vsqrt.f32 s0, s1
    assert!(matches!(
        arm_op(0xEEB1_0AE0),
        Op::Vfp(VfpOp::Sqrt { size: VfpSize::Single, vd: 0, vm: 1 })
    ));
    // vcmp.f32 s0, s1
    assert!(matches!(
        arm_op(0xEEB4_0A60),
        Op::Vfp(VfpOp::Cmp { size: VfpSize::Single, vd: 0, vm: 1, with_zero: false })
    ));
    // vcmpe.f32 s0, #0
    assert!(matches!(
        arm_op(0xEEB5_0AC0),
        Op::Vfp(VfpOp::Cmp { size: VfpSize::Single, vd: 0, vm: 0, with_zero: true })
    ));
    // vcmp.f64 d0, d1
    assert!(matches!(
        arm_op(0xEEB4_0B41),
        Op::Vfp(VfpOp::Cmp { size: VfpSize::Double, vd: 0, vm: 1, with_zero: false })
    ));
    // vcvt.f32.s32 s0, s1
    assert!(matches!(
        arm_op(0xEEB8_0AE0),
        Op::Vfp(VfpOp::CvtIntToFloat { size: VfpSize::Single, unsigned: false, vd: 0, vm: 1 })
    ));
    // vcvt.s32.f32 s0, s1
    assert!(matches!(
        arm_op(0xEEBD_0AE0),
        Op::Vfp(VfpOp::CvtFloatToInt { size: VfpSize::Single, unsigned: false, round_zero: true, vd: 0, vm: 1 })
    ));
    // vcvt.f64.f32 d0, s1
    assert!(matches!(
        arm_op(0xEEB7_0AE0),
        Op::Vfp(VfpOp::CvtSingleDouble { to_single: false, vd: 0, vm: 1 })
    ));
    // vcvt.f32.f64 s0, d1
    assert!(matches!(
        arm_op(0xEEB7_0BC1),
        Op::Vfp(VfpOp::CvtSingleDouble { to_single: true, vd: 0, vm: 1 })
    ));
    // vmov r0, s0
    assert!(matches!(arm_op(0xEE10_0A10), Op::Vfp(VfpOp::ToCore { sn: 0, rt: 0 })));
    // vmov s0, r0
    assert!(matches!(arm_op(0xEE00_0A10), Op::Vfp(VfpOp::FromCore { sn: 0, rt: 0 })));
    // vmov r0, r1, d0 / vmov d0, r0, r1
    assert!(matches!(arm_op(0xEC51_0B10), Op::Vfp(VfpOp::ToTwoCore { dm: 0, rt: 0, rt2: 1 })));
    assert!(matches!(arm_op(0xEC41_0B10), Op::Vfp(VfpOp::FromTwoCore { dm: 0, rt: 0, rt2: 1 })));
    // vmrs r0, fpscr / vmsr fpscr, r0
    assert!(matches!(arm_op(0xEEF1_0A10), Op::Vfp(VfpOp::Vmrs { rt: 0 })));
    assert!(matches!(arm_op(0xEEE1_0A10), Op::Vfp(VfpOp::Vmsr { rt: 0 })));
    // vldr s0, [r1, #4] / vldr s1, [r1, #4] / vstr s2, [r3, #8]
    assert!(matches!(
        arm_op(0xED91_0A01),
        Op::Vfp(VfpOp::Mem { load: true, size: VfpSize::Single, vd: 0, rn: 1, offset: 4, add: true, pre_index: true, writeback: false })
    ));
    assert!(matches!(
        arm_op(0xEDD1_0A01),
        Op::Vfp(VfpOp::Mem { load: true, size: VfpSize::Single, vd: 1, rn: 1, offset: 4, .. })
    ));
    assert!(matches!(
        arm_op(0xED83_1A02),
        Op::Vfp(VfpOp::Mem { load: false, size: VfpSize::Single, vd: 2, rn: 3, offset: 8, .. })
    ));
    // vstr d0, [r1, #-8]
    assert!(matches!(
        arm_op(0xED01_0B02),
        Op::Vfp(VfpOp::Mem { load: false, size: VfpSize::Double, vd: 0, rn: 1, offset: 8, add: false, pre_index: true, writeback: false })
    ));
    // vldm r0!, {d8-d11}
    assert!(matches!(
        arm_op(0xECB0_8B08),
        Op::Vfp(VfpOp::MemMulti { load: true, size: VfpSize::Double, vd: 8, rn: 0, count: 4, add: true, pre_index: false, writeback: true })
    ));
    // vldm r0!, {s0-s3} / vldm r0!, {d0-d3} / vstm r1, {s2-s5}
    assert!(matches!(
        arm_op(0xECB0_0A04),
        Op::Vfp(VfpOp::MemMulti { load: true, size: VfpSize::Single, vd: 0, rn: 0, count: 4, add: true, pre_index: false, writeback: true })
    ));
    assert!(matches!(
        arm_op(0xECB0_0B08),
        Op::Vfp(VfpOp::MemMulti { load: true, size: VfpSize::Double, vd: 0, rn: 0, count: 4, .. })
    ));
    assert!(matches!(
        arm_op(0xEC81_1A04),
        Op::Vfp(VfpOp::MemMulti { load: false, size: VfpSize::Single, vd: 2, rn: 1, count: 4, add: true, pre_index: false, writeback: false })
    ));
    // vpush {d8-d11}
    assert!(matches!(
        arm_op(0xED2D_8B08),
        Op::Vfp(VfpOp::MemMulti { load: false, size: VfpSize::Double, vd: 8, rn: 13, count: 4, add: false, pre_index: true, writeback: true })
    ));
    // vcmp s0, s0 must not be mistaken for compare-with-zero.
    assert!(matches!(
        arm_op(0xEEB4_0A40),
        Op::Vfp(VfpOp::Cmp { size: VfpSize::Single, vd: 0, vm: 0, with_zero: false })
    ));
    // vcvt.f32.u32 / vcvt.u32.f32 / cross-size conversions
    assert!(matches!(
        arm_op(0xEEB8_0A60),
        Op::Vfp(VfpOp::CvtIntToFloat { size: VfpSize::Single, unsigned: true, vd: 0, vm: 1 })
    ));
    assert!(matches!(
        arm_op(0xEEBC_0AE0),
        Op::Vfp(VfpOp::CvtFloatToInt { size: VfpSize::Single, unsigned: true, round_zero: true, vd: 0, vm: 1 })
    ));
    assert!(matches!(
        arm_op(0xEEB8_0BE0),
        Op::Vfp(VfpOp::CvtIntToFloat { size: VfpSize::Double, unsigned: false, vd: 0, vm: 1 })
    ));
    assert!(matches!(
        arm_op(0xEEBD_0BC1),
        Op::Vfp(VfpOp::CvtFloatToInt { size: VfpSize::Double, unsigned: false, round_zero: true, vd: 0, vm: 1 })
    ));
}

#[test]
fn thumb_1() {
    // movs r0, #1
    assert!(matches!(
        thumb_op(0x2001),
        Op::Dp { op: DpOp::Mov, rd: 0, op2: Operand2::Imm(1), set_flags: true, .. }
    ));
    // adds r0, r1, r2
    assert!(matches!(
        thumb_op(0x1888),
        Op::Dp { op: DpOp::Add, rd: 0, rn: 1, op2: Operand2::Reg { rm: 2, .. }, set_flags: true }
    ));
    // subs r0, r1, #3
    assert!(matches!(
        thumb_op(0x1EC8),
        Op::Dp { op: DpOp::Sub, rd: 0, rn: 1, op2: Operand2::Imm(3), set_flags: true }
    ));
    // lsls r0, r1, #4
    assert!(matches!(
        thumb_op(0x0108),
        Op::Dp {
            op: DpOp::Mov,
            rd: 0,
            op2: Operand2::Reg { rm: 1, shift: Shift { kind: ShiftKind::Lsl, amount: ShiftAmount::Imm(4) } },
            set_flags: true,
            ..
        }
    ));
    // lsrs r2, r3, #5
    assert!(matches!(
        thumb_op(0x095A),
        Op::Dp { rd: 2, op2: Operand2::Reg { rm: 3, shift: Shift { kind: ShiftKind::Lsr, amount: ShiftAmount::Imm(5) } }, .. }
    ));
    // asrs r4, r5, #6
    assert!(matches!(
        thumb_op(0x11AC),
        Op::Dp { rd: 4, op2: Operand2::Reg { rm: 5, shift: Shift { kind: ShiftKind::Asr, amount: ShiftAmount::Imm(6) } }, .. }
    ));
    // ands/eors/orrs/mvns
    assert!(matches!(thumb_op(0x4008), Op::Dp { op: DpOp::And, rd: 0, rn: 0, .. }));
    assert!(matches!(thumb_op(0x4048), Op::Dp { op: DpOp::Eor, rd: 0, rn: 0, .. }));
    assert!(matches!(thumb_op(0x4308), Op::Dp { op: DpOp::Orr, rd: 0, rn: 0, .. }));
    assert!(matches!(thumb_op(0x43C8), Op::Dp { op: DpOp::Mvn, rd: 0, op2: Operand2::Reg { rm: 1, .. }, .. }));
    // muls r0, r1, r0
    assert!(matches!(
        thumb_op(0x4348),
        Op::Mul { rd: 0, rm: 1, rs: 0, accumulate: false, set_flags: true, .. }
    ));
    // rsbs r0, r1, #0 is -r1, not -r0
    assert!(matches!(
        thumb_op(0x4248),
        Op::Dp { op: DpOp::Rsb, rd: 0, rn: 1, op2: Operand2::Imm(0), set_flags: true }
    ));
    // ldr r0, [pc, #16]
    assert!(matches!(
        thumb_op(0x4804),
        Op::Mem(Mem { kind: MemKind::Ldr, rd: 0, rn: PC, offset: MemOffset::Imm(16), add: true, pre_index: true, writeback: false })
    ));
    // ldr r1, [r2, #12] / str r3, [r4, #8]
    assert!(matches!(thumb_op(0x68D1), Op::Mem(Mem { kind: MemKind::Ldr, rd: 1, rn: 2, offset: MemOffset::Imm(12), .. })));
    assert!(matches!(thumb_op(0x60A3), Op::Mem(Mem { kind: MemKind::Str, rd: 3, rn: 4, offset: MemOffset::Imm(8), .. })));
    // ldrb r0, [r1, #2] / strh r2, [r3, #4]
    assert!(matches!(thumb_op(0x7888), Op::Mem(Mem { kind: MemKind::LdrB, rd: 0, rn: 1, offset: MemOffset::Imm(2), .. })));
    assert!(matches!(thumb_op(0x809A), Op::Mem(Mem { kind: MemKind::StrH, rd: 2, rn: 3, offset: MemOffset::Imm(4), .. })));
    // ldrsb r0, [r1, r2] / ldrsh r3, [r4, r5]
    assert!(matches!(thumb_op(0x5688), Op::Mem(Mem { kind: MemKind::LdrSb, rd: 0, rn: 1, offset: MemOffset::Reg { rm: 2, .. }, .. })));
    assert!(matches!(thumb_op(0x5F63), Op::Mem(Mem { kind: MemKind::LdrSh, rd: 3, rn: 4, offset: MemOffset::Reg { rm: 5, .. }, .. })));
    // add r0, sp, #16 / sub sp, #8
    assert!(matches!(thumb_op(0xA804), Op::Dp { op: DpOp::Add, rd: 0, rn: SP, op2: Operand2::Imm(16), set_flags: false }));
    assert!(matches!(thumb_op(0xB082), Op::Dp { op: DpOp::Sub, rd: SP, rn: SP, op2: Operand2::Imm(8), set_flags: false }));
    // push {r4-r7, lr} / pop {r4-r7, pc}
    assert!(matches!(thumb_op(0xB5F0), Op::Block(Block { load: false, rn: SP, regs: 0x40F0, add: false, before: true, writeback: true, .. })));
    assert!(matches!(thumb_op(0xBDF0), Op::Block(Block { load: true, rn: SP, regs: 0x80F0, add: true, before: false, writeback: true, .. })));
    // bx lr / blx r3
    assert!(matches!(thumb_op(0x4770), Op::Bx { rm: 14, link: false, j: false }));
    assert!(matches!(thumb_op(0x4798), Op::Bx { rm: 3, link: true, j: false }));
    // mov r8, r0 / add r8, r0 / cmp r8, r1
    assert!(matches!(thumb_op(0x4680), Op::Dp { op: DpOp::Mov, rd: 8, op2: Operand2::Reg { rm: 0, .. }, set_flags: false, .. }));
    assert!(matches!(thumb_op(0x4480), Op::Dp { op: DpOp::Add, rd: 8, rn: 8, op2: Operand2::Reg { rm: 0, .. }, set_flags: false }));
    assert!(matches!(thumb_op(0x4588), Op::Dp { op: DpOp::Cmp, rd: 8, rn: 8, op2: Operand2::Reg { rm: 1, .. }, set_flags: true }));
    // bne +0 from 0x100036 -> 0x10003a
    let b = thumb::decode(0x0010_0036, 0xD100);
    assert!(matches!(b.op, Op::B { target: 0x0010_003A, link: false, exchange: false }));
    assert_eq!(b.cond, Cond::Ne);
    // svc / bkpt
    assert!(matches!(thumb_op(0xDF12), Op::Svc { imm: 0x12 }));
    assert!(matches!(thumb_op(0xBE42), Op::Bkpt { imm: 0x42 }));
    // ldmia r0!, {r1, r2} / stmia r0!, {r1, r2}
    assert!(matches!(thumb_op(0xC806), Op::Block(Block { load: true, rn: 0, regs: 0x0006, add: true, before: false, writeback: true, .. })));
    assert!(matches!(thumb_op(0xC006), Op::Block(Block { load: false, rn: 0, regs: 0x0006, add: true, before: false, writeback: true, .. })));
    // rev / rev16 / revsh
    assert!(matches!(thumb_op(0xBA08), Op::Rev { kind: RevKind::Rev, rd: 0, rm: 1 }));
    assert!(matches!(thumb_op(0xBA5A), Op::Rev { kind: RevKind::Rev16, rd: 2, rm: 3 }));
    assert!(matches!(thumb_op(0xBAEC), Op::Rev { kind: RevKind::RevSh, rd: 4, rm: 5 }));
}

#[test]
fn thumb_bl_pair() {
    // bl 0x100040 from 0x10003c
    let insn = thumb::decode32(0x0010_003C, 0xF000, 0xF800);
    assert!(matches!(insn.op, Op::B { target: 0x0010_0040, link: true, exchange: false }));
    assert_eq!(insn.size, 4);
    let insn = thumb::decode32(0x0010_003C, 0xF000, 0xE800);
    assert!(matches!(insn.op, Op::B { target: 0x0010_0040, link: true, exchange: true }));
}

#[test]
fn emitted_semantics_compile_and_run() {
    // This test needs clang and the private runtime checkout. It skips cleanly
    // in a source-only checkout instead of failing for a missing local port.
    let Some(runtime) = runtime_dir() else { return };
    if Command::new("clang").arg("--version").output().is_err() {
        return;
    }

    let image = synthetic(&[
        0xE091_0002, // adds r0, r1, r2
        0xE1A0_F00E, // mov pc, lr
        0xE1B0_0231, // movs r0, r1, lsr r2
        0xE1A0_F00E,
        0xEE00_0A81, // vmla.f32 s0, s1, s2
        0xE1A0_F00E,
        0xEE10_0AC1, // vnmla.f32 s0, s1, s2
        0xE1A0_F00E,
        0xEE10_0A81, // vnmls.f32 s0, s1, s2
        0xE1A0_F00E,
        0xEE81_0B02, // vdiv.f64 d0, d1, d2
        0xE1A0_F00E,
        0xEEB4_0A60, // vcmp.f32 s0, s1
        0xE1A0_F00E,
    ]);
    let hints = discover::EntryHints {
        entries: [
            0x0010_0000u32,
            0x0010_0008,
            0x0010_0010,
            0x0010_0018,
            0x0010_0020,
            0x0010_0028,
            0x0010_0030,
        ]
        .into_iter()
        .map(|addr| (addr, Mode::Arm))
        .collect(),
        polls: Vec::new(),
    };
    let analysis = discover::analyze(&image, &hints);
    assert!(analysis.unhandled.is_empty());
    assert_eq!(analysis.functions.len(), 7);

    let dir = std::env::temp_dir().join(format!("fl-recomp-emit-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).expect("temp dir");
    emit::emit_all(&image, &analysis, &dir, &[]).expect("emit");

    let harness = r#"
#include "fl_recomp.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

uint8_t *recomp_mem;
/* Offline harness: no hooks are registered, but generated entry checks use the ABI. */
static uint8_t hook_pages[1u << 20];
uint8_t *recomp_hook_page_map = hook_pages;
int recomp_hook_enter(Ctx *ctx, uint32_t addr) { (void)ctx; (void)addr; return 0; }

void recomp_svc(Ctx *ctx, uint32_t imm, uint32_t addr) { (void)ctx; (void)imm; (void)addr; }
void recomp_call_indirect(Ctx *ctx, uint32_t target) { (void)ctx; (void)target; }
void recomp_unhandled(Ctx *ctx, uint32_t addr, const char *what) {
    (void)ctx; (void)addr; (void)what; abort();
}
void recomp_coproc(Ctx *ctx, uint32_t addr, uint32_t raw) {
    (void)ctx; (void)addr; (void)raw; abort();
}

static int bad;
#define CHECK_U32(actual, expected) do { \
    uint32_t a_ = (uint32_t)(actual), e_ = (uint32_t)(expected); \
    if (a_ != e_) { fprintf(stderr, "%s: got %08x want %08x\n", #actual, a_, e_); bad = 1; } \
} while (0)
#define CHECK_F32(ctx, reg, expected) do { \
    float a_ = get_f32(&(ctx), (reg)); \
    if (a_ != (expected)) { fprintf(stderr, "s%d: got %.9g want %.9g\n", (reg), a_, (double)(expected)); bad = 1; } \
} while (0)

int main(void) {
    recomp_mem = calloc(1, 0x1000);
    if (!recomp_mem) return 2;
    Ctx ctx;

    memset(&ctx, 0, sizeof(ctx));
    ctx.r[1] = 0x7FFFFFFFu; ctx.r[2] = 1;
    fn_00100000(&ctx);
    CHECK_U32(ctx.r[0], 0x80000000u);
    CHECK_U32(ctx.n, 1); CHECK_U32(ctx.z, 0); CHECK_U32(ctx.c, 0); CHECK_U32(ctx.v, 1);

    memset(&ctx, 0, sizeof(ctx));
    ctx.r[1] = 0xFFFFFFFFu; ctx.r[2] = 1;
    fn_00100000(&ctx);
    CHECK_U32(ctx.r[0], 0); CHECK_U32(ctx.c, 1); CHECK_U32(ctx.v, 0);

    /* Register-specified LSR by zero preserves the operand and carry. */
    memset(&ctx, 0, sizeof(ctx));
    ctx.r[1] = 0x80000000u; ctx.r[2] = 0;
    fn_00100008(&ctx);
    CHECK_U32(ctx.r[0], 0x80000000u); CHECK_U32(ctx.c, 0); CHECK_U32(ctx.z, 0);
    memset(&ctx, 0, sizeof(ctx));
    ctx.r[1] = 0x80000000u; ctx.r[2] = 32;
    fn_00100008(&ctx);
    CHECK_U32(ctx.r[0], 0); CHECK_U32(ctx.c, 1); CHECK_U32(ctx.z, 1);

    memset(&ctx, 0, sizeof(ctx));
    set_f32(&ctx, 0, 1.0f); set_f32(&ctx, 1, 2.0f); set_f32(&ctx, 2, 3.0f);
    fn_00100010(&ctx);
    CHECK_F32(ctx, 0, 7.0f);

    memset(&ctx, 0, sizeof(ctx));
    set_f32(&ctx, 0, 1.0f); set_f32(&ctx, 1, 2.0f); set_f32(&ctx, 2, 3.0f);
    fn_00100018(&ctx);
    CHECK_F32(ctx, 0, -7.0f);

    memset(&ctx, 0, sizeof(ctx));
    set_f32(&ctx, 0, 1.0f); set_f32(&ctx, 1, 2.0f); set_f32(&ctx, 2, 3.0f);
    fn_00100020(&ctx);
    CHECK_F32(ctx, 0, 5.0f);

    memset(&ctx, 0, sizeof(ctx));
    set_f64(&ctx, 0, 0.0); set_f64(&ctx, 1, 1.0); set_f64(&ctx, 2, 4.0);
    fn_00100028(&ctx);
    if (get_f64(&ctx, 0) != 0.25) { fprintf(stderr, "vdiv wrong\n"); bad = 1; }

    memset(&ctx, 0, sizeof(ctx));
    set_f32(&ctx, 0, 1.0f); set_f32(&ctx, 1, 2.0f);
    fn_00100030(&ctx);
    CHECK_U32(ctx.fpscr >> 28, 0x8);

    free(recomp_mem);
    if (bad) return 1;
    puts("emitted semantics ok");
    return 0;
}
"#;
    let harness_path = dir.join("harness.c");
    std::fs::write(&harness_path, harness).expect("harness");

    let exe = dir.join(if cfg!(windows) { "harness.exe" } else { "harness" });
    let mut sources = vec![harness_path.clone()];
    for entry in std::fs::read_dir(&dir).expect("generated dir") {
        let path = entry.expect("entry").path();
        if path.extension().and_then(|e| e.to_str()) == Some("c") && path != harness_path {
            sources.push(path);
        }
    }
    sources.push(runtime.join("src/arm_ops.c"));

    let mut cmd = Command::new("clang");
    cmd.args(["-std=c17", "-O0", "-ffp-contract=off"])
        .arg("-I")
        .arg(runtime.join("include"))
        .arg("-I")
        .arg(&dir);
    for source in &sources {
        cmd.arg(source);
    }
    let output = cmd.arg("-lm").arg("-o").arg(&exe).output().expect("clang");
    assert!(
        output.status.success(),
        "compile failed:\n{}\n{}",
        String::from_utf8_lossy(&output.stdout),
        String::from_utf8_lossy(&output.stderr)
    );
    let run = Command::new(&exe).output().expect("run harness");
    assert!(
        run.status.success(),
        "semantic harness failed:\n{}\n{}",
        String::from_utf8_lossy(&run.stdout),
        String::from_utf8_lossy(&run.stderr)
    );
    let _ = std::fs::remove_dir_all(&dir);
}

fn runtime_dir() -> Option<PathBuf> {
    if let Ok(dir) = std::env::var("FL_RUNTIME_DIR") {
        let p = PathBuf::from(dir);
        return p.join("include/recomp.h").is_file().then_some(p);
    }
    let manifest = Path::new(env!("CARGO_MANIFEST_DIR"));
    for candidate in [
        manifest.join("../../port/runtime"),
        manifest.join("../../../../fl-project-blue/port/runtime"),
    ] {
        if candidate.join("include/recomp.h").is_file() {
            return Some(candidate);
        }
    }
    None
}

fn synthetic(words: &[u32]) -> Image {
    let mut code = vec![0u8; 0x1000];
    for (i, word) in words.iter().enumerate() {
        code[i * 4..i * 4 + 4].copy_from_slice(&word.to_le_bytes());
    }
    let text = Segment { addr: 0x0010_0000, size: (words.len() * 4) as u32, pages: 1, file_offset: 0 };
    let empty = Segment { addr: 0x0020_0000, size: 0, pages: 0, file_offset: 0 };
    Image {
        code,
        text,
        rodata: empty,
        data: empty,
        bss_size: 0,
        stack_size: 0,
        entry: 0x0010_0000,
        exheader: vec![],
    }
}

#[test]
fn switch_add_pc_table() {
    let image = synthetic(&[
        0xE350_0002, // cmp r0, #2
        0xE08F_F100, // add pc, pc, r0, lsl #2
        0xEA00_0004, // b 0x100020
        0xEA00_0001, // b 0x100018
        0xEA00_0001, // b 0x10001c
        0xEA00_0001, // b 0x100020
        0xE1A0_F00E, // mov pc, lr
        0xE1A0_F00E,
        0xE1A0_F00E,
    ]);
    let analysis = discover::analyze(&image, &discover::EntryHints::default());
    let func = analysis.functions.get(&0x0010_0000).expect("entry function");
    assert_eq!(func.switches.len(), 1);
    let sw = &func.switches[0];
    assert_eq!(sw.site, 0x0010_0004);
    assert_eq!(sw.table_addr, 0x0010_000C);
    assert_eq!(sw.cases, vec![(0, 0x0010_000C), (1, 0x0010_0010), (2, 0x0010_0014)]);
    for target in [0x0010_0018, 0x0010_001C, 0x0010_0020] {
        assert!(func.insns.contains_key(&target), "case target {target:08x} decoded");
    }
    assert!(analysis.unhandled.is_empty());
}

#[test]
fn switch_ldr_pc_table() {
    let image = synthetic(&[
        0xE350_0002, // cmp r0, #2
        0xE79F_F100, // ldr pc, [pc, r0, lsl #2]
        0xEA00_0004, // b 0x100020 (default)
        0x0010_0018, // table
        0x0010_001C,
        0x0010_0020,
        0xE1A0_F00E, // mov pc, lr
        0xE1A0_F00E,
        0xE1A0_F00E,
    ]);
    let analysis = discover::analyze(&image, &discover::EntryHints::default());
    let func = analysis.functions.get(&0x0010_0000).expect("entry function");
    assert_eq!(func.switches.len(), 1);
    let sw = &func.switches[0];
    assert_eq!(sw.site, 0x0010_0004);
    assert_eq!(sw.table_addr, 0x0010_000C);
    assert_eq!(sw.table, vec![0x0010_0018, 0x0010_001C, 0x0010_0020]);
    assert_eq!(sw.cases, vec![(0, 0x0010_0018), (1, 0x0010_001C), (2, 0x0010_0020)]);
    assert!(analysis.unhandled.is_empty());
}
