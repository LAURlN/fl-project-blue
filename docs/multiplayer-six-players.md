# Fantasy Life EU: feasibility of four, five and six players

> **Note:** paths starting with `port/` (and `runtime/`) refer to the runtime's source code, which is not part of this package. They are kept as historical research context.

| Total players (host included) | Verdict | Required work | Delivery effort / risk | Cheapest decisive spike |
| --- | --- | --- | --- | --- |
| **4** | **Hypothesis: technically plausible; not demonstrated.** The fourth slot already crosses confirmed storage boundaries. | R: session clamp, relocated/grown player state, maps, queues and serializers; D/R: HUD and menus. Runtime instrumentation; memory tuning only if measured necessary. | **L–XL / high** | S offline storage/codec audit, then M–L four-player membership + movement proof after original three-player multiplayer works. |
| **5** | **Hypothesis: plausible only after the four-player design succeeds.** No separate five-player transport barrier found. | Same generalization to capacity six, five-slot validation, larger UI and sync/transaction audit. | **XL / very high** | Reuse the proven four-player implementation; round-trip slot 4 and exercise five distinct players, departure and rejoin. |
| **6** | **Hypothesis: plausible research target, not a promised feature.** Transport capacity is sufficient in principle; game semantics, memory and traffic remain unproven. | All above; six-slot gameplay/serialization/UI, authority and trading validation, traffic and performance budgets. | **XL / very high** | Six-slot offline round-trips, then six clients with combat/map changes and instrumented loss/burst testing. |

Effort uses ROADMAP §1: S = 1–3 days, M = 1–2 weeks,
L = 3–6 weeks, XL = months/heavy RE. Estimates are for a usable, tested feature,
after the original multiplayer prerequisites; later rows are total project scope,
not an additional XL for each player. The spike estimates are planning judgments.
**There is no data-only unlock and no demonstrated 4/5/6-player build.**

## Scope, provenance and confidence

Research date: **2026-10-25**. Main research baseline `bd75659911c18e79c671856093edcb8c81a97ce0`;
private runtime inspected at `7eaffbf6d0de80c7914280290641c19bb2eba938`.
EU v00, program `0004000000113100`. All addresses below are **guest virtual
addresses**, not code-file offsets. SCR row numbers are zero-based; resource IDs
are decimal. Object offsets describe guest RAM, not offsets in save files.

**Confirmed** means source, decoded data or ARM/generated-C behavior read
directly. **Hypothesis** means inferred purpose, scalability or gameplay behavior
which still needs validation. SDK names are descriptive research labels, not
recovered original symbols. A loop containing `3` is not classified as a player
limit without a relevant data-flow connection.

Read-only inputs were the main checkout's absolute paths under
`<project root>/`: `extracted/fl_eu/exefs/code.bin`,
`extracted/fl_eu/archive`, `port/build/generated-fl_eur`, and runtime source.
Generated instruction comments were cross-checked with Capstone ARM disassembly
of the extracted executable, using `python -I`. No game execution, build changes,
game-data edits/copies into Git, port edits, pushes or remotes were involved.
Offline verification passed for 13 key instruction anchors, seven IPC/size
literals, all 32 appended symbol addresses, symbol uniqueness/append-only history,
the report's local links and its three documentation pointers. `git diff --check`
also passed. No gameplay or performance result is claimed.

The `mp-local` branch owns the SVC `0x29` hosting crash and UDS join/event work.
Those fixes are prerequisites and are not duplicated here. Static reachability
does not establish that the current path completes successfully in-game.

## Evidence: where three lives

### E1. UDS and relay capacity are not intrinsically three

**Confirmed, runtime:** `port/runtime/src/hle/uds.cpp`:

- `NETWORK_INFO_SIZE = 0x108`, `NODE_INFO_SIZE = 0x28`, `MAX_NODES = 16`.
  `max_nodes()` reads network-info byte **`+0x1d`**.
- `BeginHostingNetwork`, command `0x001d`, copies the supplied info, installs host
  node 1 and current count 1 at `+0x1c`; it preserves the advertised maximum.
