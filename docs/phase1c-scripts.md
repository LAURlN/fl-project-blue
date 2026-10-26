# Phase 1c — events, scripts and dialogue (Fantasy Life EU)

> **Note:** paths starting with `port/` (and `runtime/`) refer to the runtime's source code, which is not part of this package. They are kept as historical research context.

Static analysis of the EU `code.bin`, loaded at **0x00100000**, and the Phase 1
archive. No game, emulator or port was run. `port/` was not modified. Function
names below are research names recorded in `tools/re/symbols_fl_eu.txt`.

The executable has a stack VM with **18 instruction forms** and **700 native
command slots**. Every native slot now has an exact handler address and argument
count in [script_commands.json](../tools/re/script_commands.json). Semantic names
are separately confidence-rated; an exact dispatch address does not imply that
an unknown handler has been understood. The codec covers **462 executable
wrappers, 5,464 message wrappers and 1,015 placement containers** byte for byte.

## Resource families and containers

**Correction to the Phase 1a candidate identification:** `0f f1 40 33` is a
placement container, not an instruction stream. [Phase 2](phase2-maps-enemies.md)
defines its 0xd4-byte header, 23 type indexes, 52-byte records and map groups.
NPCs, enemy regions, doors and script triggers are placed there. Its optional
header pointer at +0x18 and opaque per-type payloads must be preserved; they
are not decoded as ordinary VM instructions by this tool. Older `06/07/0a a1
40 33` resource variants are outside the verified writer's scope.

Both VM and message resources use the same little-endian wrapper:

| Offset | Meaning |
| --- | --- |
| 0 | u32 section count, 2 |
| 4 | u32 section-0 start, 16 |
| 8 | u32 section-1 start |
| 12 | u32 EOF offset, equal to file size |

Section lengths come from adjacent offsets; offsets are **wrapper-relative**.
An SCR section's own pointers remain **section-relative**, as in Phase 1b.
Never decide that `02 00 00 00` means bytecode without examining section 0.

- **Message wrapper:** section 0 starts `13 80 03 1d` (or `MSG `). It holds
  text rows. Section 1 begins with a u32 attribute count; preserve its records.
  Current SCR message variants have either 4- or 60-byte attribute records.
  Ordinary conversation text uses alternating speaker/message rows; a message
  index is a **row index**, not a byte offset or archive ID. The common 60-byte
  attributes correspond to message pairs. Runtime `script_message_resource_load`
  (0x57b26c) installs SCR section 0 and the attributes from section 1.
- **VM wrapper:** section 0 has an entry count followed by entry PCs, then a
  **u16 global-function count and that many u16 PCs**, followed by preserved
  debug/string bytes. Only shared script **21172** has nonzero global functions:
  **66 entries**. Section 1 contains fixed-width instructions plus 0–3 zero
  alignment bytes. PCs count instructions, not bytes.

Observed encodings: **415** wrappers use u32 entries and 5-byte instructions,
**40** use u16 entries and 6-byte instructions, **7** mix u16 entries with 5-byte
instructions. The latter are real resources, not a decoder fallback to garbage.
For u32 entries, low 24 bits are PC and high 8 bits are retained entry metadata;
`0xffffffff` is absent. For u16 entries `0xffff` is absent. In the corpus the
u16 family starts with an absent entry, which the decoder uses to distinguish
it. New resources should clone a matching encoding; creating an ambiguous new
u16 entry-table shape is unsupported. The current interpreter fetch routine
proves the 5-byte encoding; 6-byte resources have structural decoding but their
legacy runtime path has not been traced.

## Interpreter and operands

`script_vm_execute` **0x1f54c4** switches on the instruction opcode. Fetch at
**0x1ff6d4** reads `<u8 opcode,u32 operand>` without alignment and increments
the PC. Legacy instructions are `<u16 opcode,u32 operand>`.

