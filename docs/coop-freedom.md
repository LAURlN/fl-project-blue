# Co-op freedom: what the original blocks in multiplayer, and what we lift

> **Note:** paths starting with `port/` (and `runtime/`) refer to the runtime's source code, which is not part of this package. They are kept as historical research context.

Fantasy Life EU v00 (`0004000000113100`, ExeFS `.code` SHA-256 `a2e10e86…0166b35bb`).
Static analysis only: the extracted archive, `code.bin` (capstone) and the recompiled C were
read; **no game was run**. Roadmap context: ROADMAP §3 / wish 3. In-game
acceptance: testing/coop-freedom.md. Runtime reference:
`port/docs/fl/multiplayer.md` ("Co-op freedom hooks").

Text rows are zero-based; UK English text is the script's text base + 9 (e.g. VM 21900 →
text 21908). PCs are instruction indexes in the shipped resource.

## 1. How the game decides "you are in multiplayer"

There is no single flag. Three layers each check it.

**Session state** (all reads, no side effects):

| Address | Meaning |
| --- | --- |
| `*0x6ad9a4` +8 | network manager flags: bit 0 connected (`0x18a1d0`), bit 2 portal open/hosting (`0x18a1dc`), bit 10 (`0x15e70c`) |
| `*0x6ad948` +0xc / +0xd | own station index / host station index (signed bytes) |
| `*0x6ad948` +0x8700 | members in the session |
| `0x24534c` | host with visitors: connected, own == host, members ≠ 1 |
| `0x246fac` | host, portal open, nobody in yet: bit 2 and (members ≤ 1 or not connected) |
| `0x1a17b0` | visitor: connected, own ≠ host |
| `0x1a16dc` | host or hosting: bit 2, or connected with own == host |
| `0x1dd338` | **any network session**: bit 2, bit 0 or bit 10 (74 direct callers in native code) |

**Script natives** that read it (a bounded scan of all 700 handlers):

| Native | Handler | Result |
| --- | --- | --- |
| **453** | `0x003a86c0` | **multiplayer role**: 0 solo, 1 host with visitors, 2 host with the portal open, 3 visitor. 161 calls in 54 scripts. |
| 297 | `0x003aaa18` | Bounty reward multiplier: 1 solo, else members + 1 (not a gate) |
| 451 / 452 | `0x003a44a8` / `0x003a8b8c` | multiplayer-desk actions for host / visitor (not gates) |
| 584 `quest_for_npc` | `0x003aba28` | request slot for an NPC, **forced to -1 while `0x1dd338`** |

**The visitor's world is not their save.** `fl_event_bitset_get` `0x1fd7d0` returns the
player's own bitset (`save + 0x22244`) only when own station == host station; a visitor
gets `*0x6ad970 + 0xca7c`, a copy of the **host's** world flags that exists only for the
session. Every `flag_set` a visitor's script performs lands in that transient copy, while
Life records, challenge bits, inventory and quest phase bytes stay in the visitor's own save
singleton `0x705f50`. That split is the main reason a gate can be safe for the host and
unsafe for a visitor.

**What can be hooked.** Script natives are called through the VM's member-function table
(`blx r2` at `0x1f5798`), so every handler is an indirect-call target that
`recomp_call_indirect()` sees, like the camera hooks. The executing instruction's guest
address is at *thread*`+0x2c` (stored by the fetch at `0x1f55a8`; the current thread is
manager `+0x17f4`), so a native hook can tell which script site called it. **Direct `bl`
calls into `0x1dd338` and the role predicates are compiled straight into the generated C and
cannot be hooked** without editing generated code, which is not allowed. Native-code gates
(menus, save, room UI) therefore stay as shipped.

## 2. Inventory of every restriction

Search: every SCR text row in all languages for multiplayer/"playing with"/"visitors"/
"friends here"/portal wording (88 UK rows in script text), and every native-453 call site with
both branches resolved. Native-only refusals come from the system tables 5764/5768 and 6280/6284.