- `handle_join` searches free entries with **`1 <= i < max_nodes() && i < 16`**.
  With maximum 3, only guest node IDs 2 and 3 can be allocated. It also checks
  passphrase and defers requests while `ATTR_NO_NEW_PLAYERS` is set.
- Node membership and changed-node masks are **16-bit**, with bit `node_id - 1`.
  These transport masks have room for six; they are not game player-slot maps.

**Confirmed, external documentation read on this date:**
[3dbrew NWM Services](https://www.3dbrew.org/wiki/NWM_Services) states the maximum
is **16 nodes including the host** and documents NetworkStruct `+0x1c` current
count / `+0x1d` maximum count. Its
[CreateNetwork2 / BeginHostingNetwork](https://www.3dbrew.org/wiki/NWMUDS:CreateNetwork2)
page documents command header `0x001d0044` and the fatal hardware case maximum 1.
Thus real UDS does not impose the game's three-person maximum. The runtime's
synthetic wireless protocol remains Clockwork-only; this is not hardware crossplay.

`net/relay.h` has `ROOM_SIZE = 16`, `MAX_FRAME = 2000`.
`net/relay.cpp` forwards each frame to other room members, with a sender token
bucket of 300 frames/s and burst 600. Raising room size is unnecessary for six.

### E2. Hosting: caller, clamp and NetworkStruct byte

**Confirmed, generated C:** each address is searchable in the indicated
`port/build/generated-fl_eur/recomp_XXXX.c` instruction comments.

| Layer | File / address | Observed behavior |
| --- | --- | --- |
| Game hosting entry | `recomp_0059.c`, `0x0059c2c4` | Builds advertising/profile data and calls `0x0059df28`; call at `0x0059c3e4` supplies `-1` in the later capacity argument. |
| Default capacity | `recomp_0059.c`, `0x0059df28`, especially `0x0059dfec` | Replaces negative capacity with **3**, then calls `0x0047a1f4`. |
| Async session creation | `recomp_0047.c`, `0x0047a1f4` → `0x00473174` → `0x00472de0` | Transports the capacity into the common create/join-job setup. |
| Independent clamp and allocation | `recomp_0047.c`, `0x00472df4`–`0x00472e74` | Clamps requested count to **1..3**, allocates/clears a count-sized buffer (`job+0x8c`), stores count at `job+0x80`. Merely changing the default leaves this clamp. |
| Host dispatch | `recomp_0047.c`, `0x00472f20`–`0x00472f2c`; `recomp_0025.c`, `0x00253664` | Passes count into session interface vtable slot `+0x24`. Local implementation is `0x00286934` (vtable `0x0068ddcc`). |
| Local hosting setup/worker | `recomp_0028.c`, `0x00286934`, `0x00286d14` | Saves capacity byte at local-session `+0x38`; worker reads it at `0x00286d50`, calls `0x0026f680`. |
| Local library → UDS base | `recomp_0026.c`, `0x0026f680`; `recomp_0050.c`, `0x00502de8` | Virtual slot `+0x10` of vtable `0x0069b66c` dispatches to `0x00502de8`; that calls `0x004fe3fc`. |
| SDK hosting | `recomp_004f.c`, `0x004fe3fc`; `recomp_0052.c`, `0x00525598`, `0x00525420` | UDS base has a separate **12-entry** cap (`0x004fe408`/`0x004fe490`), still sufficient for six. The SDK hosting wrapper validates **2..16** at `0x00525470`–`0x0052547c`. |
| Actual maximum write | `recomp_0052.c`, `0x00525d28`, especially `0x00525d88` | Stores the supplied count byte to **NetworkStruct `+0x1d`**; `+0x16` becomes attributes `0x8000` in network byte order. |
| IPC | `recomp_0052.c`, `0x00526ce0` | Builds `0x001d0044` (literal at `0x00526d2c`) and invokes SVC `0x32`. Runtime handles command `0x001d`. |

This accounts for the reported log `max 3 players, attributes 0x8000`. It is a
chain of game policy, job sizing and SDK construction, not a constant solely in HLE.

### E3. Join, send and receive trace

**Confirmed, join:** local session interface join dispatch is
`0x0025390c` → virtual slot `+0x28` → `0x00287624`.
At the UDS-library end, `0x005022d4` calls `0x004fdc70` at `0x00502460`;
`0x004fdcc4` calls SDK connect `0x00525640` (its continuation is emitted as
`f_00525650`). This reaches `0x00526d5c`, which emits header `0x001e0084`
(literal `0x00526db8`). After joining, `0x004fdcfc` copies NetworkStruct
`+0x1d` into UDS-base `+0x1f`; it checks connection status 9 before accepting
the local connection. The same count must be consistent at all these layers.

**Confirmed, send:** game helper `0x001472a0` chooses targeted sends
`0x00139024` for nonnegative station selectors, broadcast `0x0013917c` for
negative selectors. Both reject application payloads **over `0x500` = 1280 B**.
The broadcast helper reaches `0x001598c4`, supplying station selector `0xff`.
These enqueue through the transport abstraction (`0x0016d984`, virtual output
slot `+0x10`); this is an asynchronous boundary, not a direct game→UDS call.
Local UDS output paths include `0x005031b4` → `0x004fe568` and
`0x00504b18`/`0x00504b9c` → `0x004fee90` → `0x004fdf80` → `0x005265b8`
→ `0x00527160` → IPC `SendTo` `0x00170182` (literal `0x005271d0`).
Both `0x004fdf80` and `0x005265b8` enforce **`0x5c6` = 1478 B** at that SDK
layer (literals `0x004fe130`, `0x00526664`). HLE's 1500 B ceiling is therefore
not the only payload ceiling. PIA/header space must be preserved.

**Confirmed, receive:** UDS input `0x004fe278` calls SDK pull `0x00525280`,
then IPC `0x00526c3c` / header `0x001400c0` (literal `0x00526ca4`).
Local library callers include `0x00502698` and `0x004fdda0`; its control worker
`0x00503674` also pulls directly. Higher-level game receive/ack processing is in
`0x0012f0e8` and surrounding blocks in `recomp_0012.c`; game update
`0x0011c064` handles per-peer queued messages. **Hypothesis:** a complete
transport-channel→game-message dispatch map still needs an instrumented trace;
these asynchronously separated paths are not asserted to be one direct call stack.

**Guest acceptance:** HLE's advertised-count gate is confirmed in E1. Game-side
admission also needs the session job's capacity/buffer, peer initialization,
identity mapping and handshake/ack state below. No single final game-level
"reject fourth guest" predicate was proved; removing a refusal alone would
still leave confirmed undersized storage. Preserve join-ready attributes and
connection events; `mp-local` owns their baseline repair.

### E4. Fixed player storage and masks: concrete hazards

**Confirmed:** `cAppNet` RTTI string `0x00683bc4`, typeinfo `0x0067b2cc`,
vtable `0x00696454`. `0x0010a4f8` allocates **`0x1978` bytes** (literal
`0x0010a590`) and installs that vtable. Initializer `0x00130ac8` clears
`+8` for `0x1788` bytes, then sets three-element byte groups at **`+0x284..286`**
and **`+0x287..289`**. Index 3 in the first group aliases the second group.

| Structure / consumer | Address evidence | Scaling consequence |
| --- | --- | --- |
| Three peer-status words at `net+0x11c + 4*i` | `0x0059c0f8`–`0x0059c134`, `0x0011c5ec`, `0x00146a00` | A fourth status word would land at **`+0x128`**, the first peer-state record. Increasing loop bounds in place corrupts existing state. |
| Per-peer record stride **56 B (`0x38`)**, starting `+0x128` | `0x001468e8`–`0x00146914`, `0x0059c498`; arithmetic `7*i*8` | Message pending/received/suppression bits at record `+0x128`, `+0x130`, `+0x150`, `+0x158` relative to the original net base. Grow/relocate every consumer together. |
| Broadcast scheduling loops exactly three peers | `0x00146928`–`0x00146a04`; `0x0059c478`–`0x0059c4f4`; `0x0059c60c`–`0x0059c690` | `-2` is an all-peer selector in these helpers. They iterate active peers and may exclude self/another peer. Broad `3→6` substitution would also hit unrelated constants. |
| Per-peer/type acknowledgement storage | `0x0012ebe0`, `0x0012eccc` | Indexes **`+0x1174 + 384*peer + 6*type`**; sequence slots also use `+0x15f2 + 128*peer + 2*type`. These regions need a joint layout redesign. |
| Sequence-number bands | `0x00146b10`–`0x00146ba0`, also `0x001469d8`–`0x00146a3c` | Slot 0 wraps within `0x0000..0x0fff`, slot 1 within `0x1000..0x1fff`, remaining original slot within `0x2000..0x2fff`. A fourth slot would reuse the third band without code changes. |
| Three-way station→field-player lookup | `recomp_0014.c`, **`0x00148404`** | Explicit comparisons of bytes at manager `+0x0f`, `+0x10`, `+0x11`, returning 0/1/2 or -1. This is a logical station mapping, not the 16-entry HLE node list. |
| Bulk per-player state clear/copy | `0x00146ba8`–`0x00146efc` | Manager referenced by global `0x006ad948` has indexed profile blocks (50 B, 164 B), vectors and a **`0x1280`-byte** block per player at `+0x3fc0 + 0x1280*i`, among others. Extra storage must reach save/field/UI consumers, not just net-object allocation. |
| Exactly two remote status bytes | `recomp_0059.c`, `0x0059d070`, loop end `0x0059d1ec` | Updates bytes `+0x17a/+0x17c + i` for `i<2` on the session/task object. Counted as a separate two-guest assumption, not confused with the net object's peer records. |

**Masks:** the `&31` and `1<<bit` operations in `0x001468a4` are message-type
bitsets, not a three-bit player mask. The clear loop at `0x0059c64c` covers
63 message indices; it is not a player count. UDS's 16-bit membership mask
already fits six. **No confirmed two-bit on-wire player index was identified.**
Byte-valued station/player fields and the three sequence bands do not establish
one. Packet payload schemas, sentinels, packed actor IDs and every read/write
must still be audited before claiming either a four-player encoding ceiling or
that five/six players can reuse all packet formats unchanged.

## Evidence: what else must scale

### UI, menus, names and map indicators

**Confirmed:** RTTI `cAppUIAvatarFrameMgr` (`0x006807ae`, vtable `0x00690068`)
and `cAppUIAvatarFrameFriend` / `Player` (`0x00681758` / `0x00681772`).
Manager destructor `0x0035bc08` explicitly iterates **three elements of stride
`0x298`** at **`+0x420`**; array destruction at `0x0035bc64` also uses count 3.
There is a separate player frame at `+0x5c`. **Hypothesis:** some of these three
friend frames may also serve NPC companions; this proves fixed HUD storage, not
that the third frame is an unused fourth-player slot. Audit creation/update and
player lookup as well as destruction. Adding three guest frames costs at least
`3*0x298 = 1992 B` of frame objects, excluding child layouts/textures.

**Confirmed, archive:** the custom UI format has 2290 image/layout pairs from
33045/33046, not standard CLYT/CLAN (Phase 1a). Resource **33398** contains
`party_frame_gauge` at byte `0x0c88`. Resource **35246** contains
`warp_icon_multi_vis1`, `vis2`, `vis3` at **`0x1cfc`, `0x1d10`, `0x1d24`**;
no `vis4..6` strings were found in that resource. These are evidence of authored
UI variants, not a decoded pane-count field. A lossless layout writer is not
established by the archive codec; repacking alone does not author extra panes.

Lobby/host list (`cAppUINetHostListTask`, vtable `0x00690a40`), waiting screen
(`cAppUINetWaitTask`, `0x0068f1b8`), trading selectors and map travel menus need
inspection. A list of discovered **hosts** is not the list of players in one
session. Name plates/minimap icon instance counts and exact layouts are
**Hypothesis / untraced**; do not assume duplicating a HUD gauge fixes them.
Tutorial **6842 row 251** confirms travel-to-friends entries in the Map menu;
**21908 row 143** explicitly says maximum three people and needs localization edits.

### Models, animation, pools and guest memory

**Confirmed:** field-player reset `0x00146ba8` touches many indexed guest-state
blocks; avatar and field group classes exist (`cAppFieldUnitGrpMgr` RTTI
`0x006802b7`, `cAppUnitModelAvatarMem` `0x0068153a`). This audit does **not**
establish their live network-avatar capacity, model heap quotas or animation
instance costs. NPC population proves the engine can render several actors,
not that additional controllable replicated avatars fit its player pools.

The port preserves a **32-bit guest address space**, not native C++ objects with
automatically growing containers. `runtime/src/memory.cpp` reserves **4 GiB**
and commits individual pages; `memory.h` fixes heap `0x08000000`, stack top
`0x10000000`, linear heap `0x14000000`, VRAM 6 MiB. Kernel initialization
(`kernel/kernel.cpp`, `CONFIG_PAGE+0x40`) advertises **64 MiB APPMEMALLOC**.
`kernel/svc.cpp::control_memory` accepts ordinary heap allocations only below
`STACK_TOP-0x01000000`, giving a **112 MiB address window** from HEAP_BASE;
this is a virtual bound, not a promise of a 112 MiB application heap. Linear
allocation bookkeeping and GPU address translation are separate; the GPU maps
the old linear range with a 128 MiB window in `video/gpu/gpu.cpp`.

**Hypothesis:** PC guest memory can be enlarged through coordinated kernel
reporting, guest heap initialization/pool sizes and address-map checks. Changing
the reservation or reported 64 MiB alone neither grows fixed player arrays nor
retunes game heaps. First measure guest heap/linear high-water marks and model,
animation, effects and field pools with the original three players. The observed
4864 B/player sync blocks are a lower-bound component, not a full avatar budget.
There is no established RAM requirement for six and no need yet to enlarge it.

### Enemy, loot, quest, Exchange Box and visitor saves

**Confirmed:** area-host class `cAppNetAreaHost` (RTTI `0x0067f4c1`, vtable
`0x0068e6f4`) has associated update logic around `0x002b0444`–`0x002b0f90`
calling the same peer/message scheduling helpers. It checks slot results `<3`
at `0x002b08e4` and `0x002b0948`. Game receive processing at `0x0012fa98`
copies a **`0x170`-byte** message with a **`0x168`-byte** body and can schedule
message `0x28` to other peers. Other messages use different schemas/sizes.
RTTI at `0x00681b72` describes a packet slicer for
`sAppVServerNormSyncDataONE` with capacity **128**, alongside a 64-entry
`cAppFieldLink::sMsg` slicer. Those numbers are template capacities, not evidence
of 128-byte packets or six-player support.

**Hypothesis / required audit:** identify who owns enemy AI/HP, hit validation,
aggro/target lists, resurrection, resource nodes, drops, bounties and rewards;
grow owner/target fields and recipient sets consistently. Validate one death
and one loot grant once per intended recipient. Quest/event state selection is
multiplayer-aware: known `0x001fd7d0` chooses a multiplayer bitset, and native
quest command `0x003aba28` has multiplayer gating. This does not prove that
challenge or reward replication scales. Keep the original co-op restrictions.

**Confirmed:** Exchange Box is real game functionality: **21908 rows 145/147**
name the box, **5768 row 76** announces a placement. Trading task RTTI
`0x0067ff1d` maps to vtable `0x0068f61c` / update `0x003147b8`; selector RTTI
`0x00681378` has vtable `0x00690f50`. **Hypothesis / untraced:** number of
simultaneous depositors, per-peer readiness, ownership/ack arrays and save-commit
sequence. Do not infer an unlimited shared box or atomic trading from the UI.
The six-entry clearing loop at `0x0012eba8` is not proof of six player slots.

**Confirmed:** **21908 rows 115/117** require saving before visit/invite;
**5768 row 13** refuses ordinary multiplayer saves; **21908 row 145** freezes
time and forbids save points. StreetPass visitors are a different feature
(21908 rows 65/81), so visitor-profile class names alone are not proof of
multiplayer save storage. **Hypothesis / untraced:** persistent co-op visitor
records and Exchange Box save behavior. Audit disconnected-player cleanup and
per-profile atomic writes; do not persist six players into another player's
world-save slots. A cap increase does not authorize lifting save/Life/quest gates.

## Network topology and static traffic budget

**Confirmed:** UDS radio emulation and relay forward to room peers; HLE
`handle_data` accepts broadcast or the local destination node. `SendTo` passes
the supplied destination through. HLE does not run world simulation or validate
combat. Game code supports **both station-targeted and broadcast sends**
(`0x001472a0`), keeps independent per-peer ack/sequence state, and has an
area-host role. Therefore it is not justified to call every gameplay packet a
single host-authoritative broadcast stream.

**Hypothesis, best working model:** peer messaging with selected world/area
authority (hybrid). The session host, area host and owner of a character may
differ. Strict host authority for enemy/loot decisions versus peer-authored
updates remains unproved. NEX Internet host-migration strings alone do not prove
local-Wireless migration; that menu is outside this work.

**Confirmed sizes at game send sites:** `0x0012ed9c` sends **20 B**;
`0x0011c9c0` and `0x0011cabc` send **12 B**; `0x00119738` sends **28 B**;
`0x0011995c` sends **16 B**. The `0x170` message above is a larger state body.
Game application send ceiling is 1280 B, SDK ceiling 1478 B, HLE ceiling 1500 B;
do not inflate every message to 1500 B in the normal-traffic estimate.

**Hypothesis / estimate:** a 20–30 Hz stream with 20–128 B of application state
per peer/update is a useful planning envelope (**0.4–3.84 kB/s per stream**),
with 60 Hz as a stress case. This is an assumption, **not a recovered movement
rate or a measured mean packet size**. Frame-to-network cadence, aggregation,
retries, reliable bulk transfers and combat bursts have not been established.
Observed small message sizes support the order of magnitude, not the frequency.

For one unicast per other player per update, sender frame rate is `(N-1)*f`:

| Players | Per sender at 30 Hz | Per sender at 60 Hz | Per receiver at 30 Hz, before UDS destination filtering |
| --- | --- | --- | --- |
| 4 | 90 frames/s | 180 frames/s | 270 frames/s |
| 5 | 120 frames/s | 240 frames/s | 480 frames/s |
| 6 | 150 frames/s | **300 frames/s** | **750 frames/s** |

The last column is `(N-1)^2*f`, since the relay forwards even logical unicasts to
every other member. At six/60 Hz it becomes 1500 received frames/s. If the game
instead aggregates into one broadcast each update, per-sender cost is just `f`
and receiver cost `(N-1)*f`. Neither scenario is asserted to be current behavior.

At six/30 Hz, the unicast assumption gives **3–19.2 kB/s application upload per
player** for the 20–128 B envelope. Worst-case always-full 1280 B messages at
150/s would be 192 kB/s application upload; a size/rate bound, not a forecast.
HLE adds 13 B frame header + 6 B DATA fields; relay adds 5 B, excluding UDP/IP
and SDK/PIA overhead. Host beacons are another 10 frames/s (100 ms interval),
client presence about 1/s; ACKs/retries and other control traffic also consume
the **300/s sustained** budget. Thus six/60 Hz unicast already exceeds the
budget once overhead frames are included; burst allowance is not a solution.

`air.cpp` queues **256 frames**, dropping oldest. At six/30 Hz unicast the
modelled incoming queue covers only **0.34 s**, or **0.17 s** at 60 Hz; these
are stall budgets, not expected latency. `uds.cpp::handle_data` also drops when
each game's bind-byte capacity is exhausted. Instrument frame counts, payload
sizes, bind occupancy, backlog, retries and loss before changing limits or adding
a second reliability layer. No relay rewrite is currently justified by player count.

## Recommended plan and decision gates

1. **Prerequisite: original contract (`mp-local`, ROADMAP S6).** User verifies
   hosting, join, three players, map changes, combat, trade and clean departure
   on isolated profiles. Preserve the original cap until those work. Record the
   revision, mod/DLC digest, log and network baseline. This research delivers no
   executable and does not ask the user to run an unchanged build to test six.
2. **S offline spike: layout/identity/codec proof.** Inventory every consumer of
   the E4 layouts; map station IDs → logical player → actor IDs. Decode and
   round-trip the relevant packet families with IDs 0..5, including sentinels,
   sequence wrap, active masks and departure/rejoin. Identify a complete placement
   for larger peer records, ACK tables, profile blocks and HUD instances. Success
   means no aliasing, truncation or old three-entry reads; otherwise enumerate
   the functions needing replacement before attempting live admission.
3. **R foundation: revision-checked replacement stage.** There is no general
   game-function override ABI (ROADMAP §2). Implement a reproducible wrapper/
   replacement or pre-emission transformation stage keyed to the EU code digest
   and instruction signatures; handle interior entry points and indirect calls.
   Never hand-edit generated C or assume post-recompilation byte patches alter
   emitted code. Relocate/grow structures and all offset users together; a sidecar
   alone cannot fix unchanged guest pointer arithmetic. Reject mixed protocol/
   capacity builds before joining. This is additional implementation scope, not
   an existing `fl_mod.py` configuration option.
4. **M–L four-player spike.** Compile capacity six internally if practical, expose
   maximum four first. Patch the game default/clamp, host advertisement and join
   sizing, slot maps, message/sequence tables and field state; provide bounded HUD
   diagnostics for every slot. Add allocation/slot assertions and network counters.
   Keep save/trade behavior conservative until audited; no global bypass of the
   multiplayer predicate. Deliver its own isolated executable/profiles and exact
   launch commands plus `docs/testing/multiplayer-six-players.md` then stop for
   user gameplay results, as AGENTS requires.
5. **Gate four → five → six.** Four must pass the checklist below, including trade
   and restored saves, before calling it supported. Repeat at five, then six,
   exercising every local/remote slot and host role. If bytes/frames/pools exceed
   budget, reduce redundant per-recipient traffic or tune the proven bottleneck;
   enlarge guest heaps or runtime queues only with measurements. Full delivery
   includes authored layouts/localization and balance, not just four moving actors.

**Future user checklist (after an implementation exists):**

- Start four isolated profiles/identities on the same revision and room; host and
  join in different orders. Every player has a unique name, HUD/icon/actor and
  correct position on all other screens. A fifth join gets a clean full-room result.
- Move/attack/emote with all players; approach/revive different players, enter and
  leave maps both together and apart, travel via friends' Map entries. Repeat
  with each participant hosting; log which station/field slots were assigned.
- Fight one shared enemy to death, collect distinct drops/bounties, check quest/
  challenge counters, and verify each intended award exactly once.
- Exchange Box: simultaneous deposits, one withdrawal race, disconnect during a
  trade, reconnect, then normal exit and reload every profile. No duplicated/lost
  inventory, overwritten identity or visitor world persisted into a local save.
- Leave a middle slot, join again, then lose the host. Expected original-style
  controlled disconnect/cleanup unless migration was separately proved; never a
  hang, wrong avatar or stale slot. Repeat at five/six after each preceding gate.
- Compare quiet-area and combat frame pacing, heap/linear/pool high-water marks,
  per-sender frames/s, bytes, retry rates and queue drops. Later use 30/100/200 ms
  RTT and 0/1/3% loss as test points. Report logs/counters and failures per player;
  no routine packet/queue drops or sustained relay rate-limit saturation.

## Remaining uncertainties and integration

This is a concrete blocking-site inventory, **not an exhaustive reverse-engineered
network schema**. Remaining major gates are compact player/actor fields in all
payloads, final game admission, exact movement cadence, ownership of combat and
loot, live avatar/pool allocation, minimap/nameplate capacity, and transactional
trade/save behavior. These are why four is L–XL and six is XL rather than a
small transport patch. No evidence presently establishes an architectural
impossibility at six, and no evidence presently establishes a safe six-player mod.

Only docs and append-only research symbols change on `mp-six-players`.
`mp-local` also changes `docs/README.md`, `tools/re/symbols_fl_eu.txt`, possibly
`docs/ROADMAP.md`: expect adjacent index/§3 edits and an EOF symbol conflict.
Keep both documentation entries and union appended symbols by address, resolving
alternate names after comparing evidence; never discard its baseline fixes.
The orchestrator/merge agent integrates branches; this branch does not merge.
