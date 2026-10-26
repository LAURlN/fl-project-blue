# Phase 2 — maps, doors and enemies (Fantasy Life EU)

> **Note:** paths starting with `port/` (and `runtime/`) refer to the runtime's source code, which is not part of this package. They are kept as historical research context.

Static research against the Phase 1 EU extraction and `code.bin`, base `0x100000`.
**The map ID is a row number, not the number in `NormalMap_NNN` or an archive ID.**
No game data is committed; no hardware/emulator/port boot test was performed.
`port/` was not changed. Event bytecode belongs to the parallel Phase 1c work;
this document covers placement containers and SCR tables, not opcodes.

## Results and confidence

- **Confirmed structurally:** all 1,015 `0f f1 40 33` resources are placement
  containers. Their 52-byte records and both pointer indexes are decoded.
  `fl_map.py dump/build` round-trips all 1,015 byte for byte. Warp and spawn
  payloads are editable without moving their arrays. Appending cloned warps and
  spawns rebuilds indexes and copies their payloads, behind `--experimental-growth`.
- **Confirmed by code + data:** type 3 = transitions, type 12 = monster spawn
  regions. Monster selection comes from per-area SCRs, reached through **8695**.
  **Correction to Phase 1b:** 8695 is the map → monster spawn table index, **not
  an icon atlas**. Its referenced resources are SCRs, not textures. The old
  `icon_atlas` schema is replaced by `map_spawn_index`.
- **Concrete closed-door lead:** Shopping District model 8748 has
  `map_001_door05`, but placement 22761 has no corresponding type 3 transition.
  Its local bone translation is approximately `(0.977, 2.294, -13.364)`;
  nearest existing transition is 12.48 units away in XZ. Door 01–04 and the paired
  door 06 bones have transitions within 1.62 units. This is static evidence of
  an unconnected door, not a claim to have walked up to it in game.
- **Enemy slice:** East Grassy Plains is map **25**, `NormalMap_148`, bundle 25;
  spawn table **7290**, placement layers **23053–23056**. East Castele is map
  **33**, `NormalMap_306`, a different area. West Grassy Plains is 24/147.
- **Still unresolved:** complete collision/navmesh layout, exact CB/GB/FB and
  `51d00202` semantics, respawn timer/leave-area rules, placement layer selection,
  and some stats/AI fields. Those gaps are not silently replaced with guesses.

## Area identity and resources

Map names/parameters: SCR **5966–5973**, eight Western language variants,
287 × 72 bytes (5969 English, 5973 UK English). Slot order is es-419, fr-CA,
de, en, es, fr, it, en-GB. Fields: name `+0`, ASCII key
`+4`, bundle index `+0x34`; table **8716** is 253 × 48 bytes. Multiple area
rows can share a bundle (notably tower floors). The label suffix and bundle row
must not be used interchangeably with the map row.

Table 8716 `resources[10]`, absolute outer archive IDs (`0xffffffff` absent):

| Slot | Meaning/evidence | Shopping district (map 0) | General goods (map 150) | East plains (map 25) |
| --- | --- | ---: | ---: | ---: |
| 0 | ZMDL geometry | 8748 | 8966 | 10332 |
| 1 | `COL` collision | 8727 | 8961 | 10311 |
| 2 | BPAK material/texture animation (`zmta`) | 8728 | 8962 | 10312 |
| 3 | ZTEX texture collection | 8749 | 8967 | 10333 |
| 4 | BPAK skeletal animation (`zanm`), sometimes empty | 8750 | 8968 | 10334 |
| 5 | `CB01`, camera-related candidate, not fully decoded | 8726 | 8960 | 10310 |
| 6 | First minimap ZTEX; consecutive tiles | 8730 | absent | 10314 |
| 7 | `FB01`, opaque companion | 8747 | 8965 | 10331 |
| 8 | `GB01`, opaque companion | 8746 | 8964 | 10330 |
| 9 | `02 02 d0 51`, opaque companion | 8729 | 8963 | 10313 |

Town/plains minimaps have 16 consecutive 524,416-byte ZTEXs, with embedded names
`map_001_minimap_01_01` through `_04_04` (8730–8745); East plains 10314–10329.
These are image tiles, not navigation meshes. Small interiors often have no
slot-6 image. A replacement room should inherit its donor's behavior initially.

8716 also has a type-9 nested pointer at `+0x28` (variant data, not decoded),
and a related-map halfword at `+0x2c`. Preserve both. There is no identified
standalone navigation mesh in the ten slots; `COL` may contain further topology,
but collision triangles and AI paths must not be equated without decoding it.
Clone matching geometry/collision/companions together for the first room.