| Opcode | Assembly | Operand / effect | Confidence |
| ---: | --- | --- | --- |
| 0 | `load` | push stack[frame_base[low8] + signed16(operand>>8)] | high |
| 1 | `push` | push literal 32-bit bits, interpreted signed by arithmetic/handlers | high |
| 2 | `address` | push that stack slot's index, for native output arguments | high |
| 3 | `load_index` | replace top with stack[base + signed offset + top] | high |
| 4 | `address_index` | replace top with base + signed offset + top | high |
| 5 | `store` | pop into selected stack slot | high |
| 6 | `store_index` | store top through indexed slot; retains the index slot | high |
| 7 | `native` | command ID = operand>>8; low byte retained (zero at every corpus call) | high |
| 8 | `call_global` | high24 = global-function ordinal; low8 = frame level | high |
| 9 | `return_global` | low8 frame level, high24 argument cleanup; restore calling code | high |
| 10 | `call` | high24 = local PC; low8 = frame level | high |
| 11 | `return` | low8 frame level, high24 argument cleanup | high |
| 12 | `end` | finish current execution path | high |
| 13 | `frame` | set frame-base entry at thread +0x3a | high |
| 14 | `alloc` | advance stack pointer by operand slots | high |
| 15 | `jump` | PC = operand>>8; retain low8 | high |
| 16 | `jump_zero` | pop condition, jump if zero | high |
| 17 | `alu` | sub-operation below | high |

ALU selectors 0–22: `neg add sub mul div mod shl asr inc dec and or xor not
bitnot eq ne lt gt le ge dup drop`. Comparisons are signed; right shift is
arithmetic. There is no separate string-literal push opcode in this set.

Native operands are **not inline after opcode 7**. Push/load them left to right
before `native`; `script_argument` **0x303924** indexes from the argument count
and stack top. `script_result` **0x303880** writes the result slot, and the
interpreter removes the declared arguments while retaining a result if one was
written. `script_output_argument` **0x303944** treats an argument as a stack
index, so use `address`, not `load`, for outputs.

Thread fields: stack buffer +0x34; frame bases +0x38; stack top +0x68; saved
native-call top +0x6a; PC +0x6c; run mode +0x7a; state bits +0x7c. The active
thread is at manager +0x17ec. Handler return 1 means **yield/suspend**, not a VM
boolean result. A waiting handler may rewind PC and restore arguments to retry
next update. Dialogue, fades and item acquisition also suspend through engine
tasks; copying only the final `native` can omit required setup/cleanup.

The initializer **0x3a0fa8** copies ARM C++ member-function pointers into 700
8-byte slots at manager +4. The argument-byte array is at **0x627f78**. All
member adjustments are zero in this build. The research extractor emulates only
that bounded, allocation-free initializer: no handler, services or game loop.

```sh
PYTHONPATH=tools/build/re-python python3 tools/re/script_commands.py \
  extracted/fl_eu/exefs/code.bin tools/re/script_commands.json --check
```

It verifies the complete catalog against the executable without overwriting
annotations. Without `--check`, use a separate ignored output path for raw
metadata. Unicorn is needed only for this research step; the codec is stdlib.

## Native command reference

The full 700-slot address/arity mapping is the JSON catalog. This table covers
the authoring paths verified here. **High** means direct handler/data-flow
evidence; **medium** means the mechanism is traced but some selector semantics
or gameplay behavior remain inferred. Unknown catalog slots keep `cmd_NNN`.