| # | Restriction | Guard (where) | Roles blocked | Evidence |
| ---: | --- | --- | --- | --- |
| 1 | **Change Life** | 21172 global 46, PC **5516** (`role ≠ 0` → base+0); all three Guild Offices pass their text base | all | 21908 row 9; 21530 row 1; 21766 row 1. Row 11 (Fledgling rule, `cmd_053`) is separate and kept |
| 2 | **Report to master / rank up** | 21172 global 55, PC **9418** (`role ≠ 0` → 21180 row 59); and each master's own script routes `role ≠ 0` to global 31 (plain talk) instead of global 55: 21290 PC1652, 21924 PC1541, 21984 PC51, 21996 PC1875, 22312 PC7302, 22336 PC7763, 22352 PC2959/2983/3007, 22376 PC1985, 23133 PC6220, 23145 PC7160/7184 | all | 21176/21180 row 59 |
| 3 | Legend / God-rank promotions | 22440 (Goddess ship, map 261) PCs 6270, 6367, 6492 | all | 22448 row 63 |
| 4 | **Requests** (talk, accept, hand in) | native 584 `quest_for_npc` returns -1 while `0x1dd338` | all | quest system; request icons: `0x20bb10` (direct call, also checks `0x1dd338`) |
| 5 | Request offer by story NPCs | 22324 PC1555, scripts using `role ≠ 0` → global 14 (plain talk) | all | 22332 row 77 |
| 6 | **Save** (menu, save points) | native code (system text 5764/5768 row 13) | all | "You cannot save your game during Multiplayer." |
| 7 | Room/menu functions | native code (5764/5768 row 77, 6280/6284 row 0 "Unavailable during multiplayer") | all | letters, furnishing, storage, movies, profile upload |
| 8 | **Sleep / time** | the portal stops time (native); beds 27679 PC8044/8175/9310 and house scripts (24534, 25644…26004, 27090…27588 PC5972/6004) only offer sleep/save when `role == 0`; inns 21172 global 35/36 PC2207/2565 | all | 21908 rows 145/147; 21310 row 31 ("only Rest, time won't pass"); 6842 rows 38–39 |
| 9 | **Companions / party** | entry to multiplayer requires no party and no Bounty (21900 → global 48); recruit NPCs 23759 PC155/275; tutorial 6842 row 26 | all | 21908 row 109; 23767 row 55 |
| 10 | **Housing**: move house | 22324 PC1154 | all | 22332 row 53 |
| 11 | Housing: buy house / holiday home | 21172 global 58 (salesmen 22829, 22877, 22944), 23166 PC1907, 23162/23735 | all | 22837 row 33, 22952 row 67, 23170/23174 row 101, 23743 row 99 |
| 12 | Pets: buy | 21172 global 60/61 (22764, 22829, 22894, 22932) | all | "I didn't realise you were adventuring with someone else" |
| 13 | Mounts: rent horse/turtle/camel | 21172 global 43 (22788, 22865, 22968: `role == 1/2/3`) | all | 22796 row 73, 22873 row 23, 22976 row 71 |
| 14 | **Makeover**: hair salon | 21172 global 37 PC **2604** | all | Salon de Florina "I can't style your hair right now" |
| 15 | Makeover: Timeless Beauty | 23735 PC **35** | all | 23743 row 133 |
| 16 | Makeover: Angelic / Demonic Mirror (house) | 27679 PC **9330** / **9377** | all | SYS003 rows 289 / 295 |
| 17 | Story events and NPC story talk | many NPC scripts: `role ≠ 0` → global 14 (plain talk), skipping their flag-driven event (21218, 21230, 21474, 21734, 22324, 22776, 22841, 22932, 23166, 23747…); master special events (21290 PC1696 etc.) need `role == 0`; main chapters make multiplayer unavailable | all | 27687 row 167; community reports |
| 18 | Ending credits replay | 22440 PC7287 | all | 22448 row 33 |
| 19 | Lunares coin exchange | 23747 PC124 | all | 23755 row 147 |
| 20 | Password plushling | 21172 global 53 (21936) | all | 21944 row 7 |
| 21 | Plushling performance | 22336 PC9592 | all | 22344 row 23 |
| 22 | Guild features / StreetPass desk | 21900 PC523, global 51/52 | all | 21908 rows 89, 275 |
| 23 | Visitor in the host's room: mail, wardrobe | 27679 PC5618, PC6647 (`role == 3`) | visitor | SYS003 rows 173/175 |
| 24 | Leave multiplayer while visitors are present | multiplayer desk (global 49) | host | 21908 row 193 |