Lighting/fog/sky are not yet mapped to named editable fields. ZMDL materials
include explicit time tags (`morn`, `day`, `even`, `night`, `onnight`) and shade,
water and light meshes; ZMTA/animation companions participate. The opaque
CB/GB/FB/51d00202 companions and 8716 variants are candidates for further renderer
tracing, not established lighting schemas. General Goods 8966 even has a `sky`
material: do not assume every sky is a separate global model.

Map parameters `+0x37/+0x38` strongly match day/night BGM indexes in the
77-row **8505–8513** BGM name/sound-ID family: Castele 23/33, East plains 27/34,
shop 56/56, attic 63/63; 255 is absent/inherit. Named `bgm_day/bgm_night` with
**medium** confidence pending consumer tracing. BGM bank/stream replacement is
unnecessary for either initial slice.

## Placement association (separate from geometry)

SCR **8697**, 592 × 40 bytes, associates scripts/placements with content:
`u32 resources[8]@0`, `u16 kind@0x20`, `u16 map_id@0x22`, another halfword
at `+0x24`. `kind == 1` identifies map rows. Map parameters `+0x3e` track this
map-script association ordinal minus one on ordinary maps (map 0 → 8697 row 1,
map 150 → row 106); 45 special-map rows instead contain 65535 despite having
an explicit association. Do not use this as a universal direct index.
`fl_map.py area` searches the explicit kind/map fields rather than assuming order.

| Area | 8697 row | Script pair (slots 0/1) | Placement slots 4/5/6/7 |
| --- | ---: | --- | --- |
| Shopping District, 0 | 1 | 22752 / 22751 | 22761 / 22762 / absent / absent |
| Artisans' District, 1 | 2 | 22764 / 22763 | 22773 / 22774 / absent / absent |
| Castele Square, 2 | 3 | 22776 / 22775 | 22785 / 22786 / absent / absent |
| East Grassy Plains, 25 | 26 | 23044 / 23043 | 23053 / 23055 / 23054 / 23056 |
| General Goods, 150 | 106 | 21266 / 21265 | 21275 / 21276 / absent / absent |
| Unused house A, 154 | 110 | 21314 / 21313 | 21323 / 21324 / absent / absent |
| Attic, 161 | 117 | 21398 / 21397 | 21399 / 21400 / absent / absent |

The two planes slots 4/5 clearly differ in population (ghost regions are in
23055, not 23053); additional slots 6/7 include level-key-100 and alternative
boss data. **Do not name all four files day/night or DLC on/off solely from
adjacency.** Activation needs runtime tracing of the script/resource selector.
Day/night is more than a string ending in `NIGHT` in a group label.

### `0ff14033` container (little endian, file-absolute offsets)

| Offset | Layout |
| --- | --- |
| `0x00` | magic `0x3340f10f` |
| `0x04` | u32 file length minus **0xd4** |
| `0x08` | reserved u16 (preserve) |
| `0x0a` | s16 placement count |
| `0x0c` | s16 map-group count; reserved u16 |
| `0x10` | u32 contiguous placement-array offset (originally `0xd4`) |
| `0x14` | u32 map-group-array offset |
| `0x18` | opaque pointer/word, preserved |
| `0x1c` | 23 × 8-byte per-type indexes: s16 count, reserved u16, u32 offset of u32 placement pointers |

A placement record is **0x34 bytes**:

| Offset | Type | Meaning |
| --- | --- | --- |
| `0` | s16 | ordinal, equals its array index |
| `2` | s16 | map row ID |
| `4,5` | u8, s8 | type, subtype (255/-1 common) |
| `6` | u16 | flags; bit 0 inverts initial enabled state, bit 4 selects linked UID |
| `8` | s16 | type-specific reference: route row / spawn-group row / NPC definition |
| `0x0a` | u16 | unknown, preserve |
| `0x0c,0x10` | u32,u32 | placement UID, linked/overridden UID; `0xffffffff` absent |
| `0x14` | f32[3] | position XYZ |
| `0x20` | f32[3] | region/trigger extents, not always model scale |
| `0x2c` | f32 | yaw, radians |
| `0x30` | u32 | type-specific payload offset; zero allowed for several types |

