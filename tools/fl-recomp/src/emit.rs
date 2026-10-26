//! C17 emitter.
//!
//! Every decoded guest instruction becomes portable C operating on `Ctx`.
//! Control flow is expressed with `goto` labels inside one C function per
//! guest function; direct calls use the generated lookup table and indirect
//! control flow goes through `recomp_call_indirect`.
//!
//! The output is split into bounded chunks so one huge `.c` file is never
//! produced. Only the caller's own extracted image is read; no generated code
//! is checked in.

use std::fmt::Write as _;
use std::io;
use std::path::Path;

use crate::discover::{Analysis, Function};
use crate::image::Image;
use crate::insn::*;

#[derive(Clone, Copy, Debug, Default)]
pub struct EmitStats {
    pub bytes: u64,
    pub files: usize,
}

const FUNCTIONS_PER_FILE: usize = 250;

fn fn_name(addr: u32) -> String {
    format!("fn_{addr:08x}")
}

fn label(addr: u32) -> String {
    format!("L_{addr:08x}")
}

fn hex(v: u32) -> String {
    format!("0x{v:08x}u")
}

fn is_unconditional(cond: Cond) -> bool {
    matches!(cond, Cond::Al | Cond::Nv)
}

fn pc_value(insn: &Insn, mode: Mode) -> u32 {
    match mode {
        Mode::Arm => insn.addr.wrapping_add(8),
        Mode::Thumb => insn.addr.wrapping_add(4) & !3,
    }
}

fn reg(insn: &Insn, mode: Mode, r: u8) -> String {
    if r == PC {
        hex(pc_value(insn, mode))
    } else {
        format!("ctx->r[{r}]")
    }
}

/// Guest register value for an operand that may read PC.
fn reg_read(insn: &Insn, mode: Mode, r: u8) -> String {
    reg(insn, mode, r)
}

struct Emitter<'a> {
    out: String,
    func: &'a Function,
    analysis: &'a Analysis,
    polls: &'a [(u32, Mode)],
    uniq: u32,
}

impl<'a> Emitter<'a> {
    fn new(func: &'a Function, analysis: &'a Analysis, polls: &'a [(u32, Mode)]) -> Self {
        Emitter { out: String::new(), func, analysis, polls, uniq: 0 }
    }

    fn tag(&mut self, addr: u32) -> String {
        self.uniq += 1;
        format!("{addr:08x}_{}", self.uniq)
    }

    fn line(&mut self, text: &str) {
        let _ = writeln!(self.out, "    {text}");
    }

    fn fallthrough(&mut self, addr: u32, size: u8) {
        let next = addr + size as u32;
        if self.func.insns.contains_key(&next) {
            self.line(&format!("goto {};", label(next)));
        } else {
            self.line("return;");
        }
    }

