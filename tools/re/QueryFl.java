// QueryFl.java OUTPUT_DIR [function-VA|x:reference-target|X:deep-xref(literal pool)|start:end|e:verified-entry|r:rebuild-entry|n:returning-entry]...
// @category FantasyLife
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.program.model.listing.FlowOverride;
import java.io.*;

public class QueryFl extends GhidraScript {
    public void run() throws Exception {
        String[] args = getScriptArgs();
        File dir = new File(args[0]); dir.mkdirs();
        DecompInterface di = new DecompInterface(); di.openProgram(currentProgram);
        try (PrintWriter refs = new PrintWriter(new File(dir, "query.txt"))) {
            for (int n=1; n<args.length; ++n) {
                String arg=args[n];
                if (arg.startsWith("n:")) {
                    // Correct an auto-analysis noreturn mistake only after checking ARM.
                    var a=toAddr(Long.decode(arg.substring(2)));
                    var f=getFunctionAt(a);
                    if(f!=null) {
                        f.setNoReturn(false);
                        var it=currentProgram.getReferenceManager().getReferencesTo(a);
                        while(it.hasNext()) {
                            var ins=getInstructionAt(it.next().getFromAddress());
                            if(ins!=null && ins.getFlowType().isCall()) {
                                ins.setFlowOverride(FlowOverride.NONE);
                                ins.setFallThrough(ins.getAddress().add(ins.getLength()));
                                disassemble(ins.getAddress().add(ins.getLength()));
                            }
                        }
                        refs.println("RETURNS "+a);
                    }
                } else if (arg.startsWith("X:")) {
                    // Deep xrefs: code that loads the value through a literal-pool word,
                    // plus direct references (pool word -> target, then ldr -> pool word).
                    var a=toAddr(Long.decode(arg.substring(2)));
                    var it=currentProgram.getReferenceManager().getReferencesTo(a);
                    while(it.hasNext()) {
                        var r=it.next(); var from=r.getFromAddress();
                        var f=getFunctionContaining(from);
                        if(f!=null) { refs.println(a+" <- "+from+" "+r.getReferenceType()+" "+f); continue; }
                        boolean any=false;
                        var it2=currentProgram.getReferenceManager().getReferencesTo(from);
                        while(it2.hasNext()) {
                            var r2=it2.next(); any=true;
                            refs.println(a+" <- pool "+from+" <- "+r2.getFromAddress()+" "+getFunctionContaining(r2.getFromAddress()));
                        }
                        if(!any) refs.println(a+" <- pool "+from+" (no code ref)");
                    }
                } else if (arg.startsWith("x:")) {
                    var a=toAddr(Long.decode(arg.substring(2)));
                    var it=currentProgram.getReferenceManager().getReferencesTo(a);
                    while(it.hasNext()) {
                        var r=it.next(); var f=getFunctionContaining(r.getFromAddress());
                        refs.println(a+" <- "+r.getFromAddress()+" "+r.getReferenceType()+" "+f);
                    }
                } else if (arg.startsWith("e:") || arg.startsWith("r:")) {
                    // Use only after checking an entry in the ARM listing. Ghidra's raw
                    // automatic analysis can swallow distinct functions into a bad body.
                    var a=toAddr(Long.decode(arg.substring(2)));
                    var f=getFunctionAt(a);
                    if(f!=null && arg.startsWith("r:")) { removeFunction(f); f=null; }
                    if(f==null) {
                        var containing=getFunctionContaining(a);
                        if(containing!=null) removeFunction(containing);
                        disassemble(a); f=createFunction(a,null);
                    }
                    if(f!=null) export(di,dir,f);
                    else refs.println("NO ENTRY "+a);
                } else if (arg.contains(":")) {
                    String[] bounds=arg.split(":");
                    long start=Long.decode(bounds[0]), end=Long.decode(bounds[1]);
                    var it=currentProgram.getFunctionManager().getFunctions(toAddr(start),true);
                    while(it.hasNext()) {
                        var f=it.next();
                        if(f.getEntryPoint().getOffset()>=end) break;
                        export(di,dir,f);
                    }
                } else {
                    var a=toAddr(Long.decode(arg));
                    var f=getFunctionContaining(a);
                    if (f==null) {disassemble(a); f=createFunction(a,null);}
                    if (f==null) {refs.println("NO FUNCTION "+a); continue;}
                    export(di,dir,f);
                }
            }
        } finally {di.dispose();}
    }
    void export(DecompInterface di,File dir,ghidra.program.model.listing.Function f) throws Exception {
        var res=di.decompileFunction(f,60,monitor);
        try(PrintWriter out=new PrintWriter(new File(dir,f.getEntryPoint()+".c"))) {
            out.println("// "+f.getEntryPoint()+" "+f.getName());
            var it=currentProgram.getReferenceManager().getReferencesTo(f.getEntryPoint());
            int n=0;
            while(it.hasNext()) {
                var r=it.next(); var caller=getFunctionContaining(r.getFromAddress());
                if(n++<12) out.println("// XREF "+r.getFromAddress()+" "+r.getReferenceType()+" "+caller);
            }
            if(n>12) out.println("// ... "+n+" xrefs total");
            if(res.decompileCompleted()) out.println(res.getDecompiledFunction().getC());
            else out.println(res.getErrorMessage());
        }
    }
}