UIDs encode layer, map, type and local ordinal. Existing type-3 IDs in map 0
start at `0x04000c00`; an unused same-type ID such as `0x04000ffe` is a candidate
for an appended door. Do not copy a UID unchanged. Linked overlays reference
these IDs, so preserve existing ones. The engine masks selected UIDs with
`0x8fffffff`; this is not permission to discard the other bits during editing.

Runtime evidence: `0x5a97a0` type count, `0x5a9758` pointer lookup;
`0x2512a4` returns a 0x44-byte runtime group slot. Type 0 is a locator/data
record, 1 unit/NPC placement, 3 transition, 12 monster region, 13 shop.
Other types include blockers, gatherables and event volumes; their payloads stay
opaque. Records of type 1 do not directly contain the render-model ID: reference
indexes the NPC/unit definition path (e.g. table 5977/5987–5994), then unit resources.

Map-group records are `<s16 map_id,s16 count,u32 groups_offset>`. Each nested
spawn selection group is `<s16 count,s16 choice,u32 placement_pointer_array>`.
The JSON name `choice` denotes a group selector, not an index into its member list
(original values include 20 for a three-member group). Choice -1 processes all
members; a nonnegative selector picks one member using the random
path at `0x3d66ec–0x3d670c`. The type index alone is insufficient for spawning:
new type-12 records also need membership here.

### Transitions: type 3, route table 5965

`reference` selects table **5965** (`map_links`, 218 × 16 bytes); its first two
halfwords are endpoint map IDs, bytes 4/5 transition kinds, bytes 6/7 door
selectors, and the final word contains flags. These are routes, not physical
trigger positions. Runtime `0x357c94` combines the route with type-3 placements
from both endpoint maps. Zero-sized placements can represent scripted travel
anchors rather than walk-in boundaries.

Type-3 payload, **48 bytes**: arrival XYZ `+0`, arrival yaw `+0xc`, auxiliary
volume XYZ `+0x10`, auxiliary extents `+0x1c`, auxiliary yaw `+0x28`, flags `+0x2c`.
The arrival interpretation is strong from paired thresholds/room coordinates;
the auxiliary volume is explicitly read by `0x357c94`. Verify the exact landing
point and collision clearance in a boot test before treating it as final.

Examples: route **13** joins map 2 and map 150 (General Goods). Its town record
is placement **22785 row 7**, at approximately `(16.006,2.06,3.644)`; room record
is **21275 row 0**, trigger `(-2.26,0.05,6.3)`, arrival `(-2.26,0.05,4.25)`.
Route **19** joins map 2 and attic 161; the attic has only one placement,
**21399 row 0**, trigger `(0,0.05,5.47)`, arrival `(0,0.05,3.49)`.
Route **39** joins South Castele map 3 to East plains map 25; additional plains
routes include 43, 121, 125 and 128. The route labels are authoring text and can
retain stale translated map names; use endpoint IDs and paired placements.

### Which Castele doors are unconnected?

The static census below checks door-named bones against all associated placement
layers. Counts include the two bones of a double door separately. A nearby warp
does not prove that its event/story condition permits entry.

| Map | Model | Door bones | No nearby type-3 placement |
| --- | ---: | ---: | --- |
| 0 Shopping District | 8748 | 7 | **`map_001_door05`**, nearest warp 12.48 units away |
| 1 Artisans' District | 8773 | 6 | None (all within 1.27 units XZ) |
| 2 Castele Square | 8798 | 15 | None (all within 1.98 units XZ) |
| 3 South Castele | 9090 | 2 | None |
| 32 West Castele | 11299 | 3 | None |
| 33 East Castele | 11324 | 3 | None |

Door 05 is the concrete candidate for slice A. Decorative doorways baked into a
mesh without a named bone are outside this census. Becoming enterable requires
a type-3 trigger, a route with valid endpoints, a destination bundle, an interior
exit/arrival placement, and compatible script/layer initialization. Adding an
opening animation or renaming a bone supplies none of those links. Interaction
prompts, story locks and scripted door activation remain the script agent's audit.

### Spawn regions: type 12

`reference` indexes the currently loaded area's spawn-group SCR. The placement
position/extents are the region; explicit spawn positions are in a nested array.
Its **24-byte payload**:

| Offset | Type | Meaning/confidence |
| --- | --- | --- |
| `0` | s16 | unknown/selector (usually -1); preserve |
| `2,4` | s16,s16 | maximum/minimum initial count; runtime chooses an inclusive random count |
| `6` | s16 | number of 20-byte spawn points |
| `8` | s16 | capacity/count clamp; also used to initialize spawn bookkeeping |
| `0x0a` | s8 | unknown grouping selector (often -1 or 0–5); preserve |
| `0x0b` | s8 | count of eight-byte conditions |
| `0x0c` | u8 | flags, including special persistence/behavior bits |
| `0x0d` | s8 | level/stat-curve key, clamped 1–200 after runtime modifiers |
| `0x0e` | u16 | unknown, preserve |
| `0x10` | u32 | conditions offset, zero when absent |
| `0x14` | u32 | spawn point array offset |