    fn condition(&self, insn: &Insn) -> Option<&'static str> {
        if is_unconditional(insn.cond) {
            None
        } else {
            insn.cond.c_expr()
        }
    }

    fn guard<F: FnOnce(&mut Self)>(&mut self, insn: &Insn, body: F) {
        if let Some(cond) = self.condition(insn) {
            self.line(&format!("if ({cond}) {{"));
            body(self);
            self.line("}");
        } else {
            body(self);
        }
    }

    fn function_call(&mut self, target: u32) {
        if self.analysis.functions.contains_key(&target) {
            self.line(&format!("{}(ctx);", fn_name(target)));
        } else {
            self.line(&format!("recomp_call_indirect(ctx, {});", hex(target)));
        }
    }

    fn pc_write(&mut self, addr: u32, target: &str) {
        if std::env::var_os("FL_EMIT_DEBUG").is_some() && addr == 0x20cab8 {
            eprintln!(
                "pc_write {addr:08x} func {:08x} switches {:?}",
                self.func.entry,
                self.func.switches.iter().map(|s| (s.site, s.cases.len())).collect::<Vec<_>>()
            );
        }
        let Some(sw) = self.func.switches.iter().find(|s| s.site == addr) else {
            self.line(&format!("recomp_call_indirect(ctx, {target});"));
            self.line("return;");
            return;
        };
        // Evaluate once: the expression may read memory or registers.
        let t = format!("tgt_{}", self.tag(addr));
        self.line(&format!("uint32_t {t} = {target};"));
        self.line(&format!("switch ({t}) {{"));
        let mut seen = std::collections::BTreeSet::new();
        for &(_, case) in &sw.cases {
            if !seen.insert(case) {
                continue;
            }
            if self.func.insns.contains_key(&case) {
                self.line(&format!("case {}: goto {};", hex(case), label(case)));
            } else if self.analysis.functions.contains_key(&case) {
                self.line(&format!("case {}: {}(ctx); return;", hex(case), fn_name(case)));
            }
        }
        self.line("default:");
        self.line(&format!("    recomp_call_indirect(ctx, {t});"));
        self.line("    return;");
        self.line("}");
    }

    fn set_nz(&mut self, res: &str) {
        self.line(&format!("ctx->n = ({res}) >> 31;"));
        self.line(&format!("ctx->z = (({res}) == 0);"));
    }

    /// Emit a shifted operand into locals and return the value and optional
    /// carry-out variable names.
    fn shift_operand(
        &mut self,
        tag: &str,
        value: &str,
        shift: Shift,
        want_carry: bool,
    ) -> (String, Option<String>) {
        let v = format!("sv_{tag}");
        self.line(&format!("uint32_t {v} = {value};"));
        let carry = want_carry.then(|| format!("sc_{tag}"));
        if let Some(c) = &carry {
            self.line(&format!("uint32_t {c} = ctx->c;"));
        }
        match shift.amount {
            ShiftAmount::Imm(n) => match shift.kind {
                ShiftKind::Lsl if n == 0 => {}
                ShiftKind::Lsl => {
                    let n = n.min(31);
                    if let Some(c) = &carry {
                        self.line(&format!("{c} = ({v} >> {}) & 1u;", 32 - n));
                    }
                    self.line(&format!("{v} = {v} << {n};"));
                }
                ShiftKind::Lsr => {
                    // Immediate LSR/ASR #0 means #32 in the instructions that
                    // allow it (notably SSAT).
                    let n = if n == 0 { 32 } else { n as u32 };
                    if n >= 32 {
                        if let Some(c) = &carry {
                            self.line(&format!("{c} = {v} >> 31;"));
                        }
                        self.line(&format!("{v} = 0u;"));
                    } else {
                        if let Some(c) = &carry {
                            self.line(&format!("{c} = ({v} >> {}) & 1u;", n - 1));
                        }
                        self.line(&format!("{v} = {v} >> {n};"));
                    }
                }
                ShiftKind::Asr => {
                    let n = if n == 0 { 32 } else { n as u32 };
                    if n >= 32 {
                        if let Some(c) = &carry {
                            self.line(&format!("{c} = {v} >> 31;"));
                        }
                        self.line(&format!("{v} = (uint32_t)((int32_t){v} >> 31);"));
                    } else {
                        if let Some(c) = &carry {
                            self.line(&format!("{c} = ({v} >> {}) & 1u;", n - 1));
                        }
                        self.line(&format!("{v} = (uint32_t)((int32_t){v} >> {n});"));
                    }
                }
                ShiftKind::Ror if n == 0 => {
                    if let Some(c) = &carry {
                        self.line(&format!("{c} = {v} >> 31;"));
                    }
                    self.line(&format!("{v} = ({v} >> 1) | (ctx->c << 31);"));
                }
                ShiftKind::Ror => {
                    let n = n & 31;
                    if n == 0 {
                        if let Some(c) = &carry {
                            self.line(&format!("{c} = {v} >> 31;"));
                        }
                    } else {
                        self.line(&format!("{v} = ({v} >> {n}) | ({v} << {});", 32 - n));
                        if let Some(c) = &carry {
                            self.line(&format!("{c} = {v} >> 31;"));
                        }
                    }
                }
                ShiftKind::Rrx => {
                    if let Some(c) = &carry {
                        self.line(&format!("{c} = {v} & 1u;"));
                    }
                    self.line(&format!("{v} = ({v} >> 1) | (ctx->c << 31);"));
                }
            },
            ShiftAmount::Reg(r) => {
                let amt = format!("ctx->r[{r}]");
                let cptr = carry.as_ref().map(|c| format!("&{c}")).unwrap_or_else(|| "0".to_string());
                match shift.kind {
                    ShiftKind::Lsl => self.line(&format!("{v} = lsl_rc({v}, {amt}, {cptr});")),
                    ShiftKind::Lsr => self.line(&format!("{v} = lsr_rc({v}, {amt}, {cptr});")),
                    ShiftKind::Asr => self.line(&format!("{v} = asr_rc({v}, {amt}, {cptr});")),
                    _ => self.line(&format!("{v} = ror_rc({v}, {amt}, {cptr});")),
                }
            }
        }
        (v, carry)
    }

    fn operand2(&mut self, tag: &str, insn: &Insn, op2: Operand2, want_carry: bool) -> (String, Option<String>) {
        match op2 {
            Operand2::Imm(v) => {
                let name = format!("sv_{tag}");
                self.line(&format!("uint32_t {name} = {};", hex(v)));
                let carry = if want_carry {
                    // The ARM immediate rotator produces a carry only when the
                    // encoded value needed a rotation. Values that fit in eight
                    // bits leave C unchanged.
                    let c = format!("sc_{tag}");
                    if v > 0xFF {
                        self.line(&format!("uint32_t {c} = ({name} >> 31) & 1u;"));
                    } else {
                        self.line(&format!("uint32_t {c} = ctx->c;"));
                    }
                    Some(c)
                } else {
                    None
                };
                (name, carry)
            }
            Operand2::Reg { rm, shift } => {
                let value = reg_read(insn, self.func.mode, rm);
                self.shift_operand(tag, &value, shift, want_carry)
            }
        }
    }

    fn emit_dp(&mut self, insn: &Insn, op: DpOp, rd: u8, rn: u8, op2: Operand2, set_flags: bool, dest: Option<&str>) {
        let tag = self.tag(insn.addr);
        let need_carry = set_flags && matches!(op, DpOp::And | DpOp::Eor | DpOp::Tst | DpOp::Teq | DpOp::Orr | DpOp::Mov | DpOp::Bic | DpOp::Mvn);
        let (b, shcarry) = self.operand2(&tag, insn, op2, need_carry);
        let a = format!("ra_{tag}");
        self.line(&format!("uint32_t {a} = {};", reg_read(insn, self.func.mode, rn)));
        let res = format!("rr_{tag}");
        let target = dest.map(str::to_string).unwrap_or_else(|| format!("ctx->r[{rd}]"));

        match op {
            DpOp::And | DpOp::Eor | DpOp::Orr | DpOp::Bic => {
                self.line(&format!("uint32_t {res} = {a} {} {b};", match op {
                    DpOp::And => "&",
                    DpOp::Eor => "^",
                    DpOp::Orr => "|",
                    _ => "& ~",
                }));
                if set_flags {
                    self.set_nz(&res);
                    let c = shcarry.unwrap_or_else(|| "ctx->c".to_string());
                    self.line(&format!("ctx->c = {c};"));
                }
                self.line(&format!("{target} = {res};"));
            }
            DpOp::Mov | DpOp::Mvn => {
                let neg = if op == DpOp::Mvn { "~" } else { "" };
                self.line(&format!("uint32_t {res} = {neg}{b};"));
                if set_flags {
                    self.set_nz(&res);
                    let c = shcarry.unwrap_or_else(|| "ctx->c".to_string());
                    self.line(&format!("ctx->c = {c};"));
                }
                self.line(&format!("{target} = {res};"));
            }
            DpOp::Add | DpOp::Adc | DpOp::Sub | DpOp::Sbc | DpOp::Rsb | DpOp::Rsc => {
                let cin = match op {
                    DpOp::Adc => "ctx->c".to_string(),
                    DpOp::Sbc | DpOp::Rsc => "ctx->c".to_string(),
                    // Subtraction adds the one's complement plus one; the
                    // carry-out is then "no borrow" as ARM requires.
                    DpOp::Sub | DpOp::Rsb => "1u".to_string(),
                    _ => "0u".to_string(),
                };
                let (x, y) = match op {
                    DpOp::Sub | DpOp::Sbc | DpOp::Cmp => (format!("{a}"), format!("~{b}")),
                    DpOp::Rsb | DpOp::Rsc => (format!("{b}"), format!("~{a}")),
                    _ => (format!("{a}"), format!("{b}")),
                };
                let cvar = format!("cf_{tag}");
                let vvar = format!("vf_{tag}");
                self.line(&format!("uint32_t {cvar} = 0, {vvar} = 0;"));
                self.line(&format!(
                    "uint32_t {res} = add_cv({x}, {y}, {cin}, &{cvar}, &{vvar});"
                ));
                if set_flags {
                    self.set_nz(&res);
                    self.line(&format!("ctx->c = {cvar};"));
                    self.line(&format!("ctx->v = {vvar};"));
                }
                self.line(&format!("{target} = {res};"));
            }
            DpOp::Tst | DpOp::Teq => {
                let decl = match op {
                    DpOp::Tst => format!("uint32_t {res} = {a} & {b};"),
                    _ => format!("uint32_t {res} = {a} ^ {b};"),
                };
                self.line(&decl);
                self.set_nz(&res);
                let c = shcarry.unwrap_or_else(|| "ctx->c".to_string());
                self.line(&format!("ctx->c = {c};"));
            }
            DpOp::Cmp | DpOp::Cmn => {
                let cvar = format!("cf_{tag}");
                let vvar = format!("vf_{tag}");
                let (x, y) = if op == DpOp::Cmp {
                    (format!("{a}"), format!("~{b}"))
                } else {
                    (format!("{a}"), format!("{b}"))
                };
                let cin = if op == DpOp::Cmp { "1u" } else { "0u" };
                self.line(&format!("uint32_t {cvar} = 0, {vvar} = 0;"));
                self.line(&format!(
                    "uint32_t {res} = add_cv({x}, {y}, {cin}, &{cvar}, &{vvar});"
                ));
                self.set_nz(&res);
                self.line(&format!("ctx->c = {cvar};"));
                self.line(&format!("ctx->v = {vvar};"));
            }
        }
    }

    fn emit_mem(&mut self, insn: &Insn, m: Mem) {
        let tag = self.tag(insn.addr);
        let rn = if m.rn == PC {
            hex(pc_value(insn, self.func.mode))
        } else {
            format!("ctx->r[{}]", m.rn)
        };
        let base = format!("ba_{tag}");
        self.line(&format!("uint32_t {base} = {rn};"));
        let off = match m.offset {
            MemOffset::Imm(v) => format!("{}u", v),
            MemOffset::Reg { rm, shift } => {
                let value = reg_read(insn, self.func.mode, rm);
                let (sv, _) = self.shift_operand(&format!("{tag}_off"), &value, shift, false);
                sv
            }
        };
        let addr = format!("ad_{tag}");
        let op = if m.add { "+" } else { "-" };
        self.line(&format!("uint32_t {addr} = {base} {op} {off};"));
        let ea = if m.pre_index {
            addr.clone()
        } else {
            base.clone()
        };
        let mut pc_load: Option<String> = None;

        if m.kind.is_double() {
            let lo = format!("lo_{tag}");
            let hi = format!("hi_{tag}");
            if m.kind == MemKind::LdrD {
                self.line(&format!("uint32_t {lo} = rd32({ea});"));
                self.line(&format!("uint32_t {hi} = rd32({ea} + 4);"));
                for (i, r) in [m.rd, m.rd.wrapping_add(1)].into_iter().enumerate() {
                    if r < 16 && r != PC {
                        self.line(&format!("ctx->r[{r}] = {};", if i == 0 { &lo } else { &hi }));
                    }
                }
            } else {
                for (i, r) in [m.rd, m.rd.wrapping_add(1)].into_iter().enumerate() {
                    let value = if r == PC { hex(pc_value(insn, self.func.mode)) } else { format!("ctx->r[{r}]") };
                    self.line(&format!("wr32({ea} + {}, {value});", i * 4));
                }
            }
        } else {
            match m.kind {
                MemKind::Ldr => {
                    let v = format!("ld_{tag}");
                    self.line(&format!("uint32_t {v} = rd32({ea});"));
                    if m.rd == PC {
                        pc_load = Some(v);
                    } else {
                        self.line(&format!("ctx->r[{}] = {v};", m.rd));
                    }
                }
                MemKind::Str => {
                    let v = if m.rd == PC { hex(pc_value(insn, self.func.mode)) } else { format!("ctx->r[{}]", m.rd) };
                    self.line(&format!("wr32({ea}, {v});"));
                }
                MemKind::LdrB => {
                    let v = format!("ld_{tag}");
                    self.line(&format!("uint32_t {v} = rd8({ea});"));
                    self.line(&format!("ctx->r[{}] = {v};", m.rd));
                }
                MemKind::StrB => {
                    let v = format!("ctx->r[{}]", m.rd);
                    self.line(&format!("wr8({ea}, {v});"));
                }
                MemKind::LdrH => {
                    let v = format!("ld_{tag}");
                    self.line(&format!("uint32_t {v} = rd16({ea});"));
                    self.line(&format!("ctx->r[{}] = {v};", m.rd));
                }
                MemKind::StrH => {
                    let v = format!("ctx->r[{}]", m.rd);
                    self.line(&format!("wr16({ea}, {v});"));
                }
                MemKind::LdrSb => {
                    let v = format!("ld_{tag}");
                    self.line(&format!("uint32_t {v} = rds8({ea});"));
                    self.line(&format!("ctx->r[{}] = {v};", m.rd));
                }
                MemKind::LdrSh => {
                    let v = format!("ld_{tag}");
                    self.line(&format!("uint32_t {v} = rds16({ea});"));
                    self.line(&format!("ctx->r[{}] = {v};", m.rd));
                }
                MemKind::LdrD | MemKind::StrD => unreachable!(),
            }
        }

        if m.writeback {
            let delta = match m.offset {
                MemOffset::Imm(v) => format!("{}u", v),
                MemOffset::Reg { .. } => off.clone(),
            };
            let op = if m.add { "+" } else { "-" };
            self.line(&format!("ctx->r[{}] = {base} {op} {delta};", m.rn));
        }
        if let Some(v) = pc_load {
            self.pc_write(insn.addr, &v);
        }
    }

    fn emit_block(&mut self, insn: &Insn, b: Block) {
        let tag = self.tag(insn.addr);
        let count = b.regs.count_ones();
        let base = format!("ba_{tag}");
        self.line(&format!("uint32_t {base} = ctx->r[{}];", b.rn));
        let step = 4u32;
        let start = format!("st_{tag}");
        if b.add {
            if b.before {
                self.line(&format!("uint32_t {start} = {base} + {step};"));
            } else {
                self.line(&format!("uint32_t {start} = {base};"));
            }
        } else if count > 0 {
            if b.before {
                self.line(&format!("uint32_t {start} = {base} - {}u;", count * step));
            } else {
                self.line(&format!("uint32_t {start} = {base} - {}u;", (count - 1) * step));
            }
        } else {
            self.line(&format!("uint32_t {start} = {base};"));
        }

        let mut index = 0u32;
        let mut pc_load: Option<String> = None;
        for r in 0..16u8 {
            if b.regs & (1 << r) == 0 {
                continue;
            }
            let ea = format!("{start} + {}u", index * step);
            if b.load {
                if r == PC {
                    let v = format!("pcv_{tag}");
                    self.line(&format!("uint32_t {v} = rd32({ea});"));
                    pc_load = Some(v);
                } else {
                    self.line(&format!("ctx->r[{r}] = rd32({ea});"));
                }
            } else {
                let value = if r == PC { hex(pc_value(insn, self.func.mode)) } else { format!("ctx->r[{r}]") };
                self.line(&format!("wr32({ea}, {value});"));
            }
            index += 1;
        }

        if b.writeback && b.rn != PC {
            if b.add {
                self.line(&format!("ctx->r[{}] = {base} + {}u;", b.rn, count * step));
            } else {
                self.line(&format!("ctx->r[{}] = {base} - {}u;", b.rn, count * step));
            }
        }
        if let Some(v) = pc_load {
            self.pc_write(insn.addr, &v);
        }
    }

    fn emit_vfp_mem(&mut self, insn: &Insn, load: bool, size: VfpSize, vd: u8, rn: u8, offset: u32, add: bool, pre: bool, wb: bool) {
        let tag = self.tag(insn.addr);
        let base = format!("vb_{tag}");
        let rn_expr = if rn == PC { hex(pc_value(insn, self.func.mode)) } else { format!("ctx->r[{rn}]") };
        self.line(&format!("uint32_t {base} = {rn_expr};"));
        let ea = format!("va_{tag}");
        let op = if add { "+" } else { "-" };
        let step = match size { VfpSize::Single => 4, VfpSize::Double => 8 };
        if pre {
            self.line(&format!("uint32_t {ea} = {base} {op} {}u;", offset));
        } else {
            self.line(&format!("uint32_t {ea} = {base};"));
        }
        if load {
            match size {
                VfpSize::Single => {
                    self.line(&format!("{{ uint32_t u_{tag} = rd32({ea}); memcpy(&ctx->s[{vd}], &u_{tag}, 4); }}"));
                }
                VfpSize::Double => {
                    self.line(&format!("{{ uint64_t u_{tag}; memcpy(&u_{tag}, recomp_mem + {ea}, 8); ctx->s[{}] = (uint32_t)u_{tag}; ctx->s[{}] = (uint32_t)(u_{tag} >> 32); }}", 2 * vd, 2 * vd + 1));
                }
            }
        } else {
            match size {
                VfpSize::Single => {
                    self.line(&format!("{{ uint32_t u_{tag}; memcpy(&u_{tag}, &ctx->s[{vd}], 4); wr32({ea}, u_{tag}); }}"));
                }
                VfpSize::Double => {
                    self.line(&format!("{{ uint64_t u_{tag} = (uint64_t)ctx->s[{}] | ((uint64_t)ctx->s[{}] << 32); memcpy(recomp_mem + {ea}, &u_{tag}, 8); }}", 2 * vd, 2 * vd + 1));
                }
            }
        }
        if wb {
            self.line(&format!("ctx->r[{rn}] = {base} {op} {}u;", offset));
        }
        let _ = step;
    }

    fn emit_vfp_multimem(&mut self, insn: &Insn, load: bool, size: VfpSize, vd: u8, rn: u8, count: u8, add: bool, pre: bool, wb: bool) {
        let tag = self.tag(insn.addr);
        let base = format!("vb_{tag}");
        self.line(&format!("uint32_t {base} = ctx->r[{rn}];"));
        let step = match size { VfpSize::Single => 4u32, VfpSize::Double => 8u32 };
        let start = format!("vs_{tag}");
        if add {
            if pre {
                self.line(&format!("uint32_t {start} = {base} + {step};"));
            } else {
                self.line(&format!("uint32_t {start} = {base};"));
            }
        } else if count > 0 {
            if pre {
                self.line(&format!("uint32_t {start} = {base} - {}u;", count as u32 * step));
            } else {
                self.line(&format!("uint32_t {start} = {base} - {}u;", (count as u32).saturating_sub(1) * step));
            }
        } else {
            self.line(&format!("uint32_t {start} = {base};"));
        }
        for i in 0..count as u32 {
            let ea = format!("{start} + {}u", i * step);
            let vr = (vd as u32 + i) as u8;
            if load {
                match size {
                    VfpSize::Single => self.line(&format!("{{ uint32_t u_{tag}_{i} = rd32({ea}); memcpy(&ctx->s[{vr}], &u_{tag}_{i}, 4); }}")),
                    VfpSize::Double => self.line(&format!("{{ uint64_t u_{tag}_{i}; memcpy(&u_{tag}_{i}, recomp_mem + {ea}, 8); ctx->s[{}] = (uint32_t)u_{tag}_{i}; ctx->s[{}] = (uint32_t)(u_{tag}_{i} >> 32); }}", 2 * vr, 2 * vr + 1)),
                }
            } else {
                match size {
                    VfpSize::Single => self.line(&format!("{{ uint32_t u_{tag}_{i}; memcpy(&u_{tag}_{i}, &ctx->s[{vr}], 4); wr32({ea}, u_{tag}_{i}); }}")),
                    VfpSize::Double => self.line(&format!("{{ uint64_t u_{tag}_{i} = (uint64_t)ctx->s[{}] | ((uint64_t)ctx->s[{}] << 32); memcpy(recomp_mem + {ea}, &u_{tag}_{i}, 8); }}", 2 * vr, 2 * vr + 1)),
                }
            }
        }
        if wb {
            let delta = count as u32 * step;
            let op = if add { "+" } else { "-" };
            self.line(&format!("ctx->r[{rn}] = {base} {op} {delta}u;"));
        }
    }

    fn emit_vfp(&mut self, insn: &Insn, v: VfpOp) {
        let tag = self.tag(insn.addr);
        match v {
            VfpOp::Add { size, vd, vn, vm } | VfpOp::Sub { size, vd, vn, vm } | VfpOp::Div { size, vd, vn, vm } => {
                let op = match v {
                    VfpOp::Add { .. } => "+",
                    VfpOp::Sub { .. } => "-",
                    _ => "/",
                };
                match size {
                    VfpSize::Single => self.line(&format!("set_f32(ctx, {vd}, get_f32(ctx, {vn}) {op} get_f32(ctx, {vm}));")),
                    VfpSize::Double => self.line(&format!("set_f64(ctx, {vd}, get_f64(ctx, {vn}) {op} get_f64(ctx, {vm}));")),
                }
            }
            VfpOp::Mul { size, vd, vn, vm, negate } => {
                let neg = if negate { "-" } else { "" };
                match size {
                    VfpSize::Single => self.line(&format!("set_f32(ctx, {vd}, {neg}(get_f32(ctx, {vn}) * get_f32(ctx, {vm})));")),
                    VfpSize::Double => self.line(&format!("set_f64(ctx, {vd}, {neg}(get_f64(ctx, {vn}) * get_f64(ctx, {vm})));")),
                }
            }
            VfpOp::Mla { size, vd, vn, vm, subtract, negate } => {
                // ARM ARM: VMLA Fd=Fd+p, VMLS Fd=Fd-p, VNMLA Fd=-Fd-p,
                // VNMLS Fd=-Fd+p. The negation applies to the accumulator, not
                // to the combined result.
                match size {
                    VfpSize::Single => {
                        self.line(&format!(
                            "{{ float p_{tag} = get_f32(ctx, {vn}) * get_f32(ctx, {vm}); float r_{tag} = {}get_f32(ctx, {vd}) {} p_{tag}; set_f32(ctx, {vd}, r_{tag}); }}",
                            if negate { "-" } else { "" },
                            if subtract { "-" } else { "+" },
                        ));
                    }
                    VfpSize::Double => {
                        self.line(&format!(
                            "{{ double p_{tag} = get_f64(ctx, {vn}) * get_f64(ctx, {vm}); double r_{tag} = {}get_f64(ctx, {vd}) {} p_{tag}; set_f64(ctx, {vd}, r_{tag}); }}",
                            if negate { "-" } else { "" },
                            if subtract { "-" } else { "+" },
                        ));
                    }
                }
            }
            VfpOp::MovReg { size, vd, vm } => match size {
                VfpSize::Single => self.line(&format!("set_f32(ctx, {vd}, get_f32(ctx, {vm}));")),
                VfpSize::Double => self.line(&format!("set_f64(ctx, {vd}, get_f64(ctx, {vm}));")),
            },
            VfpOp::Abs { size, vd, vm } => match size {
                VfpSize::Single => self.line(&format!("set_f32(ctx, {vd}, fabsf(get_f32(ctx, {vm})));")),
                VfpSize::Double => self.line(&format!("set_f64(ctx, {vd}, fabs(get_f64(ctx, {vm})));")),
            },
            VfpOp::Neg { size, vd, vm } => match size {
                VfpSize::Single => self.line(&format!("set_f32(ctx, {vd}, -get_f32(ctx, {vm}));")),
                VfpSize::Double => self.line(&format!("set_f64(ctx, {vd}, -get_f64(ctx, {vm}));")),
            },
            VfpOp::Sqrt { size, vd, vm } => match size {
                VfpSize::Single => self.line(&format!("set_f32(ctx, {vd}, sqrtf(get_f32(ctx, {vm})));")),
                VfpSize::Double => self.line(&format!("set_f64(ctx, {vd}, sqrt(get_f64(ctx, {vm})));")),
            },
            VfpOp::Cmp { size, vd, vm, with_zero } => {
                let rhs = if with_zero { "0.0".to_string() } else {
                    match size { VfpSize::Single => format!("(double)get_f32(ctx, {vm})"), VfpSize::Double => format!("get_f64(ctx, {vm})") }
                };
                let lhs = match size { VfpSize::Single => format!("(double)get_f32(ctx, {vd})"), VfpSize::Double => format!("get_f64(ctx, {vd})") };
                self.line(&format!("vfp_cmp(ctx, {lhs}, {rhs});"));
            }
            VfpOp::CvtSingleDouble { to_single, vd, vm } => {
                if to_single {
                    self.line(&format!("set_f32(ctx, {vd}, (float)get_f64(ctx, {vm}));"));
                } else {
                    self.line(&format!("set_f64(ctx, {vd}, (double)get_f32(ctx, {vm}));"));
                }
            }
            // VCVT between floating point and integer keeps both operands in
            // the VFP register file: the integer result/source is the raw bit
            // pattern of a *single-precision* register, never an ARM core
            // register. The decoder stores that register number in `vd`/`vm`.
            VfpOp::CvtFloatToInt { size, unsigned, round_zero, vd, vm } => {
                let src = match size { VfpSize::Single => format!("(double)get_f32(ctx, {vm})"), VfpSize::Double => format!("get_f64(ctx, {vm})") };
                let fun = if unsigned { "vfp_to_u32" } else { "vfp_to_s32" };
                self.line(&format!("ctx->s[{vd}] = {fun}({src}, {});", if round_zero { 1 } else { 0 }));
            }
            VfpOp::CvtIntToFloat { size, unsigned, vd, vm } => {
                let src = if unsigned { format!("(double)(uint32_t)ctx->s[{vm}]") } else { format!("(double)(int32_t)ctx->s[{vm}]") };
                match size {
                    VfpSize::Single => self.line(&format!("set_f32(ctx, {vd}, (float){src});")),
                    VfpSize::Double => self.line(&format!("set_f64(ctx, {vd}, {src});")),
                }
            }
            VfpOp::CvtFixed { .. } => self.line("recomp_unhandled(ctx, 0, \"VFP fixed-point conversion\");"),
            VfpOp::Mem { load, size, vd, rn, offset, add, pre_index, writeback } => {
                self.emit_vfp_mem(insn, load, size, vd, rn, offset, add, pre_index, writeback);
            }
            VfpOp::MemMulti { load, size, vd, rn, count, add, pre_index, writeback } => {
                self.emit_vfp_multimem(insn, load, size, vd, rn, count, add, pre_index, writeback);
            }
            VfpOp::FromCore { sn, rt } => {
                self.line(&format!("ctx->s[{sn}] = ctx->r[{rt}];"));
            }
            VfpOp::ToCore { sn, rt } => {
                self.line(&format!("ctx->r[{rt}] = ctx->s[{sn}];"));
            }
            VfpOp::FromTwoCore { dm, rt, rt2 } => {
                self.line(&format!("set_f64(ctx, {dm}, 0.0);"));
                self.line(&format!("ctx->s[{}] = ctx->r[{rt}];", 2 * dm));
                self.line(&format!("ctx->s[{}] = ctx->r[{rt2}];", 2 * dm + 1));
            }
            VfpOp::ToTwoCore { dm, rt, rt2 } => {
                self.line(&format!("ctx->r[{rt}] = ctx->s[{}];", 2 * dm));
                self.line(&format!("ctx->r[{rt2}] = ctx->s[{}];", 2 * dm + 1));
            }
            VfpOp::Vmrs { rt } => {
                if rt == 15 {
                    // `vmrs APSR_nzcv, fpscr` transfers the FPSCR condition
                    // bits to the integer flags instead of writing r15.
                    self.line("ctx->n = (ctx->fpscr >> 31) & 1u;");
                    self.line("ctx->z = (ctx->fpscr >> 30) & 1u;");
                    self.line("ctx->c = (ctx->fpscr >> 29) & 1u;");
                    self.line("ctx->v = (ctx->fpscr >> 28) & 1u;");
                } else {
                    self.line(&format!("ctx->r[{rt}] = ctx->fpscr;"));
                }
            }
            VfpOp::Vmsr { rt } => self.line(&format!("ctx->fpscr = ctx->r[{rt}];")),
            VfpOp::MovImm { .. } => {
                // VFPv3-only; the decoder rejects it for the ARM11 target.
                self.line(&format!("recomp_unhandled(ctx, {}, \"VFPv3 VMOV immediate on VFPv2\");", hex(insn.addr)));
            }
        }
    }

    fn emit_insn(&mut self, insn: &Insn) {
        match insn.op {
            Op::Dp { op, rd, rn, op2, set_flags } => {
                self.guard(insn, |e| {
                    if rd == PC {
                        let tag = e.tag(insn.addr);
                        let dest = format!("pcdst_{tag}");
                        e.line(&format!("uint32_t {dest} = 0;"));
                        e.emit_dp(insn, op, rd, rn, op2, set_flags, Some(&dest));
                        e.pc_write(insn.addr, &dest);
                    } else {
                        e.emit_dp(insn, op, rd, rn, op2, set_flags, None);
                    }
                });
                self.fallthrough(insn.addr, insn.size);
            }
            Op::Mul { rd, ra, rm, rs, accumulate, set_flags } => {
                self.guard(insn, |e| {
                    let tag = e.tag(insn.addr);
                    let m = format!("m_{tag}");
                    let t = format!("ctx->r[{rm}] * ctx->r[{rs}]");
                    let r = if accumulate { format!("{t} + ctx->r[{ra}]") } else { t };
                    e.line(&format!("uint32_t {m} = {r};"));
                    e.line(&format!("ctx->r[{rd}] = {m};"));
                    if set_flags {
                        e.set_nz(&m);
                    }
                });
                self.fallthrough(insn.addr, insn.size);
            }
            Op::MulLong { signed, accumulate, set_flags, rd_lo, rd_hi, rm, rs } => {
                self.guard(insn, |e| {
                    let tag = e.tag(insn.addr);
                    let prod = format!("pl_{tag}");
                    let ty = if signed { "int64_t" } else { "uint64_t" };
                    let cast = if signed { "int32_t" } else { "uint32_t" };
                    e.line(&format!(
                        "{ty} {prod} = ({ty})({cast})(ctx->r[{rm}]) * ({ty})({cast})(ctx->r[{rs}]);"
                    ));
                    let acc = format!("ac_{tag}");
                    if accumulate {
                        e.line(&format!("uint64_t {acc} = ((uint64_t)ctx->r[{rd_hi}] << 32) | ctx->r[{rd_lo}];"));
                        e.line(&format!("{prod} += (uint64_t){acc};"));
                    }
                    e.line(&format!("ctx->r[{rd_lo}] = (uint32_t){prod};"));
                    e.line(&format!("ctx->r[{rd_hi}] = (uint32_t)({prod} >> 32);"));
                    if set_flags {
                        e.line(&format!("ctx->n = (uint32_t)((uint64_t){prod} >> 63);"));
                        e.line(&format!("ctx->z = ((uint64_t){prod} == 0);"));
                    }
                });
                self.fallthrough(insn.addr, insn.size);
            }
            Op::HalfMul { accumulate, rd, rn, rm, rs, x, y } => {
                self.guard(insn, |e| {
                    let tag = e.tag(insn.addr);
                    e.line(&format!(
                        "int32_t a_{tag} = (int32_t)(int16_t)(({}ctx->r[{rn}]) >> {});",
                        if x { "" } else { "" },
                        if x { 16 } else { 0 }
                    ));
                    e.line(&format!(
                        "int32_t b_{tag} = (int32_t)(int16_t)(({}ctx->r[{rm}]) >> {});",
                        "",
                        if y { 16 } else { 0 }
                    ));
                    let prod = format!("(int32_t)(a_{tag} * b_{tag})");
                    let res = if accumulate {
                        format!("(uint32_t)({prod} + (int32_t)ctx->r[{rs}])")
                    } else {
                        format!("(uint32_t){prod}")
                    };
                    e.line(&format!("ctx->r[{rd}] = {res};"));
                });
                self.fallthrough(insn.addr, insn.size);
            }
            Op::WordHalfMul { accumulate, top, rd, rn, rm, rs } => {
                self.guard(insn, |e| {
                    let tag = e.tag(insn.addr);
                    e.line(&format!(
                        "int64_t a_{tag} = (int64_t)(int32_t)ctx->r[{rn}] * (int64_t)(int16_t)(ctx->r[{rm}] >> {});",
                        if top { 16 } else { 0 }
                    ));
                    let res = format!("(uint32_t)((int64_t)a_{tag} >> 16)");
                    if accumulate {
                        e.line(&format!("ctx->r[{rd}] = {res} + ctx->r[{rs}];"));
                    } else {
                        e.line(&format!("ctx->r[{rd}] = {res};"));
                    }
                });
                self.fallthrough(insn.addr, insn.size);
            }
            Op::HalfMulLong { rd_lo, rd_hi, rm, rs, x, y } => {
                self.guard(insn, |e| {
                    let tag = e.tag(insn.addr);
                    e.line(&format!(
                        "int64_t a_{tag} = (int16_t)(ctx->r[{rm}] >> {});",
                        if x { 16 } else { 0 }
                    ));
                    e.line(&format!(
                        "int64_t b_{tag} = (int16_t)(ctx->r[{rs}] >> {});",
                        if y { 16 } else { 0 }
                    ));
                    e.line(&format!(
                        "uint64_t p_{tag} = (uint64_t)(a_{tag} * b_{tag}) + (((uint64_t)ctx->r[{rd_hi}] << 32) | ctx->r[{rd_lo}]);"
                    ));
                    e.line(&format!("ctx->r[{rd_lo}] = (uint32_t)p_{tag};"));
                    e.line(&format!("ctx->r[{rd_hi}] = (uint32_t)(p_{tag} >> 32);"));
                });
                self.fallthrough(insn.addr, insn.size);
            }
            Op::DualMul { subtract, exchange, accumulate, rd, ra, rn, rm } => {
                self.guard(insn, |e| {
                    let tag = e.tag(insn.addr);
                    e.line(&format!("int32_t a1_{tag} = (int16_t)ctx->r[{rn}];"));
                    e.line(&format!("int32_t a2_{tag} = (int16_t)(ctx->r[{rn}] >> 16);"));
                    if exchange {
                        e.line(&format!("int32_t b1_{tag} = (int16_t)(ctx->r[{rm}] >> 16);"));
                        e.line(&format!("int32_t b2_{tag} = (int16_t)ctx->r[{rm}];"));
                    } else {
                        e.line(&format!("int32_t b1_{tag} = (int16_t)ctx->r[{rm}];"));
                        e.line(&format!("int32_t b2_{tag} = (int16_t)(ctx->r[{rm}] >> 16);"));
                    }
                    let sign = if subtract { "-" } else { "+" };
                    let base = format!("(int64_t)a1_{tag} * b1_{tag} {sign} (int64_t)a2_{tag} * b2_{tag}");
                    if accumulate {
                        e.line(&format!("ctx->r[{rd}] = (uint32_t)({base} + (int32_t)ctx->r[{ra}]);"));
                    } else {
                        e.line(&format!("ctx->r[{rd}] = (uint32_t)({base});"));
                    }
                });
                self.fallthrough(insn.addr, insn.size);
            }
            Op::DualMulLong { subtract, exchange, rd_lo, rd_hi, rn, rm } => {
                self.guard(insn, |e| {
                    let tag = e.tag(insn.addr);
                    e.line(&format!("int32_t a1_{tag} = (int16_t)ctx->r[{rn}];"));
                    e.line(&format!("int32_t a2_{tag} = (int16_t)(ctx->r[{rn}] >> 16);"));
                    if exchange {
                        e.line(&format!("int32_t b1_{tag} = (int16_t)(ctx->r[{rm}] >> 16);"));
                        e.line(&format!("int32_t b2_{tag} = (int16_t)ctx->r[{rm}];"));
                    } else {
                        e.line(&format!("int32_t b1_{tag} = (int16_t)ctx->r[{rm}];"));
                        e.line(&format!("int32_t b2_{tag} = (int16_t)(ctx->r[{rm}] >> 16);"));
                    }
                    let sign = if subtract { "-" } else { "+" };
                    e.line(&format!(
                        "int64_t p_{tag} = (int64_t)a1_{tag} * b1_{tag} {sign} (int64_t)a2_{tag} * b2_{tag};"
                    ));
                    e.line(&format!(
                        "uint64_t r_{tag} = (uint64_t)p_{tag} + (((uint64_t)ctx->r[{rd_hi}] << 32) | ctx->r[{rd_lo}]);"
                    ));
                    e.line(&format!("ctx->r[{rd_lo}] = (uint32_t)r_{tag};"));
                    e.line(&format!("ctx->r[{rd_hi}] = (uint32_t)(r_{tag} >> 32);"));
                });
                self.fallthrough(insn.addr, insn.size);
            }
            Op::Usad { accumulate, rd, ra, rn, rm } => {
                self.guard(insn, |e| {
                    let base = format!("recomp_usad8(ctx->r[{rn}], ctx->r[{rm}])");
                    if accumulate {
                        e.line(&format!("ctx->r[{rd}] = {base} + ctx->r[{ra}];"));
                    } else {
                        e.line(&format!("ctx->r[{rd}] = {base};"));
                    }
                });
                self.fallthrough(insn.addr, insn.size);
            }
            Op::Pkh { tb, rd, rn, rm, shift } => {
                self.guard(insn, |e| {
                    let sh = shift.min(31);
                    if tb {
                        if shift == 0 {
                            e.line(&format!("ctx->r[{rd}] = (ctx->r[{rn}] & 0xffff0000u) | ((uint32_t)((int32_t)ctx->r[{rm}] >> 31) & 0xffffu);"));
                        } else {
                            e.line(&format!("ctx->r[{rd}] = (ctx->r[{rn}] & 0xffff0000u) | ((uint32_t)((int32_t)ctx->r[{rm}] >> {sh}) & 0xffffu);"));
                        }
                    } else {
                        e.line(&format!("ctx->r[{rd}] = (ctx->r[{rn}] & 0xffffu) | ((ctx->r[{rm}] << {sh}) & 0xffff0000u);"));
                    }
                });
                self.fallthrough(insn.addr, insn.size);
            }
            Op::Sel { rd, rn, rm } => {
                self.guard(insn, |e| {
                    e.line(&format!("ctx->r[{rd}] = sel(ctx->ge, ctx->r[{rn}], ctx->r[{rm}]);"));
                });
                self.fallthrough(insn.addr, insn.size);
            }
            Op::Sat { signed, rd, rn, imm, shift } => {
                self.guard(insn, |e| {
                    let tag = e.tag(insn.addr);
                    let (sv, _) = e.shift_operand(&tag, &format!("ctx->r[{rn}]"), shift, false);
                    let fun = if signed { "ssat" } else { "usat" };
                    e.line(&format!("ctx->r[{rd}] = {fun}((int32_t){sv}, {imm}, &ctx->q);"));
                });
                self.fallthrough(insn.addr, insn.size);
            }
            Op::Sat16 { signed, rd, rn, imm } => {
                self.guard(insn, |e| {
                    let tag = e.tag(insn.addr);
                    e.line(&format!("uint32_t in_{tag} = ctx->r[{rn}];"));
                    let fun = if signed { "ssat" } else { "usat" };
                    e.line(&format!(
                        "ctx->r[{rd}] = ({fun}((int32_t)(int16_t)in_{tag}, {imm}, &ctx->q) & 0xffffu) | ({fun}((int32_t)(int16_t)(in_{tag} >> 16), {imm}, &ctx->q) << 16);"
                    ));
                });
                self.fallthrough(insn.addr, insn.size);
            }
            Op::Rev { kind, rd, rm } => {
                self.guard(insn, |e| {
                    let expr = match kind {
                        RevKind::Rev => format!("rev32(ctx->r[{rm}])"),
                        RevKind::Rev16 => format!("(rev32(ctx->r[{rm}]) >> 16) | (rev32(ctx->r[{rm}]) << 16)"),
                        RevKind::RevSh => format!("(uint32_t)(int32_t)(int16_t)((ctx->r[{rm}] >> 8) | (ctx->r[{rm}] << 8))"),
                    };
                    e.line(&format!("ctx->r[{rd}] = {expr};"));
                });
                self.fallthrough(insn.addr, insn.size);
            }
            Op::Clz { rd, rm } => {
                self.guard(insn, |e| {
                    e.line(&format!("ctx->r[{rd}] = clz32(ctx->r[{rm}]);"));
                });
                self.fallthrough(insn.addr, insn.size);
            }
            Op::QAdd { op, rd, rm, rn } => {
                self.guard(insn, |e| {
                    let tag = e.tag(insn.addr);
                    e.line(&format!("int64_t a_{tag} = (int32_t)ctx->r[{rm}];"));
                    e.line(&format!("int64_t b_{tag} = (int32_t)ctx->r[{rn}];"));
                    let expr = match op {
                        QAddOp::Qadd => format!("a_{tag} + b_{tag}"),
                        QAddOp::Qsub => format!("a_{tag} - b_{tag}"),
                        QAddOp::Qdadd => format!("a_{tag} + sat_s32(2 * b_{tag}, &ctx->q)"),
                        QAddOp::Qdsub => format!("a_{tag} - sat_s32(2 * b_{tag}, &ctx->q)"),
                    };
                    e.line(&format!("ctx->r[{rd}] = sat_s32((int64_t)({expr}), &ctx->q);"));
                });
                self.fallthrough(insn.addr, insn.size);
            }
            Op::Parallel { signed, saturating, halving, op, rd, rn, rm } => {
                self.guard(insn, |e| {
                    let prefix = if signed {
                        if saturating { 1 } else if halving { 2 } else { 0 }
                    } else if saturating { 4 } else if halving { 5 } else { 3 };
                    let opv = match op {
                        ParallelOp::Add16 => 0,
                        ParallelOp::Asx => 1,
                        ParallelOp::Sax => 2,
                        ParallelOp::Sub16 => 3,
                        ParallelOp::Add8 => 4,
                        ParallelOp::Sub8 => 5,
                    };
                    e.line(&format!(
                        "ctx->r[{rd}] = recomp_parallel(ctx, {prefix}, {opv}, ctx->r[{rn}], ctx->r[{rm}]);"
                    ));
                });
                self.fallthrough(insn.addr, insn.size);
            }
            Op::Extend { signed, width, rd, rn, rm, rotate } => {
                self.guard(insn, |e| {
                    let tag = e.tag(insn.addr);
                    let source = rm.unwrap_or(0);
                    e.line(&format!(
                        "uint32_t in_{tag} = ror_r(ctx->r[{source}], {rotate});"
                    ));
                    let ext = match width {
                        ExtWidth::B => {
                            if signed { format!("(uint32_t)(int32_t)(int8_t)in_{tag}") } else { format!("in_{tag} & 0xffu") }
                        }
                        ExtWidth::H => {
                            if signed { format!("(uint32_t)(int32_t)(int16_t)in_{tag}") } else { format!("in_{tag} & 0xffffu") }
                        }
                        ExtWidth::B16 => {
                            let lo = if signed {
                                format!("(uint32_t)(int32_t)(int8_t)in_{tag}")
                            } else {
                                format!("in_{tag} & 0xffu")
                            };
                            let hi = if signed {
                                format!("((uint32_t)(int32_t)(int8_t)(in_{tag} >> 8) << 16)")
                            } else {
                                format!("((in_{tag} & 0xff00u) << 8)")
                            };
                            format!("(({lo}) & 0xffffu) | ({hi} & 0xffff0000u)")
                        }
                    };
                    if rn == 15 {
                        e.line(&format!("ctx->r[{rd}] = {ext};"));
                    } else {
                        match width {
                            ExtWidth::B16 => e.line(&format!(
                                "ctx->r[{rd}] = ((ctx->r[{rn}] + ({ext})) & 0xffffu) | (((ctx->r[{rn}] >> 16) + (({ext}) >> 16)) << 16);"
                            )),
                            _ => e.line(&format!("ctx->r[{rd}] = ctx->r[{rn}] + ({ext});")),
                        }
                    }
                });
                self.fallthrough(insn.addr, insn.size);
            }
            Op::B { target, link, exchange } => {
                let _ = exchange;
                self.guard(insn, |e| {
                    if link {
                        e.line(&format!("ctx->r[14] = {};", hex(insn.addr + insn.size as u32)));
                        e.function_call(target);
                    } else if e.func.insns.contains_key(&target) {
                        e.line(&format!("goto {};", label(target)));
                    } else {
                        e.function_call(target);
                        e.line("return;");
                    }
                });
                if !link {
                    if self.func.insns.contains_key(&target) {
                        // Both paths are labels; the guard already emitted the goto.
                    } else {
                        // Unconditional tail call already returned; conditional
                        // tail calls fall through here.
                        self.fallthrough(insn.addr, insn.size);
                    }
                } else {
                    self.fallthrough(insn.addr, insn.size);
                }
            }
            Op::Bx { rm, link, j } => {
                let _ = j;
                self.guard(insn, |e| {
                    if rm == LR && !link {
                        e.line("return;");
                    } else {
                        let t = format!("ctx->r[{rm}]");
                        if link {
                            e.line(&format!("ctx->r[14] = {};", hex(insn.addr + insn.size as u32)));
                            e.line(&format!("recomp_call_indirect(ctx, {t});"));
                        } else {
                            e.line(&format!("recomp_call_indirect(ctx, {t});"));
                            e.line("return;");
                        }
                    }
                });
                if !(rm == LR && !link) {
                    self.fallthrough(insn.addr, insn.size);
                }
            }
            Op::Mem(m) => {
                self.guard(insn, |e| e.emit_mem(insn, m));
                if !(m.kind.is_load() && m.rd == PC) {
                    self.fallthrough(insn.addr, insn.size);
                }
            }
            Op::Block(b) => {
                self.guard(insn, |e| e.emit_block(insn, b));
                if !(b.load && b.regs & (1 << PC) != 0) {
                    self.fallthrough(insn.addr, insn.size);
                }
            }
            Op::Swp { byte, rd, rm, rn } => {
                self.guard(insn, |e| {
                    e.line(&format!(
                        "ctx->r[{rd}] = recomp_swp(ctx, {}, ctx->r[{rn}], ctx->r[{rm}]);",
                        if byte { 1 } else { 0 }
                    ));
                });
                self.fallthrough(insn.addr, insn.size);
            }
            Op::Ldrex { size, rd, rn } => {
                self.guard(insn, |e| {
                    let bits = ex_bits(size);
                    e.line(&format!("ctx->r[{rd}] = recomp_ldrex(ctx, {bits}, ctx->r[{rn}]);"));
                });
                self.fallthrough(insn.addr, insn.size);
            }
            Op::Strex { size, rd, rm, rn } => {
                self.guard(insn, |e| {
                    let bits = ex_bits(size);
                    e.line(&format!(
                        "ctx->r[{rd}] = recomp_strex(ctx, {bits}, ctx->r[{rn}], ctx->r[{rm}]);"
                    ));
                });
                self.fallthrough(insn.addr, insn.size);
            }
            Op::Ldrexd { rd, rn } => {
                self.guard(insn, |e| {
                    let tag = e.tag(insn.addr);
                e.line(&format!("uint32_t hi_{tag} = 0;"));
                e.line(&format!("ctx->r[{rd}] = recomp_ldrexd(ctx, ctx->r[{rn}], &hi_{tag});"));
                if rd < 15 {
                    e.line(&format!("ctx->r[{}] = hi_{tag};", rd + 1));
                }
                });
                self.fallthrough(insn.addr, insn.size);
            }
            Op::Strexd { rd, rm, rn } => {
                self.guard(insn, |e| {
                    if rm >= 15 {
                        e.line(&format!("recomp_unhandled(ctx, {}, \"STREXD with odd high register\");", hex(insn.addr)));
                    } else {
                        e.line(&format!(
                            "ctx->r[{rd}] = recomp_strexd(ctx, ctx->r[{rn}], ctx->r[{rm}], ctx->r[{}]);",
                            rm + 1
                        ));
                    }
                });
                self.fallthrough(insn.addr, insn.size);
            }
            Op::Clrex => {
                self.guard(insn, |e| e.line("recomp_clrex(ctx);"));
                self.fallthrough(insn.addr, insn.size);
            }
            Op::Mrs { rd, spsr } => {
                self.guard(insn, |e| {
                    let _ = spsr;
                    e.line(&format!(
                        "ctx->r[{rd}] = (ctx->n << 31) | (ctx->z << 30) | (ctx->c << 29) | (ctx->v << 28) | (ctx->q << 27) | (ctx->ge << 16);"
                    ));
                });
                self.fallthrough(insn.addr, insn.size);
            }
            Op::TlsRead { rd } => {
                self.guard(insn, |e| e.line(&format!("ctx->r[{rd}] = ctx->tls;")));
                self.fallthrough(insn.addr, insn.size);
            }
            Op::Msr { rn, mask, spsr } => {
                self.guard(insn, |e| {
                    let _ = spsr;
                    if mask & 8 != 0 {
                        e.line(&format!("ctx->n = (ctx->r[{rn}] >> 31) & 1u;"));
                        e.line(&format!("ctx->z = (ctx->r[{rn}] >> 30) & 1u;"));
                        e.line(&format!("ctx->c = (ctx->r[{rn}] >> 29) & 1u;"));
                        e.line(&format!("ctx->v = (ctx->r[{rn}] >> 28) & 1u;"));
                    }
                    if mask & 4 != 0 {
                        e.line(&format!("ctx->q = (ctx->r[{rn}] >> 27) & 1u;"));
                    }
                });
                self.fallthrough(insn.addr, insn.size);
            }
            Op::Cps { .. } | Op::Setend { .. } | Op::Barrier | Op::Nop | Op::Pld { .. } => {
                self.fallthrough(insn.addr, insn.size);
            }
            Op::Svc { imm } => {
                self.guard(insn, |e| {
                    e.line(&format!("recomp_svc(ctx, {}, {});", hex(imm), hex(insn.addr)));
                });
                self.fallthrough(insn.addr, insn.size);
            }
            Op::Bkpt { .. } => {
                self.line(&format!("recomp_unhandled(ctx, {}, \"BKPT\");", hex(insn.addr)));
            }
            Op::Vfp(v) => {
                self.guard(insn, |e| e.emit_vfp(insn, v));
                self.fallthrough(insn.addr, insn.size);
            }
            Op::Coproc { raw } => {
                self.guard(insn, |e| {
                    e.line(&format!("recomp_coproc(ctx, {}, {});", hex(insn.addr), hex(raw)));
                });
                self.fallthrough(insn.addr, insn.size);
            }
            Op::Unhandled { what } => {
                self.line(&format!(
                    "recomp_unhandled(ctx, {}, {:?});",
                    hex(insn.addr),
                    what
                ));
            }
        }
    }

    fn emit_function(&mut self) {
        let _ = writeln!(self.out, "void {}(Ctx *ctx) {{", fn_name(self.func.entry));
        self.line(&format!("RECOMP_ENTER(ctx, {});", hex(self.func.entry)));
        if self.polls.iter().any(|&(a, _)| a == self.func.entry) {
            self.line(&format!("recomp_svc(ctx, 0xFFFFFFFFu, {});", hex(self.func.entry)));
        }
        self.line(&format!("goto {};", label(self.func.entry)));
        for (&addr, insn) in &self.func.insns {
            self.line(&format!("{}: ;", label(addr)));
            self.emit_insn(insn);
        }
        self.line("return;");
        let _ = writeln!(self.out, "}}");
    }
}

