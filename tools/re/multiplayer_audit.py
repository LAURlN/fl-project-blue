#!/usr/bin/env python3
"""Read-only FL EU v00 SDK IPC/SVC inventory (no guest execution).

Requires capstone. Generated C and code.bin must come from the user's own dump.
Only service-attributed UDS wrappers are listed, not unrelated identical headers.
"""
import argparse
from bisect import bisect_right
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re
import struct

from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM
from capstone.arm import ARM_OP_IMM, ARM_OP_MEM, ARM_REG_PC

BASE = 0x100000
UDS_START, UDS_END = 0x526C08, 0x5272D8
COMMANDS = {
    3: "Shutdown", 5: "EjectClient", 7: "UpdateNetworkAttribute", 8: "DestroyNetwork",
    10: "DisconnectNetwork", 11: "GetConnectionStatus", 13: "GetNodeInformation",
    15: "RecvBeaconBroadcastData", 16: "SetApplicationData", 17: "GetApplicationData",
    18: "Bind", 19: "Unbind", 20: "PullPacket", 23: "SendTo", 26: "GetChannel",
    27: "InitializeWithVersion", 29: "BeginHostingNetwork", 30: "ConnectToNetwork",
    31: "DecryptBeaconData", 33: "SetProbeResponseParam", 34: "ScanOnConnection",
}


def inventory(binary, generated, port):
    data = binary.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != "a2e10e861c49220070b74d2b3c1d6f8cc7e253bfa837a4b7543f87e0166b35bb":
        raise ValueError("requires unmodified Fantasy Life EU v00 code.bin")
    funcs = sorted(set(int(n, 16) for n in re.findall(
        r"\{0x([0-9a-f]+)u, f_", (generated / "lookup.c").read_text())))
    svcs = defaultdict(set)
    for source in generated.glob("recomp*.c"):
        for num, site in re.findall(r"recomp_svc\(ctx, 0x([0-9a-f]+)u, 0x([0-9a-f]+)u\)", source.read_text()):
            if int(num, 16) != 0xFFFFFFFF:  # scheduler checkpoint, not a guest SVC
                svcs[int(num, 16)].add(int(site, 16))
    # Also inspect every aligned ARM word in .text, including words outside emitted functions.
    # A raw candidate is not reachability proof, but an absent candidate would require review.
    emitted_sites = {site for sites in svcs.values() for site in sites}
    raw_candidates = set()
    for offset in range(0, 0x51CC68 - 3, 4):
        word = struct.unpack_from("<I", data, offset)[0]
        if word & 0xFFFFFF80 == 0xEF000000:
            raw_candidates.add(BASE + offset)
    assert not raw_candidates - emitted_sites, sorted(raw_candidates - emitted_sites)
    implemented_svcs = set(int(n, 16) for n in re.findall(
        r"case 0x([0-9A-Fa-f]+):", (port / "runtime/src/kernel/svc.cpp").read_text().split("uint32_t dispatch(")[1]))
    implemented_uds = set(int(n, 16) for n in re.findall(
        r"case 0x([0-9A-Fa-f]+):", (port / "runtime/src/hle/uds.cpp").read_text().split("void handle(Request")[1]))
    # Follow immediate/literal headers to STR TLS+0x80 or the Bind STM at 0x527128.
    # The attributed contiguous SDK stub block contains all UDS SendSyncRequest sites.
    cs = Cs(CS_ARCH_ARM, CS_MODE_ARM)
    cs.detail = True
    vals = {}
    headers = []
    svc_sites = []
    for addr in range(UDS_START, UDS_END, 4):
        decoded = list(cs.disasm(data[addr - BASE:addr - BASE + 4], addr))
        if not decoded:
            vals.clear()
            continue
        ins = decoded[0]
        ops = ins.operands
        if ins.mnemonic == "svc":
            svc_sites.append(addr)
        if ins.mnemonic == "ldr" and len(ops) == 2 and ops[1].type == ARM_OP_MEM and ops[1].mem.base == ARM_REG_PC:
            lit = addr + 8 + ops[1].mem.disp
            vals[ops[0].reg] = struct.unpack_from("<I", data, lit - BASE)[0]
        elif ins.mnemonic == "mov" and len(ops) == 2:
            vals[ops[0].reg] = ops[1].imm if ops[1].type == ARM_OP_IMM else vals.get(ops[1].reg)
        elif ins.mnemonic == "str" and len(ops) == 2 and ops[1].type == ARM_OP_MEM and ops[1].mem.disp == 0x80:
            header = vals.get(ops[0].reg)
            if header is not None:
                headers.append((addr, header))
        elif addr == 0x527128:  # STM r4,{r1,r2,r3}, command buffer base set by ADD r4,r4,#0x80
            headers.append((addr, vals[ops[1].reg]))
    assert len(headers) == len(svc_sites) == 21, (len(headers), len(svc_sites))
    assert set(h >> 16 for _, h in headers) == set(COMMANDS)
    uds = [{"function": f"0x{funcs[bisect_right(funcs, addr) - 1]:08x}", "header_site": f"0x{addr:08x}",
            "header": f"0x{header:08x}", "command": COMMANDS[header >> 16],
            "implemented": header >> 16 in implemented_uds} for addr, header in headers]
    return {"code_sha256": digest, "scope": "all emitted guest SVCs; all 21 service-attributed UDS SDK stubs",
            "raw_unconditional_arm_svc_candidates_outside_generated": 0,
            "svc": {f"0x{n:02x}": {"implemented": n in implemented_svcs,
                                     "sites": [f"0x{a:08x}" for a in sorted(sites)]}
                    for n, sites in sorted(svcs.items())}, "uds": uds}


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--generated", type=Path, required=True)
    parser.add_argument("--port", type=Path, required=True)
    args = parser.parse_args()
    report = inventory(args.binary, args.generated, args.port)
    print(json.dumps(report, indent=2))
    if any(not item["implemented"] for item in [*report["svc"].values(), *report["uds"]]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