Each point: XYZ f32 at 0, yaw f32 at 12, signed member/variant selector at 16,
unknown byte 17, flags at 18, unknown byte 19. Flag `4` makes the selector choose
a specific member of the spawn group; otherwise selection uses weights. Point
yaw is retained raw: several original points use 1.0.

Eight-byte conditions remain hex in JSON. Runtime `0x3d65d0` evaluates event,
player/story, mode and other conditions; the exact enum meanings need more
tracing. Most initial plains spawns have no such conditions. The reset/respawn
code also uses save/death lists and callbacks. **No dedicated respawn-seconds
field has been established**; do not relabel count or selector bytes as a timer.
The base layer uses level key 1 even where labels describe a level-6 wolf;
monster stats already differ at that key. It is not a reliable displayed level.

East plains **7290–7298** currently contain 20 groups in each language slot.
Representative rows: 0 Baja Ha (monster 5), 1 Red Wolf (11), 2 Worker bee (138),
3 `スナトカゲ` (35), 6 Ghost (112, label `NIGHT`), 8 `いねむりドラゴン` (161), 10 Coyote
(12, `NIGHT`), 13 weighted 84/81 (20/80), 15 weighted 12/11 (30/70), and 19
monster 253. Resolve localized names through `monster_names`; the group labels
are not runtime conditions. Placement 23053 has 36 monster regions; 23055 has 38,
23054 has 34, 23056 has 37. The group table defines what can be selected, while
those layers define where, how many, and under which conditions.

## Monster definition, models, AI and loot

| Table/schema | Resources | Purpose |
| --- | --- | --- |
| `map_spawn_index` | **8695**, 122 × 8 | map ID + per-area spawn-table resource; row 28 is map 25 → 7290 |
| `spawn_groups` | **6957–8054**, 122 families × 9 slots | 36-byte group rows, eight monster IDs and weights |
| `monster_names` | **6920**, **6940–6947**, 275 × 8 | monster name, u16 unit-resource index, opaque byte |
| monster book parameters | **6921–6929**, 275 × 32 | display position/scale, descriptions and habitat text; not combat stats |
| `unit_resources` | **8706–8713**, **8719**, 1582 × 76 | shared monster/NPC/prop model/animation/parameter bundles and display names |
| `monster_battle_parameters` | named `unit/{mon,bnp}/…/*.uparm01`, 485 resources | 116-byte endpoint rows (keys usually 1 and 100); stats and combat parameters |
| `monster_loot` | **6930**, 556 × 36 | grouped by monster ID@2 and level/special key@0; five normal item slots + bounty item |
| `bounty_stats` | **6783–6791**, 146 × 28 | three bounty turn-in reward items and percentage weights; category-local item order |

The **bounty_stats drop tables are real**, but they do not replace the ordinary
monster-loot table. Resource 6930 has five item IDs at `+0xc,+0x10,…,+0x1c`,
a bounty item at `+0x20`, probability-like bytes at `+4…+9` and further flags.
77/255 and 13/255 strongly suggest 30% and 5% thresholds; the exact roll and
independence are untraced. `0x3328e0` loads 6930; `0x332904` groups records by
monster ID. A custom monster without a bounty only needs ordinary loot entries.
Bounty rewards require a category-7 item plus its parallel bounty_stats row.

**Loot ordering matters:** `0x332904` walks a contiguous block per monster in
ascending monster-ID order; it does not search an unordered list. Preserve this
ordering and level-key order within each block. The current final block is
monster 271; a block for reserve monster 274 goes at EOF. The decompiler also
shows one-row lookahead at block boundaries, so final-block termination/allocation
needs a runtime audit before shipping a new last block. A SCR rebuild does not
establish that contract.

Spawn groups use monster IDs, **not unit IDs**. Example: group 7290 row 1 →
monster 11 Red Wolf → `monster_names.unit_index=12` → unit 12. This is not
universally `monster+1`: monster 253 maps to unit 1385, monster 274 to unit 1406.
Do not derive the unit ID arithmetically.

