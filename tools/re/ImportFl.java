// Raw EU .code layout. Run as analyzeHeadless -preScript ImportFl.java.
// @category FantasyLife
import ghidra.app.script.GhidraScript;
import ghidra.program.model.mem.MemoryBlock;

public class ImportFl extends GhidraScript {
    public void run() throws Exception {
        var mem = currentProgram.getMemory();
        MemoryBlock text = mem.getBlock(toAddr(0x100000));
        mem.split(text, toAddr(0x61d000));
        MemoryBlock ro = mem.getBlock(toAddr(0x61d000));
        mem.split(ro, toAddr(0x6a4000));
        MemoryBlock data = mem.getBlock(toAddr(0x6a4000));
        text.setName(".text"); text.setRead(true); text.setWrite(false); text.setExecute(true);
        ro.setName(".rodata"); ro.setRead(true); ro.setWrite(false); ro.setExecute(false);
        data.setName(".data"); data.setRead(true); data.setWrite(true); data.setExecute(false);
        var bss = mem.createUninitializedBlock(".bss", toAddr(0x6dc000), 0xcca88, false);
        bss.setRead(true); bss.setWrite(true); bss.setExecute(false);
        disassemble(toAddr(0x100000)); createFunction(toAddr(0x100000), "entry");
        // Verified ARM entry points and RTTI-derived destructors; no generated-C edits.
        for (long a : new long[]{0x28b748,0x28b8dc,0x28b9a0,0x28ba54,0x28ba58,0x11312c}) {
            disassemble(toAddr(a)); createFunction(toAddr(a), null);
        }
    }
}