Not gates: shops (global 33 skips only a shop-star line in multiplayer), Bounty cash-in
(works, with a members + 1 multiplier), Lily's Bliss song (different line only).

## 3. Per-gate analysis and design

"Lift" below means the hook answers 0 (solo) to native 453 **at that one site**, so the
script takes the branch it takes offline. Everything after that is the game's own code.

### Change Life (#1): lifted for host and visitor

- **Protects:** the changing player's own character (Life id, equipment, skills). No world
  write: global 46 sets no flag; the Life UI is native 340.
- **Naive-lift risk:** peers keep showing the old outfit/weapon until the game resends
  appearance (equipment changes in the menu are already allowed in co-op, so this is
  expected to propagate; unverified). First time in a Life (rank ≤ Novice) runs the Life
  intro (global 45: camera fades, actor moves) and `quest_start` for that Life's first Life
  quest (local event thread). For a **visitor** that intro and quest run in the host's
  world; any flags they set go to the transient copy. The Life record itself is in the
  visitor's own save.
- **Design:** host: lift. Visitor: lift (`fl_coop_change_life_visitor`), because the change
  is character data; the checklist tests a known Life first, then a never-played Life, and
  asks the user to compare both saves after reloading. Risk: **low (host), medium (visitor)**.

### Report to master / rank up (#2, #3): lifted for the host only

- **Protects:** global 55 sets **25 event flags**, calls `quest_start` twelve ways, grants
  items/recipes, stars and rank (Life record `save+0x1fc48`), and plays a local ceremony
  (camera fades, actor animation, messages). Masters' scripts route co-op talk to plain talk.
- **Naive-lift risk:** host — none to their save: flags, ranks and challenges are all the
  host's own. A visitor would get the rank and items in their own save but the 25 flags in
  the transient host copy: on the next solo load the rank is up while the "already told",
  unlock and Life-quest flags are missing (repeated ceremonies, stuck Life quests).
- **Design:** host only; visitors keep the original refusal. All 13 master routing sites
  plus global 55 and the three Goddess-ship promotions are one gate. The ceremony is local
  to the host's screen; visitors only see the host standing at the master. Risk: **low–medium**.

### Requests (#4): lifted for the host only (talking, accepting, handing in)

- **Guard:** native 584 returns -1 while any session is active, so request NPCs only chat.
- **Design:** the hook replaces native 584 for the host with the identical computation
  without the `0x1dd338` term (same helpers: `0x20cb24` slot for NPC, `0x20cbc8` state,
  `0x20baf4` accepted-count limit, `0x20ce58` disabled check), so slot, state and limits
  are the game's own. Quest bytes (`save+0x21c9c`) are the host's save. Visitors keep -1:
  their offers depend on world flags they only see as the host's copy.
- **Known limit:** the request **icon** over NPC heads (`0x20bb10`) is a direct call with its
  own session check and stays hidden in co-op: talk to the NPC you know has your request.
  Story-linked request steps that need NPC events stay blocked by #17. Risk: **low–medium**.

### Makeover (#14–#16): lifted for host and visitor

- **Protects:** the player's own avatar/appearance (and, for the Demonic Mirror, the
  player's own stat allocation, native 565). Timeless Beauty sets one flag (its first-visit
  letter), harmless if it lands in a visitor's transient copy (they see the intro again).
- **Naive-lift risk:** peers may keep the old face/hair until they rejoin. No save risk.
- **Design:** lift for all roles. Risk: **low**.

### Kept, with reasons