Unit-resource slot order is:
`model, material_animation, textures, common_motion, battle_motion,
common_action_parameters, battle_action_parameters, common_parameters,
battle_parameters, ai_rules, ai_schedule, common_action_motion,
battle_action_motion, effects, sound_bank, battle_missiles, sound_ids`.
The source named paths establish these roles independently of guesses about numbers.

Concrete Red Wolf (`unit/mon/mon004/0001/`): model **46390**, texture **46391**,
motions **46393/46394**, action parameters **46396/46398**, common parameters
**46400**, battle parameters **46401**, AI **46402/46403**, action-motion metadata
**46395/46397**, effects **46389**, bank **46404**, missiles **46399**, sound IDs
**46405**. The named pack parent is separately indexed by the extraction manifest;
edit leaves so the archive builder propagates changes to their parent.

`uparm01` endpoints: u16 key@0, HP@2, likely SP@4, physical attack/defence@6/8,
magic attack/defence@10/12, likely XP@102. These stat labels have **medium**
confidence, not a fully traced interpolation formula. Red Wolf key 1 has
HP 46, attacks 26, defences 20; key 100 has HP 1280 and combat values 256.
Changing HP at both endpoints gives an isolated first stats test.

AI is not one global integer named "AI type": `uparm02` (28-byte rule records),
`uparm03` (60-byte schedules with labels such as `Sched_FreMode`), plus
`actparm`/`actmot` reference actions and ZANM motion packs. Common `uparm00`
is 112 bytes and supplies model/unit behavior parameters. Preserve a complete
compatible donor set initially. `mon004/0001` is a useful authoring family/variant
path, but no authoritative global family/species enum has been identified.

## Concrete slice A: closed Shopping District door → custom room