| ID | Name / arguments in push order | Handler | Confidence / meaning |
| ---: | --- | --- | --- |
| 2 | `wait_frames(frames)` | 0x3b0308 | high; u16 frame delay, execution mode 5 |
| 4 | `wait_camera()` | 0x39f138 | high; retry while camera busy |
| 6 | `wait_field_ready()` | 0x3a5350 | medium; readiness predicate |
| 61 | `get_context(selector,&a,&b)` | 0x3a6a34 | high; outputs caller context; selector 9 supplies shop selector |
| 65 | `flag_set(id,value)` | 0x3a0468 | high; 0 clear, 1 set |
| 66 | `flag_test(id)` | 0x39f674 | high; **DLC-aware** save/ECFlag test |
| 90 | `message(row)` | 0x3afad4 | high; calling thread's text + attributes |
| 91 | `message_global(row)` | 0x3b0114 | high; global text object |
| 93 | `message_npc(npc,text_slot,row)` | 0x39cbcc | high; selected NPC text |
| 95 | `message_named(npc,speaker_row,row,style)` | 0x3b0350 | high; speaker -1 uses NPC name; first argument is **not** a resource ID |
| 98 | `text_argument(kind,value)` | 0x3b0a24 | medium; 6 item name, 15 quest title, 0 player name |
| 99 | `message_result()` | 0x39c968 | high; choice result |
| 131 | `object_enable(uid,on)` | 0x3ac6b0 | high; placement UID, boolean |
| 133 | `door_enable(uid,on)` | 0x3ab5a8 | high; same queue mechanism as 131 |
| 134 | `route_select(route,selector)` | 0x3a7860 | medium; route must be **<218** in this handler |
| 141 | `camera_fade(duration,mode)` | 0x3ab35c | medium; camera transition, donor conventions required |
| 161 | `placement_enable(uid,on)` | 0x3a7900 | high; alias of 131 |
| 181 | `item_change(item,quantity)` | 0x399dac | high; positive acquires, negative removes; acquisition yields |
| 189 | `item_result()` | 0x3a66c8 | medium; acquisition state result |
| 200 | `actor_option(actor,option)` | 0x3a7abc | medium; NPC/actor option switch, not a general placement UID |
| 214 | `actor_animation(actor,action,variant)` | 0x3a7a4c | medium; queues actor action; donor actparm/actmot define numbering |
| 251–253 | actor action / timed action / stop | 0x3a4f10 / 0x3a9360 / 0x3a0c00 | medium; signatures in catalog |
| 256–257 | NPC place / place at locator | 0x3a7f78 / 0x3aca08 | medium; NPC ID, **map ID**, position or locator, slot; XYZ in thousandths |
| 258–259 | NPC spawn / spawn at locator | 0x3ad844 / 0x3aec88 | medium; event queue 0x1e; NPC <2792, map <287 |
| 324 | `shop_open(shop,mode)` | 0x39baf8 | high; 0 buy, 1 sell; shop **0 → 8405** |
| 326 | `item_notice(item,quantity,option)` | 0x39e3b4 | medium; acquisition notification/UI |
| 339 | `ui_open_20(selector)` | 0x3a9bd0 | high; different selector/global than the stock shop; not `shop_open` |
| 350 | `screen_fade(duration)` | 0x3b06ec | medium; suspends screen transition |
| 432 | `debug_line(line)` | 0x39c774 | high; retail no-op, compiler line marker |
| 433 | `debug_value(selector)` | 0x39e070 | high; returns zero in retail |
| 580 | `quest_text_load(slot)` | 0x3a0c50 | high; load active quest dialogue |
| 581 | `quest_message(slot,column,option)` | 0x3b1554 | high; columns 0..6; substitutions supplied by engine |
| 584 | `quest_for_npc(npc)` | 0x3aba28 | high; active slot, or -1 |
| 585 | `quest_objective_test(slot)` | 0x3ac944 | high; inventory quality/count or monster counter |
| 586 | `quest_state_set(slot,state)` | 0x3a0d08 | high; 2 accept, 3 complete |
| 587 | `quest_state(slot)` | 0x3a0ccc | high; 1 offered, 2 accepted, 3 pending completion, 4 finished |
| 588 | `quest_reward(slot,selector)` | 0x3a5094 | high; item, quantity, Dosh, points, objective kind |
| 590 | `quest_refresh()` | 0x3ad700 | high; rebuild offers; fixed 400 quest rows |
| 591 | `quest_complete_notice(slot)` | 0x3a7c70 | high; completion UI |
| 592 | `quest_request(slot,selector,alternative)` | 0x3ad730 | high; requested item / quantity / quality |
| 593 | `quest_consume(item,quantity,quality)` | 0x3ae534 | high; remove eligible units, return count |

NPC placement commands take NPC definitions, not raw model IDs. Enemy spawning
uses type-12 placements and Phase 2 spawn tables through **0x3d65d0 / 0x3d544c**;
activation reaches these through the field arrangement/event system. A separate
general-purpose "spawn arbitrary enemy" native command has not been established;
reuse an authored region rather than guessing one of the unknown command slots.

## Worked quest: Furcasso's Humble Beginnings

This is shipped **quest row 285** in **8715**, client **2445 Furcasso**, map
**86 Fluffkin Grotto**. Association **8697 row 53** supplies VM **23759**, text
**23758 + language offset**, and placements **23768/23769**. In 23768, row 1 is
Furcasso: UID **0x042b0400**, NPC reference 2445, approximately `(2.347,0.05,9.811)`.
The local map script falls through the shared talk dispatcher; it does not
contain a bespoke quest-285 reward program.

Parameters: **White Gel 2454 ×3**, any quality (255/-1), reward **Fluffkin Chair
1454 ×1**, points **640**, minimum level **50**, required story flag **1931**
(chapter 8 first-part completion), no prerequisite quest. `u_31=50` participates
in offer selection; this is not a guarantee the quest is offered immediately.
The title/request row is **32670 row 285** (UK English). Dialogue base **31627**;
UK English **31635** has one row with seven string columns.

The complete static flow is shared VM **21172**, global function **31** at PC
**854**, and its local call **1313**:

1. The quest manager builds at most **60 active records**, 0xb0 bytes each,
   with at most **30 accepted**. Eligibility checks include story flag, level,
   earlier quest's completion bit, NPC conflicts, probability and per-group
   quotas (0x260af4). NPC icons/talk eligibility use the resulting active list.
2. Shared talk obtains NPC identity, calls **584** at PC **881**, and passes
   the returned **active slot** to local PC **1313**. This slot is not 285.
   **580** at PC **1350** loads that slot's dialogue resource from 8715.
3. **587** at PC **1365** selects state. Offered state displays column **0**
   at PC **1385**. Choice result **99** is compared with zero. Accept invokes
   **586(slot,2)** at PC **1394**, then column **1**; decline displays **2**.
4. On later talk, accepted state invokes **585** at PC **1417**. For this
   collection quest, 0x26163c counts matching inventory items meeting quality,
   excluding units with the protected/status bits `+0x18 & 0x7ff` set. Without
   three eligible White Gels it displays the reminder column **1**.
5. With enough items it displays handover column **3** at PC **1439**. A zero
   choice obtains quantity/quality via **592**, consumes eligible alternatives
   with **593** at PC **1487**, and issues removal notices via **495**. Cancel
   displays column **5** and retains the accepted state.
6. Success displays column **4** at PC **1509**. **588 selectors 0/1** supply
   chair/quantity, **181** at PC **1528** queues acquisition, **189** checks its
   result, and **326** at PC **1538** handles notification. **588 selector 2**
   supplies Dosh; positive amounts enter commands 178/484. **588 selector 3**
   supplies the points passed to the later notification path.
7. **591** at PC **1557** queues completion UI, column **6** is displayed,
   then **586(slot,3)** at PC **1564** sets pending/completed bits. Later field
   maintenance (0x2616e0) retires the pending record and updates its NPC state.
   Quest 286 can subsequently become eligible via prerequisite 285.

Save quest byte at `save +0x21c9c + quest_id`: bit 1 accepted (`0x2`), bit 2
talk suppression (`0x4`), bit 3 pending completion (`0x8`), bit 4 completed at
least once (`0x10`), bit 5 retired/finished (`0x20`). Do not substitute event
flag 285 for these bits. Event flags and per-quest state are different stores.

**Shipped discrepancy:** English dialogue advertises 200 Dosh, but row 285's
`reward_dosh` is **0xffffffff**. The shared program grants Dosh only for a
positive signed value. This report preserves that difference; text alone is
not evidence of a numeric reward. A cloned quest should make text and table
agree explicitly. No reward edit was made here.

Rows 333–399 are duplicated filler parameters/text, not 67 independently
verified playable quests. Reusing one requires checking its save state and all
cross-references; appending beyond the engine's 400-row loops is unsupported.

## Worked shop: Castele weapons and armour, stock 8405

Map **213 Castele Fine Arms**, not outdoor map 0. **8697 row 169** supplies VM
**21912**, Japanese text **21911**, UK English **21920**, placements **21921/21922**.
21921 row 1 places NPC **171 Shopkeeper**, UID **0x046a8400**.

Script 21912 entry at PC **41** gets context selector 0 and selector **9**;
the latter reads manager **+0x162c** (the shop selector). Flag **70** is the
story condition for opening the Castele shop. If it is not set the script calls
global 14's ordinary interaction path. Once set, PC **64** calls global **33**
with **NPC, shop selector, text base 3**.

Global 33 in shared script 21172 starts at PC **1762**, displays the buy/sell
choice, and invokes **324(shop,0)** at PC **1821** for buying or **324(shop,1)**
at PC **1825** for selling. The context supplies **shop selector 0** for this
stock. The handler opens UI task **0x0e** or **0x0f**; the buy path stores its
selector byte at **0x6ac0a0**. **0x2b0f9c** passes that byte to
`shop_menu_initialize` **0x29fe0c**, then `shop_inventory_load` **0x25d0ac**:
selector 0 → resource **8405**. It never pushes archive ID 8405 into the VM.

Minimal call body inside a correctly initialized interaction:

```text
  push 0x00000000  # shop selector
  push 0x00000000  # buy mode
  native shop_open 0x0
```

For a full shopkeeper clone retain global 33's dialogue/choice, actor facing,
UI suspension and cleanup. Editing stock remains an 8405 `shop_inventory` row
edit; it needs no VM change. Native 339 stores a different selector at 0x6ac200
and opens task 0x20; identifying every UI opener as a stock shop is incorrect.