| Gate | Why it stays |
| --- | --- |
| Save (#6, #7) | Native code, not hookable. Even with a hook: a host save mid-session would persist session-only state (Exchange Box contents are lost on exit, furniture "placed during the multiplayer session" must be removed, frozen time), and a visitor's save would mix their character with flags that belong to the host's world. Saves are the one thing that must not be risked. |
| Sleep / inns / time (#8) | Opening the portal stops time for everyone; there is no time sync to the visitors' copies. A host sleep would advance the host's day (NPC schedules, spawns, shops) under visitors whose world copy does not advance: desync. Needs a host-authoritative day change, i.e. new net messages. |
| Companions (#9) | AI party members are not part of the co-op player state; multiplayer cannot even start with a party. Replicating companions is a new feature (XL). |
| Housing (#10, #11), pets (#12) | Change the host's rooms, doors and owned properties while visitors may be standing in them (map reload under a peer). Pets live in the room. |
| Mounts (#13) | Rentals spawn a mount actor that peers do not replicate. |
| Story / NPC events, credits (#17, #18) | Cutscenes and story events are local event threads with map transitions; peers are not synchronised, and a visitor's flags go to the transient copy. The game also refuses co-op during main chapters. |
| Lunares, password, performance, Guild features (#19–#22) | Low value or online-service features; not traced far enough to lift. Candidates for later (Lunares: host only). |
| Visitor in host's room (#23), leave while visitors are present (#24) | The host's private objects; ending the session under visitors would drop them. |

## 4. Order (value / risk) and status

| Order | Gate | Status | Roles | Setting | Risk |
| ---: | --- | --- | --- | --- | --- |
| 1 | Change Life | **lifted** | host; visitor | `fl_coop_change_life`, `fl_coop_change_life_visitor` | low / medium |
| 2 | Report & rank up (incl. Legend/God) | **lifted** | host | `fl_coop_report` | low–medium |
| 3 | Requests | **partially lifted** (no icons) | host | `fl_coop_requests` | low–medium |
| 4 | Makeover (salon, Timeless Beauty, mirrors) | **lifted** | all | `fl_coop_makeover` | low |
| – | Save, sleep/time, companions, housing, pets, mounts, story, credits | kept | – | – | high or not hookable |

All settings are **on** in this build and live in `settings.ini` and the launcher (Fantasy
Life section). With all of them off the hooks return before touching anything, so the game
runs exactly as shipped. The settings are part of the LAN compatibility fingerprint, so peers
with different co-op settings refuse each other just like peers with different mods.

## 5. Implementation

Runtime only (`port/runtime/src/games/fantasylife/coop.{h,cpp}`); **no resource is
replaced**, so it stacks with every overlay, including story-skip, which replaces 21172 and
27679 (all four of those sites still match there, at their relocated PCs).

- `tools/fl_coop_gates.py` is the single source of the 22 sites. Each pattern is the 16
  instructions around the call with branch operands masked; `check` proves each pattern
  matches only its gate's sites in the whole corpus, and reports the stacked overlays.
  `generate` writes `coop_sites.inc`.
- The native-453 hook reads thread `+0x2c`, compares the masked window, asks the game's own
  role predicates, and only for a matching site, an enabled gate and an allowed role writes
  result 0 (the game's own `0x303880`). Every other call runs the original handler.
- The native-584 hook (host only, setting on) reimplements the handler minus the session term.
- Activation is pinned to the EU v00 code SHA-256 and refuses any other image.

## 6. Open questions for in-game testing

- Do peers see the new Life's outfit/weapon immediately? (If not: leave and rejoin.)
- Does the Life change menu (native 340) or the master ceremony have a native co-op check of
  its own? If a lifted gate leads to a different refusal, report the exact text.
- Visitor Life change into a never-played Life: does the visitor's solo save afterwards
  behave (intro not stuck, first Life quest available)?
- Does a host rank-up ceremony stall waiting for anything while visitors are present?

## 7. Offline verification (2026-10-25)

- Port `coop-freedom` 238cdac, Release `-O3 -g1`, `build/windows-native` in the port
  worktree: `ctest` **10/10** pass (shader, geometry, pica, camera, **coop**, controller,
  multiplayer local/relay/lan, lan mesh). `fl-coop` drives both hooks against a scratch
  guest with stand-in game functions: every site × every role, relocated branch operands,
  non-site calls, a wrong instruction pointer, unreadable threads, every setting off (no
  guest read at all), the request helper order and refusals, the fingerprint and the
  revision pin. `fl-controller` round-trips the five settings.
- Main repo: `python -I -m unittest discover -s tools/tests` with `FL_EU_ARCHIVE` (and
  `FL_PORT_SRC`): **115 tests OK**, including `test_fl_coop_gates.py` (22 exact sites,
  survive the merged story-skip/Castele/Thistle Wolf/Wooden Sword overlays, generated table
  pinned and equal to the port file).
- Not run in game. Binaries: `fl_eur.exe` SHA-256 `d7874cfa…60c03`, `clockwork-relay.exe`
  `4efd4bb1…7e5f1` (build version `mp-lan-238cdacfea9d`).