Implementation update (2026-10-24): [`mods/castele-house`](../mods/castele-house/)
now builds a 22-resource overlay for door05 → map 154. It uses furnished house
bundle 125 rather than the empty attic shell, keeps the attic's exit-only placement
container with the new shell's paired threshold, and appends route 218. Source,
stacking and validation details: [modding guide](modding-guide.md#how-to-make-a-door-and-a-custom-interior).
Gameplay acceptance remains the user's checklist.

1. Reserve unused **map 154**, `HouseMap_019`, bundle **120** (authoring label
   unused house A). Its bundle is already real geometry: model **9002**,
   collision **8997**, material animation **8998**, texture **9003**, motion
   **9004**, CB **8996**, FB **9001**, GB **9000**, opaque companion **8999**.
   Placements **21323/21324** are empty. First audit scripts **21313/21314**
   and any direct references with the Phase 1c agent; unused labels alone do
   not prove freedom from every scripted reference.
   Both empty placement files retain map-group **98**, despite belonging to
   map 154 in 8697; correct it to 154, including in the empty 21324.
2. For the simplest tiny room, replace bundle 120's slots with copies/references
   to attic bundle **127**: 9065 model, 9060 collision, 9061 ZMTA, 9066 texture,
   9067 motions, 9059 CB, 9064 FB, 9063 GB, 9062 opaque companion, no minimap.
   Keep the geometry/collision pair and companions coherent. Reuse donor
   resources initially; a uniquely retextured room should copy 9065/9066 into
   reserved IDs 9002/9003 and reference those so the original attic is unaffected.
   For furnishing, choose a donor room whose complete placement file already has
   compatible type-1 props/NPCs and move those existing records. Their payloads
   are opaque: this writer cannot append a type-1 record with a payload or safely
   transplant its offsets between files. The attic donor has only an exit;
   independent prop insertion is a later tooling step.
3. In all **5966–5973**, rename row 154 and copy the donor's camera/room
   parameters, retaining its own map key, bundle 120 and map-script association.
   Set BGM candidates 63/63 from the attic for the initial test. Do not change
   unrelated map rows. Keep **8697 row 110** pointing to **21323/21324** in slots
   4/5; replacing those IDs needs no association edit. Scripts **21313/21314**
   may need compatible initialization or an audited donor script. Do not blindly
   copy attic scripts **21397/21398**, which may embed map/route IDs.
4. Append route **218** to **5965**, endpoints `[0,154]`, cloning a simple
   shop/house route's flags/kinds. Door animation selector for shopping door 05
   is a candidate **5**; confirm the bone-selector convention in runtime before
   relying on its opening animation. Instant fade/transition can be the first test.
5. Append a type-3 clone to **22761**, reference 218, unique UID, trigger just
   outside `map_001_door05`. Start near `(0.98,1.5,-12.5)` and adjust against
   collision; bone Y is not floor Y. Set its arrival point on the street clear
   of the door. Create interior **21323** from attic placement **21399**:
   change map ID to 154, route reference to 218, UID to the new map's namespace,
   and the header map-group ID too. Keep **21324** empty initially.
6. Test entering, landing, exiting, repeated entry, camera, save/load outside,
   time change and follower behavior. Confirm route 218 is accepted: the
   resource/SCR counts can grow structurally, but the runtime route limit has
   not been audited. If it is literal-limited, use a verified unused route slot
   or a later runtime patch; do not overwrite a live route casually.

`fl_map.py` can clone/append a warp **from the same source document**. For a new
interior file use the attic's entire placement document as the donor, then edit
map/UID/reference and header map-group ID. After a growth build, dump it again
before editing the clone's now-independent payload. Do not manually copy pointer
offsets between unrelated placement files.

## Concrete slice B: custom Red Wolf variant in East plains

Implementation update (2026-10-25): [`mods/eastern-plains-enemy`](../mods/eastern-plains-enemy/)
builds a 31-resource overlay: the **Thistle Wolf**, monster 274 / unit 1406 with the
Red Wolf's motions, actions, AI and sounds, a copy of the wolf model in leaf 51120
(material renamed to the reserve's texture name), its own texture in leaf 51121, a
full copy of 46401 in leaf 51131 with HP 60 / attack 28 / defence 23, loot (Animal Hide, Animal
Fang, Oak Log), spawn group 20 (Thistle Wolf 40% / Red Wolf 60%) and one new region
in the day layer 23053 and the night layer 23055. Recipe and builder changes:
[modding guide](modding-guide.md#how-to-add-a-new-enemy); gameplay acceptance:
the user's checklist. Findings that correct or
complete the plan below:

- **Displayed names** come from the unit tables 8706–8713/8719 (es-419, fr-CA, de, en,
  es, fr, it, en-GB, ja). 6940–6947 are eight identical copies of developer names
  (`Haneruti`, `Banyikira`); 6920 is Japanese.
- **Monster book** tables 6921–6929 are Japanese in all nine slots: untranslated cut
  data in the EU release. A new monster needs no entry.
- **Layers of map 25:** 0x3d65d0 skips the first placement file (time selector −2) at
  time slot 3 when its caller asks, and spawns the second (selector 3) only at slot 3:
  **23053 = day, 23055 = night** spawns. The Red Wolf (group 15) is in both. The flag
  of 8697 row 26 is **2162**, `発生中：12の試練「王国兵士」` (Paladin "Trial of 12"
  in progress): 23054/23056 are that event's layout, not DLC or post-game layers.
- **Loot termination resolved:** 0x332904 walks monsters 0..274 (literal 275 at
  0x332980) and reads the monster ID of the row after each row; the only other reader
  (0x32246c) stays inside blocks. Rows end at EOF in the shipped file, so the read
  after the last block already lands past the table. `fl_mod.py` now ends every
  changed loot table with a terminator row (monster ID 0xffff) and refuses
  out-of-order blocks. 6930 is the only code literal for the table.
- **Battle-parameter fields:** `experience` (+102) is 65534 in all 1,144 rows; the
  XP-like value that scales with HP is `u_68` (+104; Red Wolf 12, key 100: 384), with
  `u_40` (+64) a second reward-like endpoint. The reserve's 51131 has four rows
  (two placeholder rows after keys 1/100); the full copy replaces them with the wolf's
  two. Spawn group rows are fetched through 0x1fb74c, which bounds-checks against the
  table's own row count, so appending group 20 needs no code change.
- The reserve's own model (mon078/0003, 12 bones with ears) is a different creature;
  its model, texture and battle leaves are overwritten with wolf-based content.
- **Model/texture binding:** in 160 of 1,551 unit model/texture pairs the material's
  texture name differs from the texture's image name, including real monsters
  (*Possessed Dogu*, unit 1250: `mon028_0001_001` vs `mon065_0001_001`), so binding is by
  slot. No two shipped units share a model resource with different textures; every
  re-skin has its own model resource. The Thistle Wolf follows that convention.

1. Prefer an existing unused definition over appending IDs: candidate **monster
   274**, unit **1406**, explicitly labelled dummy/reserve. No spawn-group
   reference to 274 occurs in the 122 base spawn families scanned here; this
   excludes direct script/unit references, which need a separate audit.
2. In monster-name tables **6920/6940–6947**, copy row 11 to row 274, give it a
   custom name, and retain `unit_index=1406`. In unit tables
   **8706–8713/8719**, copy unit row 12 to 1406, with custom display name.
   Reuse the wolf skeleton, both motion packs, actions, AI, sound and effects.
3. Reserve **51131** (the dummy's battle-parameter leaf) for a copy of **46401**;
   point custom unit slot 8 to 51131 and change HP endpoints there. For a visual
   variant, copy wolf texture 46391 into reserved **51121**, set custom slot 2
   to 51121 and recolor with ZTEX tooling; names inside the texture must still
   match the donor model. Model 46390 can be shared. Only copy to IDs whose
   existing users were audited, including named-pack leaf propagation.
   In the inspected bundle tables, 51121/51131 belong only to unit 1406, which
   only monster 274 references; this does not audit executable/script literals.
   Both leaves belong to named pack **51122**. Replace leaves, not that parent
   simultaneously. Reusing all wolf visuals initially avoids texture authoring.
4. Optionally copy monster-book row 11 to row 274 in **6921–6929** with custom
   description/habitat. Append rows in **6930** copied from monster 11's loot
   block, changing `monster_id` to 274, preserving its level keys and ordering.
   There is currently no 274 loot block. Set `bounty_item=0xffffffff` and
   `bounty_threshold=0`. For a deterministic drop test, use an existing ordinary
   material (the wolf uses item **2204**) in slot 0, set its threshold to 255 and
   other item IDs to 0xffffffff/thresholds to 0; verify that 255 guarantees a
   drop before naming it a probability. Use no bounty for the first enemy;
   if one is later added, touch the category-7 item family and **6783–6791** too.
5. Append group row **20** in **7290–7298** (all nine slots): clone row 1,
   `monsters=[274,65535,…]`, `weights=[100,0,…]`, no boss slot. Names like
   `NIGHT` are labels, not enable conditions.
6. For a minimal fixed-layout proof, retarget **one** compatible ordinary spawn
   region in **23053** to group 20 (e.g. row **38**, a single monster-35 region at
   `(55.54,1.75,-12.22)`, capacity 1, in the always-process group). Preserve
   its points/selector until boot-tested. Row 19 is Baja Ha and belongs to a
   random-selection group, so it is a poor guaranteed test location.
   For a genuinely additional encounter,
   append a type-12 clone with a unique correctly encoded UID, adjust its
   position and nested points to a tested walkable patch, set min=max=capacity=1,
   reference 20, and include it in the map-group `choice=-1` list. The available
   point count can remain unchanged with capacity 1. Check the corresponding
   overlays **23055/23054/23056**, linked UIDs and activation before extending
   the change to other time/story/mode layers.
7. Test one kill/drop, disengagement, death persistence, leaving/re-entering,
   day/night and alternate layers. The existing placement trigger geometry and
   explicit points avoid needing a navmesh authoring tool for this first variant.

### Packaging either slice

For offline archive experiments, build SCRs/placements to a separate extraction
copy and use `fl_archive.py build`, then re-extract and inspect the result. Keep
the base extraction unchanged. Do not append archive IDs: all resources above
reuse existing IDs; resource 1 and the outer ID index need no modification.

The native `fl_mod.py` overlay workflow can express schema-backed SCR row edits
and raw placement replacements via `files`. **It rejects `files` replacements
for schema-backed tables**, including new battle-parameter schemas. Its
`copy_from` also only copies a row within the same resource. Thus the full
**46401 → 51131** donor-file copy in slice B currently needs offline repacking,
or a reviewed extension to the mod builder for cross-resource copies with
validation. Do not bypass the check by removing a schema. A narrower overlay
proof can edit the reserve's existing battle rows while keeping their layout,
but that is not equivalent to copying the full wolf parameter file.

`fl_data.py validate` covers existing item/recipe/shop/quest links; it does **not**
validate all new monster, unit, spawn-group, loot-order or transition links.
Explicitly check those IDs, weights, point selectors, paired route endpoints,
UID uniqueness and layer relationships with the inventory/placement tools.
No playable house/enemy overlay is delivered by this research commit. The future
user acceptance steps are in the slice checklist.

## Tools, authoring and validation

```sh
python3 -I tools/fl_map.py area extracted/fl_eu/archive 25 tools/build/plains.json
python3 -I tools/fl_map.py doors extracted/fl_eu/archive 0 tools/build/doors.json
python3 -I tools/fl_map.py monster extracted/fl_eu/archive 11 tools/build/wolf.json
python3 -I tools/fl_map.py dump extracted/fl_eu/archive/_unnamed/23053_*.bin tools/build/spawns.json
# Edit rows and, for appended spawns, map_groups. Keep original and payload offsets.
python3 -I tools/fl_map.py build tools/build/spawns.json tools/build/spawns.bin
# Only for append / map-group edits; runtime acceptance still needs testing:
python3 -I tools/fl_map.py build tools/build/spawns.json tools/build/spawns-grown.bin --experimental-growth
python3 -I tools/fl_scr.py dump extracted/fl_eu/archive/_unnamed/07290_*.scr tools/build/groups.json
python3 -I tools/fl_scr.py build tools/build/groups.json tools/build/groups.scr
python3 -I tools/fl_map.py model extracted/fl_eu/archive/_unnamed/08748_*.mdl tools/build/model.json
python3 -I -m unittest discover -s tools/tests -v
python3 -I tools/fl_data.py validate extracted/fl_eu/archive
```

Shell globs above resolve the hash-labelled extraction filename; use the manifest
for a generic ID lookup. `area`, `doors` and `monster` output IDs and exact paths.
`doors` compares **local bone** XZ positions to placements: it is not a general
skeletal world-transform solver and does not establish accessibility by itself.

The placement writer preserves all unknown bytes and original pointers for
fixed-layout edits; it rejects type changes, resizing nested arrays, inconsistent
shared-payload edits and malformed indexes. Growth retains the original image,
appends a relocated record array, copies new type-3/12 payloads and their known
nested arrays, and rebuilds type/map-group indexes. Unknown payloads are not
relocated or reauthored. It does not resolve possible pointers from opaque
embedded scripts into the old record array. Use growth as an explicit structural
experiment; ordinary edits remain the conservative path. A newly grown document
must be dumped again before changing the clone's payload fields.

Validation performed here: **1,015/1,015 placement byte-identical round-trips**;
**1,611 affected SCR schema round-trips**; real-data append + independent payload
edit proofs for 22761 and 23053; synthetic tests for bounds, fixed fields, shared
payloads, cloning/index/group reconstruction, float-bit preservation through JSON,
room remapping, RTTI previews and ZMDL metadata. **49 tool tests pass** with
`python3 -m unittest discover -s tools/tests`. Reviewed source resources still
match their manifest SHA-256 values. Proof binaries and
`maps-review-validation.json` are ignored under `tools/build/`.
`fl_data.py validate` passed with zero errors.
This establishes tool/data structure correctness, not successful gameplay.

Model inspection pointers:
[Ohana3DS Rebirth Fantasy Life ZMDL importer](https://github.com/gdkchan/Ohana3DS-Rebirth/blob/c50635e82763fad9d1bcc30a905523a1b92d7d1f/Ohana3DS%20Rebirth/Ohana/Models/ZMDL.cs)
reads material records (0xb4), bone records (0xcc) and mesh records (0xc4);
`fl_map.py model` follows its metadata layout. It is an importer, not evidence of
ZMDL export support. [Kuriimu2 ZTEX Load/Save](https://github.com/FanTranslatorsInternational/Kuriimu2/blob/6babcdc3562975f445f258f0b7f1d9bd8e5e2a83/plugins/Level5/plugin_level5/N3DS/Image/Ztex.cs)
preserves the texture-family structure and recalculates names/CRC32 and offsets.
Neither GUI was exercised in this task.

For fully new geometry a Blender → ZMDL writer (mesh/index buffers, materials,
PICA attributes, skeleton/bounds) and a compatible collision authoring path are
still needed; a DAE/OBJ export for viewing does not provide that return path.
Reusing an existing room shell and arranging existing props avoids that blocker.
Moving baked walls in Blender without updating collision would be unsafe even
if a model exporter existed. New animations additionally need ZANM/actmot support.

Reproduce runtime evidence using the Phase 3 headless workflow. Use a separate
copy of the ignored Ghidra project when another agent has it locked, rather than
removing that agent's lock:

```sh
FL_GHIDRA_PROJ=tools/build/ghidra-project-maps tools/re/ghidra.sh tools/build/map-query \
  0x357c94 0x3d65d0 0x3d544c 0x3d6174 0x3d5ae0 0x332904 0x5a9758 0x5a97a0
```

The five Origin Island bundles at archive **11677–11801** use the same map
resource/placement separation. They are useful comparison material, but are not
required assets for either Castele slice. Remaining blockers should be tackled in
order: boot-test fixed placement edits, trace layer selection and route capacity,
then test append; decode collision/render environment only when new shells need it.