## Doors, warps and placement-layer selection

An ordinary house door is primarily **route 5965 + two type-3 placements**.
The engine arranges enabled transition objects at **0x357c94**, then crossing
the trigger enters the transition state machine. Arrival selection at
**0x5b56d4** searches loaded type-3 records by route and uses their arrival
position/yaw; map-change requests use **0x5a7048 / 0x5a6f98**. A walk-in door
does not require inventing a "warp" VM instruction. A zero-sized travel anchor
can instead be selected by a scripted travel sequence.

Native **131 / 133 / 161(uid,on)** call 0x232ed8, queue **event 0x1d**, then
0x2559a8 → 0x2ca6cc → **0x32e538** dispatches by `(uid>>10)&31`. Type 3 reaches
**0x357bb0**, looks up that UID in runtime type-2 transition objects, and toggles
its enabled state. The UID's placement type and the runtime object's type number
are different namespaces. Passing map ID 154 or route ID 218 as the UID fails.
Initial activation comes from **`~placement.flags & 1`**; bit 0 clear enables.

The Phase 2 layer blocker is now traced for normal maps:

1. `field_select_layers` **0x5a4a98** enumerates resource **8697**, tests
   `kind@+0x20 == 1`, and matches `map_id@+0x22` to the current map.
2. `required_flag@+0x24` is tested with **0x205da8** when not -1. Flag false/absent
   selects **slots 4/5** (`+0x10/+0x14`); true selects **6/7** (`+0x18/+0x1c`).
3. The first file is queued with time selector **-2** (always); the second with
   **3**. Loaded event threads contribute their association rows as well.
4. `field_queue_layer` **0x2330fc** → queue event **2** → **0x5a3e20** →
   **0x2cb650** → placement-resource loading **0x251528**. Field arrange
   **0x2cac94** compares time selector against **0x17c328**, with -2 unconditional.
   The second file is therefore the time-slot-3/night layer in this path.
   Its final boolean controls spawn/group behavior; preserve the map/event caller.

This establishes the normal-map selector; it does not label every adjacent
placement resource or special scenario as day/night. Other event associations
and linked-UID overlays can affect objects after the base layer loads.

### Applying this to Shopping District `door05` → spare map 154

Keep Phase 2's geometry/collision/route plan; add these concrete activation checks:

- Map **0** association row **1** has no required flag (`65535`), so **22761**
  is always loaded and **22762** is time-slot 3. **A transition cloned into
  22761 with bit 0 clear needs no extra layer-loading opcode.** Use unique UID
  **0x04000ffe** only after checking it remains unused; do not inherit a donor's
  linked UID/bit 4. Adding a baseline door does not require duplicating it into
  the night file. Audit story/event overrides before adding any linked clone.
- Map **154** association row **110** likewise has no required flag, selecting
  **21323/21324**. Keep that row attached to map 154. The reserve VM **21314**
  has only empty lifecycle entries and a no-op debug marker; no discovered
  command turns the spare map's door off. **21313** is its message wrapper,
  not a second competing executable. The stub is useful for a room with only
  an exit; NPCs/quest interactions need a compatible populated script template.
- Clone the complete attic placement into 21323 as in Phase 2, remap its map
  ID/map group to 154, assign a fresh UID and route **218** to both endpoints.
  Clear flags bit 0. Correct 21324's stale map-group ID separately. Preserve
  paired landing positions and the donor's transition-kind conventions.
- To gate the door, insert into the map's setup/lifecycle entry a flag test and
  `door_enable(new_uid,0/1)` **after arrangement**. Entry 2 is the setup hook
  used by ordinary map wrappers; preserve the donor's dispatcher and test when
  it runs relative to arrangement. A later flag change needs reapplication or
  re-entry. Setting a flag alone does not search for a new placement UID.
- Native **134 rejects route 218** because its bound is `<218`. The placement
  arrangement path looks up SCR rows dynamically, so an ordinary appended
  walk-in route does not inherently require native 134. Full route-state/save
  capacity is still unproved. Do not add `route_select(218,...)` and claim it
  works. Opening animation selectors, floor height, collision and save/reload
  remain user acceptance items. `door05`'s bone name alone does not establish
  which route selector animates it.

This research initially included no door mod. The later
[`mods/castele-house`](../mods/castele-house/) implementation now retains this stub
script, appends walk-in route 218 and remaps the paired baseline placements.
Its user checklist covers route/save acceptance,
threshold clearance and opening animation; the game has not been run by the agent.

## Where purchase flag 1963 is tested

