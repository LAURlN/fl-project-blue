//! Instruction representation shared by the A32 and T16 decoders.
//!
//! This IR is intentionally explicit rather than a generic "opcode + operands"
//! form: the emitter can match every variant without re-decoding bit fields,
//! and the discovery pass can ask precise questions about control flow.
//!
//! The IR intentionally covers more of ARMv6K than the current emitter uses;
//! unused variants are kept so decoding and diagnostics stay complete.
#![allow(dead_code)]

/// Guest program counter register index.
pub const PC: u8 = 15;
/// Guest link register index.
pub const LR: u8 = 14;
/// Guest stack pointer index.
pub const SP: u8 = 13;

#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub enum Mode {
    Arm,
    Thumb,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Cond {
    Eq,
    Ne,
    Cs,
    Cc,
    Mi,
    Pl,
    Vs,
    Vc,
    Hi,
    Ls,
    Ge,
    Lt,
    Gt,
    Le,
    Al,
    Nv,
}

impl Cond {
    pub fn from_bits(bits: u32) -> Cond {
        match bits & 0xF {
            0x0 => Cond::Eq,
            0x1 => Cond::Ne,
            0x2 => Cond::Cs,
            0x3 => Cond::Cc,
            0x4 => Cond::Mi,
            0x5 => Cond::Pl,
            0x6 => Cond::Vs,
            0x7 => Cond::Vc,
            0x8 => Cond::Hi,
            0x9 => Cond::Ls,
            0xA => Cond::Ge,
            0xB => Cond::Lt,
            0xC => Cond::Gt,
            0xD => Cond::Le,
            0xE => Cond::Al,
            _ => Cond::Nv,
        }
    }

    pub fn is_al(self) -> bool {
        matches!(self, Cond::Al)
    }

