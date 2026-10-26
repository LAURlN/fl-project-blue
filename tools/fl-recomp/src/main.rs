mod arm;
mod discover;
mod emit;
mod image;
mod insn;
mod thumb;

#[cfg(test)]
mod tests;

use std::collections::BTreeMap;
use std::io::Write;
use std::path::PathBuf;
use std::process::ExitCode;

fn usage() {
    eprintln!(
        "fl-recomp: clean-room ARM11 AOT translator for Fantasy Life EU v00\n\n\
         usage:\n\
           fl-recomp decode <hex-word> [arm|thumb]\n\
           fl-recomp analyze <extracted/fl_eu> [--entries FILE] [--polls FILE] [--json FILE]\n\
           fl-recomp emit <extracted/fl_eu> <out-dir> [--entries FILE] [--polls FILE]\n"
    );
}

fn option(args: &[String], name: &str) -> Option<PathBuf> {
    args.iter().position(|a| a == name).and_then(|i| args.get(i + 1)).map(PathBuf::from)
}

fn input_dir(args: &[String]) -> Option<PathBuf> {
    args.iter().find(|a| !a.starts_with("--") && a.as_str() != "analyze" && a.as_str() != "emit")
        .map(PathBuf::from)
}

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let Some(cmd) = args.first().map(String::as_str) else {
        usage();
        return ExitCode::from(2);
    };
    match cmd {
        "decode" => {
            let Some(text) = args.get(1) else {
                usage();
                return ExitCode::from(2);
            };
            let raw = u32::from_str_radix(text.trim_start_matches("0x"), 16).unwrap_or(0);
            let mode = args.get(2).map(String::as_str).unwrap_or("arm");
            let insn = if mode == "thumb" {
                thumb::decode(0, raw as u16)
            } else {
                arm::decode(0, raw)
            };
            println!("{raw:08x}  {:?}", insn);
            ExitCode::SUCCESS
        }
        "analyze" => analyze(&args).map_or_else(|e| fail(&e), |_| ExitCode::SUCCESS),
        "emit" => emit(&args).map_or_else(|e| fail(&e), |_| ExitCode::SUCCESS),
        _ => {
            usage();
            ExitCode::from(2)
        }
    }
}

fn fail(message: &str) -> ExitCode {
    eprintln!("fl-recomp: {message}");
    ExitCode::from(1)
}

fn analyze(args: &[String]) -> Result<(), String> {
    let dir = input_dir(args).ok_or_else(|| "analyze needs an extracted/fl_eu directory".to_string())?;
    let image = image::Image::load(&dir).map_err(|e| format!("{}: {e}", dir.display()))?;
    let hints = discover::load_hints(option(args, "--entries").as_deref(), option(args, "--polls").as_deref())
        .map_err(|e| format!("hints: {e}"))?;
    let analysis = discover::analyze(&image, &hints);
    report(&image, &analysis, option(args, "--json").as_deref())?;
    if analysis.unhandled.is_empty() {
        Ok(())
    } else {
        Err(format!("{} instruction(s) decoded as unhandled", analysis.unhandled.len()))
    }
}

fn emit(args: &[String]) -> Result<(), String> {
    let dir = input_dir(args).ok_or_else(|| "emit needs an extracted/fl_eu directory".to_string())?;
    let out = args.iter().filter(|a| !a.starts_with("--")).nth(2).map(PathBuf::from)
        .ok_or_else(|| "emit needs an output directory".to_string())?;
    let image = image::Image::load(&dir).map_err(|e| format!("{}: {e}", dir.display()))?;
    let hints = discover::load_hints(option(args, "--entries").as_deref(), option(args, "--polls").as_deref())
        .map_err(|e| format!("hints: {e}"))?;
    let analysis = discover::analyze(&image, &hints);
    if !analysis.unhandled.is_empty() {
        return Err(format!(
            "refusing to emit with {} unhandled instruction(s); run `analyze` for addresses",
            analysis.unhandled.len()
        ));
    }
    let started = std::time::Instant::now();
    let stats = emit::emit_all(&image, &analysis, &out, &hints.polls).map_err(|e| format!("{}: {e}", out.display()))?;
    eprintln!(
        "emitted {} functions, {} instructions, {} bytes in {:.2}s to {}",
        analysis.functions.len(),
        analysis.instruction_count,
        stats.bytes,
        started.elapsed().as_secs_f64(),
        out.display()
    );
    Ok(())
}