fn ex_bits(size: ExSize) -> u32 {
    match size {
        ExSize::B => 8,
        ExSize::H => 16,
        ExSize::W => 32,
        ExSize::D => 64,
    }
}

pub fn emit_all(image: &Image, analysis: &Analysis, out: &Path, polls: &[(u32, Mode)]) -> io::Result<EmitStats> {
    std::fs::create_dir_all(out)?;
    let mut stats = EmitStats::default();

    let mut header = String::new();
    header.push_str("/* Generated by fl-recomp from the caller's own Fantasy Life EU image. */\n");
    header.push_str("#ifndef FL_RECOMP_GENERATED_H\n#define FL_RECOMP_GENERATED_H\n\n#include \"recomp.h\"\n\n");
    for &addr in analysis.functions.keys() {
        let _ = writeln!(header, "void {}(Ctx *ctx);", fn_name(addr));
    }
    for &(addr, _) in &analysis.stubs {
        let _ = writeln!(header, "void {}(Ctx *ctx);", fn_name(addr));
    }
    header.push_str("\n#endif\n");
    stats.bytes += header.len() as u64;
    std::fs::write(out.join("fl_recomp.h"), header)?;
    stats.files += 1;

    let funcs: Vec<&Function> = analysis.functions.values().collect();
    for (chunk_index, chunk) in funcs.chunks(FUNCTIONS_PER_FILE).enumerate() {
        let mut body = String::new();
        let _ = writeln!(body, "/* fl-recomp chunk {chunk_index} */");
        body.push_str("#include \"fl_recomp.h\"\n\n");
        for func in chunk {
            let mut e = Emitter::new(func, analysis, polls);
            e.emit_function();
            body.push_str(&e.out);
            body.push('\n');
        }
        let path = out.join(format!("fl_recomp_{chunk_index:03}.c"));
        stats.bytes += body.len() as u64;
        std::fs::write(&path, body)?;
        stats.files += 1;
    }

    let mut lookup = String::new();
    lookup.push_str("/* Generated function lookup. */\n#include \"fl_recomp.h\"\n\n");
    for &(addr, _) in &analysis.stubs {
        let _ = writeln!(
            lookup,
            "void {}(Ctx *ctx) {{ recomp_unhandled(ctx, {}, \"function contains data or non-Thumb-1 bytes\"); }}",
            fn_name(addr),
            hex(addr)
        );
    }
    // `recomp_call_indirect` binary-searches this table. Stubs are separate
    // functions in `Analysis`, so merge and sort both sets rather than
    // appending them after the ordinary functions.
    let mut entries: Vec<u32> = analysis.functions.keys().copied().collect();
    entries.extend(analysis.stubs.iter().map(|&(addr, _)| addr));
    entries.sort_unstable();
    entries.dedup();
    lookup.push_str("\nconst RecompEntry recomp_functions[] = {\n");
    for addr in entries {
        let _ = writeln!(lookup, "    {{{}, {}}},", hex(addr), fn_name(addr));
    }
    lookup.push_str("};\nconst size_t recomp_function_count = sizeof(recomp_functions) / sizeof(recomp_functions[0]);\n");
    stats.bytes += lookup.len() as u64;
    std::fs::write(out.join("fl_recomp_lookup.c"), lookup)?;
    stats.files += 1;

    let _ = image;
    Ok(stats)
}