    /// C expression evaluating the condition against the Ctx flag fields.
    /// `None` means the instruction is unconditional.
    pub fn c_expr(self) -> Option<&'static str> {
        Some(match self {
            Cond::Eq => "ctx->z",
            Cond::Ne => "!ctx->z",
            Cond::Cs => "ctx->c",
            Cond::Cc => "!ctx->c",
            Cond::Mi => "ctx->n",
            Cond::Pl => "!ctx->n",
            Cond::Vs => "ctx->v",
            Cond::Vc => "!ctx->v",
            Cond::Hi => "ctx->c && !ctx->z",
            Cond::Ls => "!ctx->c || ctx->z",
            Cond::Ge => "ctx->n == ctx->v",
            Cond::Lt => "ctx->n != ctx->v",
            Cond::Gt => "!ctx->z && ctx->n == ctx->v",
            Cond::Le => "ctx->z || ctx->n != ctx->v",
            Cond::Al => return None,
            Cond::Nv => "0",
        })
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ShiftKind {
    Lsl,
    Lsr,
    Asr,
    Ror,
    Rrx,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ShiftAmount {
    Imm(u8),
    Reg(u8),
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Shift {
    pub kind: ShiftKind,
    pub amount: ShiftAmount,
}

impl Shift {
    pub const NONE: Shift = Shift { kind: ShiftKind::Lsl, amount: ShiftAmount::Imm(0) };

    pub fn is_none(self) -> bool {
        self.kind == ShiftKind::Lsl && self.amount == ShiftAmount::Imm(0)
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Operand2 {
    Imm(u32),
    Reg { rm: u8, shift: Shift },
}

impl Operand2 {
    pub fn reg(rm: u8) -> Operand2 {
        Operand2::Reg { rm, shift: Shift::NONE }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum DpOp {
    And,
    Eor,
    Sub,
    Rsb,
    Add,
    Adc,
    Sbc,
    Rsc,
    Tst,
    Teq,
    Cmp,
    Cmn,
    Orr,
    Mov,
    Bic,
    Mvn,
}

impl DpOp {
    pub fn from_bits(bits: u32) -> DpOp {
        match bits & 0xF {
            0x0 => DpOp::And,
            0x1 => DpOp::Eor,
            0x2 => DpOp::Sub,
            0x3 => DpOp::Rsb,
            0x4 => DpOp::Add,
            0x5 => DpOp::Adc,
            0x6 => DpOp::Sbc,
            0x7 => DpOp::Rsc,
            0x8 => DpOp::Tst,
            0x9 => DpOp::Teq,
            0xA => DpOp::Cmp,
            0xB => DpOp::Cmn,
            0xC => DpOp::Orr,
            0xD => DpOp::Mov,
            0xE => DpOp::Bic,
            _ => DpOp::Mvn,
        }
    }

    pub fn is_test(self) -> bool {
        matches!(self, DpOp::Tst | DpOp::Teq | DpOp::Cmp | DpOp::Cmn)
    }

    pub fn is_unary(self) -> bool {
        matches!(self, DpOp::Mov | DpOp::Mvn)
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum MemKind {
    Ldr,
    Str,
    LdrB,
    StrB,
    LdrH,
    StrH,
    LdrSb,
    LdrSh,
    LdrD,
    StrD,
}

impl MemKind {
    pub fn is_load(self) -> bool {
        !matches!(self, MemKind::Str | MemKind::StrB | MemKind::StrH | MemKind::StrD)
    }

    pub fn is_double(self) -> bool {
        matches!(self, MemKind::LdrD | MemKind::StrD)
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum MemOffset {
    Imm(u32),
    Reg { rm: u8, shift: Shift },
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Mem {
    pub kind: MemKind,
    pub rd: u8,
    pub rn: u8,
    pub offset: MemOffset,
    pub add: bool,
    pub pre_index: bool,
    pub writeback: bool,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Block {
    pub load: bool,
    pub rn: u8,
    pub regs: u16,
    pub add: bool,
    pub before: bool,
    pub writeback: bool,
    /// LDM/STM user-mode bank transfer. Not modelled by the runtime Ctx.
    pub user: bool,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum RevKind {
    Rev,
    Rev16,
    RevSh,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum QAddOp {
    Qadd,
    Qsub,
    Qdadd,
    Qdsub,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ParallelOp {
    Add16,
    Asx,
    Sax,
    Sub16,
    Add8,
    Sub8,
}

impl ParallelOp {
    pub fn from_bits(bits: u32) -> Option<ParallelOp> {
        Some(match bits & 7 {
            0 => ParallelOp::Add16,
            1 => ParallelOp::Asx,
            2 => ParallelOp::Sax,
            3 => ParallelOp::Sub16,
            4 => ParallelOp::Add8,
            7 => ParallelOp::Sub8,
            _ => return None,
        })
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ExtWidth {
    B,
    H,
    B16,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ExSize {
    B,
    H,
    W,
    D,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum VfpSize {
    Single,
    Double,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum VfpOp {
    Add {
        size: VfpSize,
        vd: u8,
        vn: u8,
        vm: u8,
    },
    Sub {
        size: VfpSize,
        vd: u8,
        vn: u8,
        vm: u8,
    },
    Mul {
        size: VfpSize,
        vd: u8,
        vn: u8,
        vm: u8,
        negate: bool,
    },
    Div {
        size: VfpSize,
        vd: u8,
        vn: u8,
        vm: u8,
    },
    Mla {
        size: VfpSize,
        vd: u8,
        vn: u8,
        vm: u8,
        subtract: bool,
        negate: bool,
    },
    MovReg {
        size: VfpSize,
        vd: u8,
        vm: u8,
    },
    Abs {
        size: VfpSize,
        vd: u8,
        vm: u8,
    },
    Neg {
        size: VfpSize,
        vd: u8,
        vm: u8,
    },
    Sqrt {
        size: VfpSize,
        vd: u8,
        vm: u8,
    },
    Cmp {
        size: VfpSize,
        vd: u8,
        vm: u8,
        with_zero: bool,
    },
    CvtSingleDouble {
        to_single: bool,
        vd: u8,
        vm: u8,
    },
    CvtFloatToInt {
        size: VfpSize,
        unsigned: bool,
        round_zero: bool,
        vd: u8,
        vm: u8,
    },
    CvtIntToFloat {
        size: VfpSize,
        unsigned: bool,
        vd: u8,
        vm: u8,
    },
    CvtFixed {
        size: VfpSize,
        to_fixed: bool,
        unsigned: bool,
        wide: bool,
        frac_bits: u8,
        vd: u8,
    },
    Mem {
        load: bool,
        size: VfpSize,
        vd: u8,
        rn: u8,
        offset: u32,
        add: bool,
        pre_index: bool,
        writeback: bool,
    },
    MemMulti {
        load: bool,
        size: VfpSize,
        vd: u8,
        rn: u8,
        count: u8,
        add: bool,
        pre_index: bool,
        writeback: bool,
    },
    /// VMOV Sn, Rt (core register to VFP single).
    FromCore { sn: u8, rt: u8 },
    /// VMOV Rt, Sn (VFP single to core register).
    ToCore { sn: u8, rt: u8 },
    /// VMOV Dm, Rt, Rt2.
    FromTwoCore { dm: u8, rt: u8, rt2: u8 },
    /// VMOV Rt, Rt2, Dm.
    ToTwoCore { dm: u8, rt: u8, rt2: u8 },
    Vmrs { rt: u8 },
    Vmsr { rt: u8 },
    MovImm {
        size: VfpSize,
        vd: u8,
        imm8: u8,
    },
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Op {
    Dp {
        op: DpOp,
        rd: u8,
        rn: u8,
        op2: Operand2,
        set_flags: bool,
    },
    Mul {
        rd: u8,
        ra: u8,
        rm: u8,
        rs: u8,
        accumulate: bool,
        set_flags: bool,
    },
    MulLong {
        signed: bool,
        accumulate: bool,
        set_flags: bool,
        rd_lo: u8,
        rd_hi: u8,
        rm: u8,
        rs: u8,
    },
    HalfMul {
        accumulate: bool,
        rd: u8,
        rn: u8,
        rm: u8,
        rs: u8,
        x: bool,
        y: bool,
    },
    WordHalfMul {
        accumulate: bool,
        top: bool,
        rd: u8,
        rn: u8,
        rm: u8,
        rs: u8,
    },
    HalfMulLong {
        rd_lo: u8,
        rd_hi: u8,
        rm: u8,
        rs: u8,
        x: bool,
        y: bool,
    },
    DualMul {
        subtract: bool,
        exchange: bool,
        accumulate: bool,
        rd: u8,
        ra: u8,
        rn: u8,
        rm: u8,
    },
    DualMulLong {
        subtract: bool,
        exchange: bool,
        rd_lo: u8,
        rd_hi: u8,
        rn: u8,
        rm: u8,
    },
    Usad {
        accumulate: bool,
        rd: u8,
        ra: u8,
        rn: u8,
        rm: u8,
    },
    Pkh {
        tb: bool,
        rd: u8,
        rn: u8,
        rm: u8,
        shift: u8,
    },
    Sel {
        rd: u8,
        rn: u8,
        rm: u8,
    },
    Sat {
        signed: bool,
        rd: u8,
        rn: u8,
        imm: u8,
        shift: Shift,
    },
    Sat16 {
        signed: bool,
        rd: u8,
        rn: u8,
        imm: u8,
    },
    Rev {
        kind: RevKind,
        rd: u8,
        rm: u8,
    },
    Clz {
        rd: u8,
        rm: u8,
    },
    QAdd {
        op: QAddOp,
        rd: u8,
        rm: u8,
        rn: u8,
    },
    Parallel {
        signed: bool,
        saturating: bool,
        halving: bool,
        op: ParallelOp,
        rd: u8,
        rn: u8,
        rm: u8,
    },
    Extend {
        signed: bool,
        width: ExtWidth,
        rd: u8,
        rn: u8,
        rm: Option<u8>,
        rotate: u8,
    },
    B {
        target: u32,
        link: bool,
        exchange: bool,
    },
    Bx {
        rm: u8,
        link: bool,
        j: bool,
    },
    Mem(Mem),
    Block(Block),
    Swp {
        byte: bool,
        rd: u8,
        rm: u8,
        rn: u8,
    },
    Ldrex {
        size: ExSize,
        rd: u8,
        rn: u8,
    },
    Strex {
        size: ExSize,
        rd: u8,
        rm: u8,
        rn: u8,
    },
    Ldrexd {
        rd: u8,
        rn: u8,
    },
    Strexd {
        rd: u8,
        rm: u8,
        rn: u8,
    },
    Clrex,
    Mrs {
        rd: u8,
        spsr: bool,
    },
    /// MRC p15, 0, Rd, c13, c0, 3: thread-local storage pointer.
    TlsRead {
        rd: u8,
    },
    Msr {
        rn: u8,
        mask: u8,
        spsr: bool,
    },
    Cps {
        imod: u32,
        aif: u32,
        mode: u32,
    },
    Setend {
        big: bool,
    },
    Svc {
        imm: u32,
    },
    Bkpt {
        imm: u32,
    },
    Pld {
        rn: u8,
        offset: MemOffset,
        add: bool,
    },
    Barrier,
    Nop,
    Vfp(VfpOp),
    Coproc {
        raw: u32,
    },
    Unhandled {
        what: &'static str,
    },
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Insn {
    pub addr: u32,
    pub size: u8,
    pub cond: Cond,
    pub op: Op,
    /// Original encoding word (A32) or `first_halfword << 16 | second_halfword`.
    pub raw: u32,
}

impl Insn {
    pub fn is_terminator(&self) -> bool {
        match self.op {
            Op::B { .. } => true,
            Op::Bx { .. } => true,
            Op::Svc { .. } => false,
            Op::Block(ref b) => !b.load || (b.regs & (1 << PC)) != 0,
            Op::Mem(ref m) => m.kind.is_load() && m.rd == PC,
            Op::Dp { rd: PC, .. } => true,
            Op::Vfp(_) => false,
            _ => false,
        }
    }
}