fn report(image: &image::Image, analysis: &discover::Analysis, json: Option<&std::path::Path>) -> Result<(), String> {
    let covered_code = analysis
        .code_bytes
        .saturating_sub(analysis.literal_bytes)
        .saturating_sub(analysis.switch_bytes);
    let coverage = if analysis.text_size == 0 {
        0.0
    } else {
        100.0 * analysis.code_bytes as f64 / analysis.text_size as f64
    };
    let gap_bytes: u32 = analysis.gaps.iter().map(|&(_, len)| len).sum();
    println!("text            {:08x}-{:08x} ({} bytes)", image.text.addr, image.text_end(), analysis.text_size);
    println!("functions       {}", analysis.functions.len());
    println!("instructions    {}", analysis.instruction_count);
    println!("entry seeds     {}", analysis.entries.len());
    println!("rejected seeds  {}", analysis.rejected.len());
    println!("unhandled       {}", analysis.unhandled.len());
    println!("stub functions  {}", analysis.stubs.len());
    println!("indirect sites  {}", analysis.indirect_sites.len());
    println!("covered bytes   {} ({coverage:.2}%)", analysis.code_bytes);
    println!("literal bytes   {}", analysis.literal_bytes);
    println!("switch bytes    {}", analysis.switch_bytes);
    println!("gap bytes       {gap_bytes}");
    println!("non-data code   {covered_code}");

    if !analysis.rejected.is_empty() {
        println!("\nrejected:");
        for r in analysis.rejected.iter().take(20) {
            println!("  {:08x} {:?}: {}", r.addr, r.mode, r.reason);
        }
        if analysis.rejected.len() > 20 {
            println!("  ... {} more", analysis.rejected.len() - 20);
        }
    }
    if !analysis.unhandled.is_empty() {
        let mut by_raw: BTreeMap<(u32, u32), usize> = BTreeMap::new();
        for &(_, _, raw) in &analysis.unhandled {
            *by_raw.entry((raw >> 20, raw & 0xF)).or_default() += 1;
        }
        println!("\nunhandled (first 30):");
        for &(addr, mode, raw) in analysis.unhandled.iter().take(30) {
            println!("  {:08x} {:?} {raw:08x}", addr, mode);
        }
        println!("\nunhandled opcode groups (bits27:20, low nibble):");
        for ((hi, lo), count) in by_raw.iter().take(40) {
            println!("  {hi:03x}:{lo:x} x{count}");
        }
    }
    if let Some(path) = json {
        let body = analysis_json(image, analysis);
        std::fs::write(path, body).map_err(|e| format!("{}: {e}", path.display()))?;
    }
    Ok(())
}

fn analysis_json(image: &image::Image, analysis: &discover::Analysis) -> String {
    let mut s = String::new();
    s.push_str("{\n");
    s.push_str(&format!("  \"text_start\": {},\n", image.text.addr));
    s.push_str(&format!("  \"text_size\": {},\n", analysis.text_size));
    s.push_str(&format!("  \"functions\": {},\n", analysis.functions.len()));
    s.push_str(&format!("  \"instructions\": {},\n", analysis.instruction_count));
    s.push_str(&format!("  \"covered_bytes\": {},\n", analysis.code_bytes));
    s.push_str(&format!("  \"unhandled\": {},\n", analysis.unhandled.len()));
    s.push_str("  \"stubs\": [");
    for (i, &(addr, mode)) in analysis.stubs.iter().enumerate() {
        if i != 0 {
            s.push(',');
        }
        s.push_str(&format!("\n    {{\"addr\": {addr}, \"mode\": \"{mode:?}\"}}"));
    }
    s.push_str("\n  ],\n");
    s.push_str("  \"unhandled_sites\": [");
    for (i, &(addr, mode, raw)) in analysis.unhandled.iter().enumerate() {
        if i != 0 {
            s.push(',');
        }
        s.push_str(&format!("\n    {{\"addr\": {addr}, \"mode\": \"{mode:?}\", \"raw\": {raw}}}"));
    }
    s.push_str("\n  ],\n");
    s.push_str("  \"gaps\": [");
    for (i, &(addr, len)) in analysis.gaps.iter().enumerate() {
        if i != 0 {
            s.push(',');
        }
        s.push_str(&format!("\n    {{\"addr\": {addr}, \"size\": {len}}}"));
    }
    s.push_str("\n  ],\n  \"switch_sites\": [");
    let mut first_switch = true;
    for func in analysis.functions.values() {
        for sw in &func.switches {
            if !first_switch {
                s.push(',');
            }
            first_switch = false;
            s.push_str(&format!(
                "\n    {{\"site\": {}, \"entries\": {}}}",
                sw.site,
                sw.cases.len()
            ));
        }
    }
    s.push_str("\n  ],\n  \"function_list\": [");
    for (i, func) in analysis.functions.values().enumerate() {
        if i != 0 {
            s.push(',');
        }
        s.push_str(&format!(
            "\n    {{\"addr\": {}, \"mode\": \"{:?}\", \"insns\": {}}}",
            func.entry,
            func.mode,
            func.insns.len()
        ));
    }
    s.push_str("\n  ]\n}\n");
    s
}

#[allow(dead_code)]
fn write_file(path: &std::path::Path, body: &str) -> std::io::Result<()> {
    let mut f = std::fs::File::create(path)?;
    f.write_all(body.as_bytes())
}