Native **66** → **0x39f674** → **event_flag_test_with_ec 0x205da8** is the
script-level connection to [Phase 3](phase3-dlc-mechanism.md): table **5780 row
1963** maps to ECFlag 0, ORed with the save bit; label **5417 row 1963** is
`200_0001(EXパッチ課金済み)`.

The corpus has **37 direct literal tests in 31 VM resources**. Shared script
**21172 PC 834**, global function **28** (entry PC 832), is the small reusable
purchase predicate: push 1963, native 66, return_global. Other concrete calls:
**22324 PCs 2137/2485/2499** (Origin-related story event), **23747 PCs 437/778**,
and **27679 PCs 5520/8854/9533/11586**. These are instruction indexes.

Complete resource→PC inventory (remaining singletons): 22440→6253; 22776→5504;
22841→3006; 22932→709; 23166→1921; 24534→5948;
25644/25674/25704/25734/25764/25854/25884/25914/25944/25974/26004→5948;
27090/27138/27192/27246/27300/27354/27408/27462/27558/27588→5520.
This inventory covers **literal native tests only**; global-28 callers, computed
arguments and recipe/table gates add indirect consumers.
The scanner also reports **8 literal writes** in VM **27669** at PCs
17602/17676/17753/17842/17940/18044/18151/18267: **45 references in 32 resources**
in total. These native-65 save-flag writes are distinct from DLC ownership.

```sh
python3 -I tools/fl_script.py find-flag extracted/fl_eu/archive 1963
```

Do not use 1963 as a writable new quest flag: ownership and local progress have
different lifetimes. Quest eligibility also tests its own story prerequisites;
not every Origin quest body directly tests purchase ownership.

## Authoring tools, validation and limits

```sh
mkdir -p tools/build/scripts
python3 -I tools/fl_script.py disasm extracted/fl_eu/archive/_unnamed/21912_*.scr \
  --archive extracted/fl_eu/archive --language 8 -o tools/build/scripts/shop.fls
python3 -I tools/fl_script.py asm tools/build/scripts/shop.fls tools/build/scripts/shop.scr
cmp extracted/fl_eu/archive/_unnamed/21912_*.scr tools/build/scripts/shop.scr
python3 -I tools/fl_script.py check extracted/fl_eu/archive
python3 -m unittest discover -s tools/tests
```

`.fls` exposes `.labels`, `.entry`, `.globals`/`.global`, `.pool`, `.code`,
instruction labels and padding. Assembler relocates local calls, branches,
entrypoints **and global-function PCs** when instructions move. Native operands
accept catalog names or numeric IDs. Use 32-bit unsigned spelling for negative
literals (`0xffffffff` = -1). Metadata/debug bytes are explicit `.hex`; there
is no hidden original-image preservation blob. Message wrappers expose raw SCR
bytes/attributes with resolved text comments; use `fl_scr.py` for actual text
edits and retain control records. Placement `.object` records are annotated raw
bytes; use `fl_map.py` for typed editing/index reconstruction and growth.

`--archive` resolves literal flag names and local/global message rows. Text slot
0 is Japanese; Western slots 1..8 correspond to text-base +2..9 because the VM
occupies +1; default 8 is UK English. Comments resolve only contiguous literal
arguments, never pretend to evaluate a branch or dynamic stack expression, and
are ignored by assembly. Opcode/arity/label checks are structural; the assembler
is **not** a VM stack/type checker, control-flow verifier or runtime capacity test.

Validation: synthetic tests cover all three observed encodings, branches/local
calls/global/entry relocation, raw attributes, field records, resolved comments,
dynamic-argument exclusions and malformed inputs. Full corpus `check` verifies
**6,941 byte-identical round-trips**. All 700 dispatch/arity pairs were checked
against the executable. No game bytes or decompiler output are committed.

Reproduce decompilation using the [Phase 3 workflow](phase3-dlc-mechanism.md#tooling-no-gui):

```sh
FL_GHIDRA_PROJ=tools/build/ghidra-project-script tools/re/ghidra.sh tools/build/script-query \
  0x1f54c4 0x1ff6d4 0x3a0fa8 0x39f674 0x39baf8 0x5a4a98 0x2cb650 0x32e538
```

`QueryFl.java` additionally supports `r:VA` to rebuild a verified function entry
and `n:VA` to repair a proven erroneous noreturn classification. Check raw ARM
first; incorrect automatic function bodies/prototypes produced several misleading
decompilations in this area. Never remove another agent's Ghidra project lock.
