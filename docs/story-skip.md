# Free Life: story-skip implementation and S7 audit

Status: **experimental user-test candidate**, EU v00 only. Built and checked
offline on 2026-10-25; no game was run. This implements roadmap wish 1 / spike S7.
Gameplay acceptance, NPC schedules and the chapter-end landing still need the
user checklist. Do not label it a finished remaster option
until that checklist passes.

**Version 3** restores the weapon and Life skills that the twelve intro quests
teach. Free Life now selects each Life, grants its rank 1 and restores your
current Life; see [Weapon and Life skills](#weapon-and-life-skills-version-3).

**Version 2** adds two things on top of the base skip: it completes the Origin
Island story when the game itself reports the expansion as owned (the entitlement
is only read, never forged), and it fixes the settlement music that used to keep
playing after the Bliss report. Both are authored-script only; no runtime,
save-editor or entitlement change is involved.

## The option

`mods/story-skip/mod.json` enables a **Story Mode / Free Life** choice immediately
before the first dream scene, after character creation and Life selection. Story
Mode is first/default; cancellation follows Story Mode. The ordinary system
message window and SCR two-choice control are reused. New copy covers all nine
language slots; translations need human review.

Free Life completes the base story and its 39 Flutter requests, completes all
twelve Life introductions, and starts all playable Lives at **Novice (rank 1)**.
Their initial challenge is completed but unreported. The first normal master
report can earn Fledgling; higher ranks and challenges remain normal progression.
The player's selected Life, level, Dosh, inventory, equipment, and purchased Bliss
bonuses are not overwritten. The guild's separate `rank <= 1` refusal is bypassed
only for a Free Life save, using reserve flag **49**.

The skipped quests contribute **8,000 Bliss** through the game's normal Bliss
settlement UI, including its ordinary bonus milestones. Bag capacity, pets, mounts,
storage and other bonuses remain choices, not forced purchases. Real estate and
holiday-home offers become available; this does not buy every house.

The base world's routes, transport, shops and guild features use the completion
flags below. Base-game quest 35 is the ending; **1931/1932 are the two DLC chapter
completions** and are written only by the Origin Island part of the preset, never
by the base one.

When the expansion is owned, Free Life completes the Origin Island story as well:
its two chapters (159/160), its fourteen requests (118–128, 164–166) and their
access flags, plus **4600** more Bliss through the same settlement report, for
**12600** on a fresh Free Life save. Ownership is whatever the game itself
reports (`flag_test 1963`, the EC-backed and write-protected entitlement flag);
the overlay never writes 1963/1968, never replaces table **5780**, never touches
ECFlag at `0x748a24` and never registers the DLC. Without the expansion the save
behaves exactly as version 1 did. See [Origin Island story skip](#origin-island-story-skip-version-2).

## Files and architecture

`tools/fl_story_skip.py` is a source-only generator invoked by `fl_mod.py` through
`fl_mod_content.py`. The mod manifest adds `"story_skip": {"version": 3}`. No
new runtime command, generated-C edit, save editor or entitlement hook is needed.
Existing generic mod operations keep their behavior. Bad versions, unexpected
base hashes, switch/branch anchors and message layouts fail the build.

The overlay changes twelve physical archive IDs:

- **27060**: first-dream event, original PC **5133**. The original setup global 6
  remains in place. Story Mode falls through to the original instructions. Free
  Life runs its preset and uses normal `chapter_exit(1)` / `quest_complete(-100)`
  cleanup. A raw map warp kills its script thread and cannot safely be followed
  by completion; it is deliberately not used.
- **27679** (SYS003): the Origin Island part. The preset is inserted at PC
  **5519**, directly after the shipped story-offer function's `alloc 2` and
  before its first test, so the checks that follow already see terminal state.
  No original instruction is replaced or reordered; only branch targets, entries
  and globals relocate. Version 2 is the first release that replaces this
  resource, so it conflicts with any other mod that edits SYS003.
- **21172**: four instructions before the guild's original conditional branch
  to PC **5668**, changing refusal to `rank <= 1 && !flag49`. Global function
  addresses, entries and branches relocate through the existing assembler.
- **27059**, **27063**, **27066**, **27069**, **27072**, **27075**, **27078**,
  **27081**, **27084**: system prompt in unused message pairs 566/567 and
  568/569. The nine quest-language message banks have a **three-resource stride**
  after Japanese, unlike ordinary map messages. Other rows and attribute records
  stay unchanged. Only these two speaker attributes become `-1` (system).

The extraction, archive, base runtime and original generated code are unchanged.
All derived bytes and decompilations stay under ignored build directories.

## Auditing the post-story flags

Generate a reproducible report from the original extraction:

```sh
python -I tools/fl_story_skip.py \
  "<project root>/extracted/fl_eu/archive" \
  tools/build/story-skip/audit.json
```

The generator pins SHA-256 for the shared script, opening script, **SYS003 27679**,
Bliss ledger and challenge table. It decodes SYS003's literal completion switch
at original PCs **10333–10592** and selects the case for each skipped chapter,
Flutter request and primary Life introduction. Within each selected case it
records only contiguous literal `flag_set(id,1)` calls, with their original PC
and quest ID. This is not a union of every write in a chapter, which would include
temporary cutscene and contradictory state. The report records every source PC.

There are **75 completion/access flags**, plus marker **49**:

```text
0–20
50,51,59,60,68,69,70,71,72,73,75,77,78,79,80,91,108,117
120,121,122,123,124,125,126,127,129,130,131,132,133,134,135,136,
137,138,139,140,142,144,145,146
239–250
```

Meanings and boundaries:

- **0–6**: base chapter endings; **7/8**: opening quests; **9–20**: twelve Life
  introductions. Life ending movies **28–39** are not claimed.
- **50/77**: change Life / guild functions; **51/71**: real estate / mansion
  listing; **59/60**: holiday-home offers; **70**: Castele shops.
- **68/69**: two-/three-kingdom airship routes; **72**: Robin's aircraft;
  **78–80**: regional garages; **117**: guild warp from request 79's shipped
  completion case. This LINK-era guild feature is not Origin Island entitlement.
- **120–146**, as explicitly listed: plains, Snowpeak summit, Elderwood and Great
  Spirit routes, Nautilus/palace/lighthouse/holiday-region barriers, desert valley,
  repaired engine, ruins and post-story travel states. Reserved holes are excluded.
- **239–250**: base regional map visibility. These are not the same as doors.

Eight deliberate additions are listed separately in `EXTRA_FLAGS`:
**73** party feature; **75** Dark Tome library route (normally level 35);
**91** Other Requests; **108** post-story world;
**132** Lunares route (normally unlocked by SYS003 at level 40);
**139** restored Flightstone; **144** Gigante ruins; **249** summit map visibility.
The helper-derived flags are stronger evidence than these additions. Gate 144 has
a rank-dependent SYS003 writer at PC 10884; 139/249 are based on shipped labels
and access role, not a proven final-chapter write. No literal VM writer for 139
was found. Their effects require user checks.
No blanket flag range is set, no door/native predicate is globally forced true,
and no level or Life-rank cap is removed.

Quest phases are completed with native **62** for **1,5,10,15,20,25,30,35**, Flutter
**79–117**, and all introduction stages **43–78**. The currently active opening
quest **0** is completed last by native **41**, which also tears down its active
record. Native 62 queues the game's normal end callbacks; these can produce normal
story mail and associated effects. Phase is not the localized chapter-label table.
Starting/chapter-ready flags 21–27 do not need to be fabricated when phases and
completion flags are already terminal.

## Life and Bliss records

Runtime Life IDs are **2,3,5,7,8,9,11,13,14,16,17,18**. Primary intro quests are
respectively **55,46,67,58,76,49,64,73,52,70,43,61**. The other two records in each
three-quest block are introduction stages, not extra ranks. Native **173(life,1)**
uses the normal rank setter. Its rank-1 skill grant (table 08493) applies only to the
Life that is current when 173 runs (the intro quests select theirs with **171** first),
so version 3 selects each Life before its 173. Rank 0 is Amateur, 1 Novice,
2 Fledgling (text family 5910–5918).

The twelve rank-1 challenges in 5827 are
**124,202,345,494,567,654,794,943,1030,1168,1255,1329**. Native
**87(challenge,1,0)** marks each achieved/notified/unreported, matching the shipped
intro-skip helper (e.g. **26280**, original PC **4554** onward). It does not open
the game's automatic tutorial rank-up screen. A master report remains available.

Bliss parameters are in **5791**, Western languages **5802–5809** (255 × 28-byte
rows). Objective type **35** means a story/request quest. Parameter 0 is its
quest ID; reward is u16 at **+0x16** (`c03`); **+0x1a** (`c06`) is entitlement flag.
Filter **type 35 + required flag 65535**: precisely 47 base-game records, with
the same amounts in all nine languages:

| Bliss row | Quest IDs | Bliss per row | Subtotal |
| --- | --- | ---: | ---: |
| 0–7 | 0,5,10,15,20,25,30,35 | 10,50,100,200,300,400,500,1000 | 2560 |
| 137–140 | 79–82 | 10 | 40 |
| 141–146 | 83–88 | 25 | 150 |
| 147–151 | 89–93 | 50 | 250 |
| 152–157 | 94–99 | 100 | 600 |
| 158–163 | 100–105 | 150 | 900 |
| 164–168 | 106–110 | 200 | 1000 |
| 169–173 | 111–115 | 300 | 1500 |
| 174–175 | 116–117 | 500 | 1000 |

Native **79(row,1,0)** marks each achieved/notified/unclaimed. Native **344** then
opens ordinary settlement. **0x2eb48c** sums unclaimed rows' rewards, sets their
claimed bits and updates the accumulated Bliss total; it also calculates normal
bonus milestones. The generator does not add 8000 independently, avoiding double
credit when Flutter is visited later. Ordinary exploration achievements can add
their own Bliss. Reserve flag 49 is written after synchronous initialization,
before settlement; rerunning the authored branch cannot reset claimed bits.

## Weapon and Life skills (version 3)

Each intro quest ends by granting its Life's rank 1 skills. Version 2 set the
ranks but skipped those grants, so a Free Life character had no Longsword,
Archery or Magic proficiency. Version 3 mirrors the intro in the authored branch:

```text
for each Life L (LIVES order):
  cmd_171(L)     # make L the current Life (Life intros do this first)
  cmd_173(L, 1)  # rank setter: grants L's rank-1 skills while L is current
cmd_171(original) # restore the Life the player chose (read by cmd_172)
```

The original current Life is read with **172** into local **0x201** before the
loop; the opening function does not otherwise use that slot. Story Mode never
reaches this code. Each Life is set once, so each rank-1 grant happens once.

Evidence (archive, script, PC):

- **Intro completion:** the twelve Life intro scripts each run `cmd_173(L,1)` near
  their end, after `cmd_056`/`cmd_078` (e.g. **26148** PC 10754 for Life 11,
  **26568** PC 11891 for Life 9, **26412** PC 10425 for Life 2). Life intros start
  with `cmd_171(L)` (e.g. **21302** PC 2 for Life 2 / quest 55; **21254** for Life 8).
- **Current-Life gate (inferred):** the rank setter (**0x5671d0**, native 173
  handler **0x39ea54**) reaches its skill path (`fl_life_rank_set`'s `0x1d6d34` call)
  only when the provider in slot 3 (`0x1fb528`) equals the Life being set. Native
  **171** (`0x39a584` -> `0x567908`) writes the current-Life byte at save
  `+0x1fcc8`. The gate is decoded from generated C, not confirmed in game.
- **Shipped intro-skip helper:** the skip block present in about 111 Life/NPC
  scripts (e.g. **26280** PC 4554-4711, **24444** PC 4550-4711) reads the current
  Life (`cmd_172`), marks the rank-1 challenge (`cmd_087`), then calls
  `cmd_481(life, cmd_174(life))`. It grants only for five craft Lives (5, 8, 11, 13,
  16). Combat and field Lives do not use it, so version 3 does not emit 481; see
  the open point below.

Skill IDs and owning Life come from table **08493** (EU English; column **c05** is
the owning Life, **c02** the type: 0 field, 1 combat, 2 craft). Combat skills
owned by a Life, with the Life that owns them:

| Life (runtime ID) | Combat/field skills owned (table row) |
| --- | --- |
| 3 | Archery Skill (27) |
| 9 | Longsword Skill (32), Shield Skill (33) |
| 14 | Greatsword Skill (35) |
| 17 | Wind Magic (26), Earth Magic (29), Fire Magic (30), Magic Skill (34), Water Magic (36) |
| 2 | Fishing (8) |
| 7 | Woodcutting (12) |
| 18 | Mining (15) |

Craft skills by Life (c05): 5 Armoursmithing (10), Metal Tool Smithing (11),
Smithing (20), Weaponsmithing (23); 8 Misc. Tailoring (2), Garment Tailoring (4),
Sewing (18), Fabric Tailoring (21); 11 Alchemy (1), Accessory Alchemy (0),
Compound Alchemy (14); 13 Cooking (5), Meat Cuisine (13), Seafood Cuisine (17),
Egg & Veg Cuisine (22); 16 Carpentry (3), Furniture Carpentry (9), Tools
Carpentry (24), Weapons Carpentry (25). Dashing (6) and Sneaking (19) have c05 254
(all Lives). Dagger Skill (28) has no owner (255).

These tables list the skills each Life owns. They do not say which of them rank 1
grants. The game's own grant decides that, so the authored branch does not hard-code
per-Life lists.

**Open point.** Native **481(life, rank)** (`0x3a4750`) is the only skill-related
native in the shipped skip helper. It looks up a (life, rank) row (`0x5af5fc`), shows a
notice (`0x23875c`) and sets three save flags. The row contents are not decoded, so
481 is not the sole grant path and is not emitted. Check in game (testing checklist).

## Origin Island story skip (version 2)

The expansion's story is base-story episode 8, *Tale of Lunares: EX 1/EX 2*
(chapter-label rows **159/160**), plus a fourteen-request continuation of the
Flutter line (**118–128** and **164–166**). SYS003's completion switch has a case
for each of them; the generator decodes the case for every quest and pins the
contiguous literal `flag_set(id,1)` writes with their original PCs, exactly like
the base audit. Quest **118** is the story start and has no completion case.

| Quest | Literal writes inside its SYS003 case (flag @ PC) |
| --- | --- |
| 119–124 | 42 @ 10217, 43 @ 10223, 44 @ 10229, 45 @ 10235, 46 @ 10241, 47 @ 10247 |
| 125 | 48 @ 10253, **147** @ 10258 |
| 126–128 | 1970/1988 @ 10264/10269, 1971/1998 @ 10275/10280, 1972/1999 @ 10290/10295 |
| 164–166 | 1973/2000 @ 10301/10306, 1974/2001 @ 10312/10317, 1975/2002 @ 10323/10328 |
| 159 (EX 1) | **1931** @ 9842, **154** @ 9847, **155** @ 9852, **156** @ 9857, 158 @ 9862, 159 @ 9867, **1928** @ 9872, 118 @ 9877 |
| 160 (EX 2) | **1932** @ 9883, **157** @ 9888 |

The preset writes those **30 flags** plus phase 3 for the **16 quests**. The
barriers it opens are exactly the ones a completed chapter opens: **147** (the
route into the expansion's region) and **154–159** (the God Island/god-beast
access flags). Everything else in that range belongs to the God Tower's own
progress function, not to a completion case, so the preset must not write it and
the audit fails the build if it ever does: **148/149** are the level gates (75
and 100), **151/152** their notified companions, all written at SYS003 PCs
10722, 10746, 10753 and 10777 next to the tower object enables, and **153**
belongs to the PC 8031 route. Guild Novice handling, the opening preset and every
base flag are unchanged.

Bliss: type-35 rows whose required flag is not 65535 are the expansion's. Exactly
sixteen rows match and they are disjoint from the 47 base rows:

| Row | Quest | Bliss |
| --- | --- | ---: |
| 200–207 | 118–125 | 350 each (2800) |
| 223/224 | 159/160 | 500/1000 |
| 225–230 | 126–128, 164–166 | 50 each (300) |

**4600** Bliss, marked achieved+notified+unclaimed with native **79** like the base
rows and credited by the same single settlement. Nothing is added by the
generator, so there is no independent credit and no double credit; the repeat
runs in the tests grant nothing.

### Entitlement is only read

Table **5780** row **1963** is EC-controlled (`c00 = 0`) and write-protected
(`c01 = 1`). The generator pins the hash of 5780, asserts that row 1963 keeps that
shape, asserts that no flag in the Origin Island set is EC-controlled, and asserts
that no `flag_set` in any replaced script touches 1963/1968. It never replaces
5780 and never touches ECFlag at `0x748a24`; `f_00205da8` keeps combining
entitlement and save flags normally. The DLC CIA is still what makes the
expansion playable, and the region, its maps and its data are the shipped ones.

### The shipped gate, and a DLC installed later

SYS003 PC **5518** is the game's own story-offer function:

```text
flag_test 1963 == 1                       # expansion owned (EC-backed)
&& quest_phase(116) == 3                  # requests 116/117 complete
&& quest_phase(117) == 3
&& quest_phase(118) == 0                  # story not started yet
&& player_level() >= 50                   # native 569, SYS003 PC 5536
&& no blocking UI / movie                 # natives 52, 53, 453
  -> cmd_367(); quest_start(118)          # PC 5559, native 40, starts the story
```

It is reached from SYS003's own update: PC 12003 compares two context/map values
(`g257` and `g513`) and, when they match, PC 12016 calls this function. That is
the point where the story "first becomes reachable". The preset is inserted at
PC **5519**, immediately
after the function's `alloc 2` and before the first test: the writes therefore
land before the checks are evaluated, phase(118) is no longer 0, and the original
`quest_start(118)` does not run. Nothing is skipped or jumped over, so if the
preset is already applied the function still evaluates and simply finds nothing
to do.

The entry test is `flag_test 49` (Free Life marker) `&& flag_test 1963`
(expansion owned) `&& !flag_test 1932` (EX 2 not yet complete). That covers the
late purchase: a save created without the DLC keeps version 1 behaviour for as
long as 1963 is clear, and the first time the game itself offers the story after
the expansion is installed, the completed state is applied instead of the start.
Flag 1932 makes it a one-time operation.

The gate does not open a second settlement site: it marks the expansion's rows
achieved+notified+unclaimed, and the game's own report flow (the SYS003 block at
7555 that tests `487 == 1`) credits them through `fl_bliss_settlement_step` the
next time it runs, exactly like any other pending achievement. That keeps one
settlement path, one credit and no double credit, at the cost of the 4600 showing
up in a report that opens slightly later than the skip itself - which the user
checklist treats as an explicit check.

**Level gate.** The skip does not lower the shipped `level >= 50` requirement —
it completes the story at the same entry point the game uses, so a Free Life save
below level 50 that installs the DLC later is skipped too, while a story save is
unaffected. This is deliberate: the base preset already completes every base
chapter regardless of progress, and the requirement is pacing, not a purchase.
The God Tower's own level gates **148/149 (75/100)** and their companion route
flags **150–153** are explicitly *not* set, so the tower keeps its real
requirements even though the story bookkeeping is complete.

## The settlement music that never stopped

User report: after choosing Free Life the Bliss settlement music keeps playing;
the world never gets its BGM back.

Root cause, established statically:

1. Native **344** does not run the report to completion. Its handler `0x39cb24`
calls `0x23edc8`, which tests `fl_has_unclaimed_bliss` and then only *requests*
UI task **40** from the UI manager (`0x28f5b4(manager, 40, -1)`). It returns
immediately, so the event thread keeps running and owns the music.
2. Both shipped landing sequences therefore do the BGM bookkeeping themselves
after the report: `audio_cue(0x90029, 0)` (native 382) at **27060 PC 5183** (the
first-dream path the choice replaces) and **27090 PC 6433** (the base ending),
each followed by two 60-frame waits and `cmd_352(0, 0)`.
3. Version 1 injected the choice at 27060 PC **5133** and jumped to its own
teardown (`cmd_073(1)`, `cmd_041(-100)`, `end`), i.e. straight past PC 5183. The
settlement track stayed current while the chapter ended, which is the reported
behaviour.

Fix, authored script only: after `cmd_344` the branch polls native **487** —
`fl_has_unclaimed_bliss` (`0x3aa018` → `0x244188` → `0x5b68ac`), the same
predicate 344 uses and the one 27679 tests with `487 == 1` before opening the
report — every 30 frames, at most 60 times (about 30 s at 60 fps). When the rows
are claimed it plays `audio_cue(0x90029, 0)` (native 382), waits 30 frames, and
only then runs the normal chapter teardown. The Origin Island settlement uses the
same routine,
so both ledgers settle in one report and end on the same BGM. A player who leaves
rows unclaimed only hits the bounded wait: the world theme is still restored and
the rows stay pending, exactly as the shipped report leaves them.

## Save/state layout and entitlement boundary

These are **in-memory object offsets**, not offsets to write into an on-disk
save. Loading converts representations (e.g. **0x270050**); this work implements
no raw-save patcher and does not claim a complete serializer schema.

| Owner / offset | Field and evidence |
| --- | --- |
| save singleton `0x705f50`, accessor `0x1dd7cc`; **+0x22244** | Event bitset, through `0x1fd7d0`, `0x371c14`, `0x205da8`; 32 flags/word. Multiplayer may select another bitset. |
| same save, **+0x1fc48 + 4*Life** | Life record: low 24 bits stars, high byte rank; `0x5671d0`. Setter includes skills and clamps rank. |
| same save, **+0x2dc40**, bit `5*challenge + 2/3/4` | Challenge achieved/notified/reported; native 87 at `0x3a76a0`. Other two bits are preserved. |
| same save, **+0x2e000**, bit `3*BlissRow + 0/1/2` | Bliss achieved/notified/claimed; native 79 at `0x3a4998`, tests `0x3a3f3c`/`0x3ac490`. |
| same save, **+0x2e060** | 26 Bliss-bonus selection bits, used by `0x24972c` and `0x33c018`. Preset does not set these. |
| active actor's stat component **+0x94 → profile, +0x1a0** | Accumulated Bliss, `0x300e24`/`0x300e9c`; normal settlement writes it. Flat file/save offset not established here. |
| global **0x70359c + quest** | Runtime quest phase byte: 0 unstarted, 1 active, 2 complete. Native 62 exposes completed phase as 3; `0x3fe888`/`0x3fe824`. Active quest records and serialization are distinct. |

Bliss bonus parameters **5793–5801**, milestones **5792**, purchase flags such as
**52/53/82** (bag), **61–63** (pets), **83–85** (storage), **1924–1927** (LINK bag/
storage) remain on the normal path. No bonus is preselected. Housing offers and
owned properties are distinct: opening access flags does not forge purchases.

The overlay still does not replace **5780**, change **ECFlag** at `0x748a24` or
grant **1963/1968**; `f_00205da8` continues to combine entitlement and save flags
normally. What changed in version 2: *when the game reports the expansion as
owned*, the preset also completes **159/160**, sets **1931/1932/1928** and opens
the completion barriers **147** and **154–159**. With the DLC absent those flags,
the Origin Island maps and every route into them stay exactly as they are today,
and nothing is registered, unlocked or simulated by the overlay.

## Offline evidence and remaining limits

The fifteen focused tests include an authored-VM model running the actual patched
opening branch *and* the inserted SYS003 gate: Story Mode/cancel fallthrough, the
exact 8000 credit without DLC, 12600 with DLC in one report, no second credit,
all twelve Novice records, unreported challenges, the entitlement boundary (no
5780 replacement and no write to 1963/1968 in any replaced script), the late
install (gate applies once, then stays inert), Story Mode at level 50 still
reaching the shipped story start, the settlement poll and BGM restore order, and
the bounded wait for a report that never closes. The model stubs native
contracts; it does **not** execute game UI, callbacks or maps. The gate insertion
is verified to be a pure insertion: masking branch operands, the remaining
instruction stream equals the original byte for byte.

All **107 Python tests pass with no skips** using `FL_EU_ARCHIVE` to read the
original extraction by absolute path. The entire script corpus round-trips (1015
fields, 5926 wrappers). The port's host checks are unchanged by this task (no
runtime code was touched).

The built overlay (`12 resources, 206,926 bytes`) stacks with freshly built
Thistle Wolf (31), Quiet House (22) and Wooden Sword (53): **118 disjoint
resources**. `test-fl-mod.exe` loads all four into one virtual archive, reads back
**376,070,781 bytes** and verifies the ExeFS icon, without starting the guest.
`fl_mod.py check-stack` accepts the same order and reversed order.

Outstanding acceptance risks:

- Prompt timing/fade, long localized lines, choice focus and Bliss settlement UI
  need visual/input checks. The callback queue for many simultaneous completions
  has not been exercised in game.
- The opening uses its configured chapter-end landing; a real new save must
  demonstrate that it finishes in a controllable, usable world with no dream,
  letter, royal-audience or Life-intro sequence restarting.
- All regional barriers, ferries, balloons, airships, Flightstone, NPC placement
  layers and post-story companion states need traversal checks. Eight extra gates
  above have weaker evidence; this is not a proof that every side quest is safe.
- Starting tools, recipes, skill availability, and each master's first promotion
  need checks across gathering, crafting and combat Lives. No starter inventory
  bundle is fabricated; shops and normal Life changes remain the acquisition path.
- Future Life rank-ups must not resurrect skipped introductions. Removing the
  overlay retains progression but removes the special Novice guild exception
  until the current Life reaches Fledgling. Keep it enabled for a Free Life save.
- Origin Island: the preset writes what a completed chapter writes, but access
  that ordinary progress opens elsewhere (barriers **150–153**, route endpoints,
  map-visibility layers, NPC placement) may still refuse access. Report each
  spot that still refuses, with its map/door/NPC and message.
- The settlement fix plays the shipped landing track **0x90029** and does not
  add a region-specific BGM. If a region's own theme should start instead, it
  will only do so on the next map load; check that the landing music does not
  override it audibly.
- The report now lists 63 rows on a DLC save. Check that one pass claims all of
  them, that the total is **12600** (8000 + 4600), and that a later Flutter visit
  grants nothing more.
- Other mods editing **27679** (SYS003), **21172** or the opening/message banks
  conflict. The loader correctly rejects them; a merge agent must combine source
  changes.


## Version 4: verified intro-skip rewards (2026-10-25)

**This section supersedes the version-3 skill claims and the unchanged inventory/Dosh
claims above.** The user confirmed v3 still lacks skills in game. Round 2 reviewed
round 1's uncommitted patch, all twelve scratch disassemblies, and every recorded
skip/played-intro call against the absolute-path EU v00 extraction. Round 1's two
incorrect claims were fixed: item helper 4168 calls **181**, not 199; there are
**31**, not 33, distinct skill grants. Magician also has UI-only native 492.

The authored evidence is [free_life_intro_skips.json](../tools/re/free_life_intro_skips.json).
It contains source hashes, offer callers, yes/no branches, exact ordered rewards
(PC, native/helper, arguments, handler), played-intro equivalent skill PCs,
challenge/finish calls, rank end-entry PCs, and SYS003 completion flag writes.
No extracted bytecode or game text is committed.

Each master script calls helper **4807** before the offer: it tests the twelve
primary intro phases using native 63 and permits skipping after another intro is
complete. Function **5042** offers the choice. The first answer **1** continues
the quest (returns 0), **2** takes the skip conversation; the confirmation accepts
with **1** and returns 0 on **2**. Message rows and the complete function bounds
are pinned per Life; UK English is resource+24 (three-resource language stride).
For example Paladin resource 26568 row 619 asks whether to continue, and row 631
confirms the skip. Offer caller 5368 follows the helper-4807 result check.

In the table, skill entries are **skill ID@skip PC**, each using helper 4219;
ability entries are native **191(id,1)**; items are native **181(id,quantity)**
through helper 4168 (quantity 1 except Miner item 1477: quantity 2). The JSON keeps
exact interleaving, including Magician's elements and their ability writes.
All rows finish their reward sequence with helper **4338 -> 178(500)** (Dosh),
then helper **4549** (Novice challenge), and helper **4019(2,2,-1)** (quest-local
finish). Challenge/rank column gives native-87 row / native-173 PC in entry slot 1.

| Life | Quest / resource | Offer caller / function | Skill ID@PC | Ability IDs | Item IDs | Challenge / rank PC |
| --- | --- | --- | --- | --- | --- | --- |
| Angler (2) | 55 / 26412 | 5494 / 5042 | 8@5273 | 55, 57 | 925 | 124 / 10425 |
| Hunter (3) | 46 / 26478 | 5268 / 5042 | 27@5146 | 109, 110, 111, 113, 119 | 34 | 202 / 10891 |
| Blacksmith (5) | 67 / 26214 | 5437 / 5042 | 20@5191, 23@5194, 10@5197, 11@5200 | - | 936 | 345 / 12752 |
| Woodcutter (7) | 58 / 26634 | 5380 / 5042 | 12@5203 | 50, 51 | 914, 1868 | 494 / 12283 |
| Tailor (8) | 76 / 26724 | 5522 / 5042 | 18@5268, 4@5271, 21@5274, 2@5277 | - | 947 | 567 / 10646 |
| Paladin (9) | 49 / 26568 | 5368 / 5042 | 32@5195, 33@5198 | 67, 61, 62, 63, 65 | 0, 523 | 654 / 11891 |
| Alchemist (11) | 64 / 26148 | 5523 / 5042 | 1@5223, 14@5226, 0@5229 | - | 980 | 794 / 10754 |
| Cook (13) | 73 / 26346 | 5616 / 5042 | 5@5311, 22@5314, 17@5317, 13@5320 | - | 970 | 943 / 11437 |
| Mercenary (14) | 52 / 26880 | 5578 / 5042 | 35@5350 | 103, 98, 99, 100 | 17, 1638 | 1030 / 12486 |
| Carpenter (16) | 70 / 26280 | 5675 / 5042 | 3@5216, 9@5219, 25@5222, 24@5225 | - | 959 | 1168 / 12256 |
| Magician (17) | 43 / 26970 | 5579 / 5042 | 34@5246, 29@5249, 36@5255, 30@5261, 26@5267 | 78, 76, 75, 77, 79, 81, 82, 80 | 45, 1646 | 1255 / 14708 |
| Miner (18) | 61 / 26790 | 5838 / 5042 | 15@5409 | 45, 46 | 903, 1477 | 1329 / 10913 |

The first Life cannot reach the normal skip offer. Its **played introduction uses
the same helper 4219 for each skill**, verified at every `intro_pcs` entry in the
JSON. Therefore v4 applies the same list once across all twelve Lives, including
the selected starting Life. It does not run a second grant for that Life.

### Native/save proof and why v3 failed

Native **183(skill,level)** (`0x39ba98`) resolves explicit arguments and calls
`0x567ab4`, which obtains the global player and its stat component (+0xd4).
`0x2ff770` requires an active component (byte +0x8c, profile pointer +0x94), records
first learning, and calls **0x287ff0**. That function stores the level byte at
**profile+0x0c+8*skill** at **0x288034**, clamped to the skill table's maximum;
XP is the adjacent float at **profile+8+8*skill**. The save profile block is
save+0x1fb18 (also used at 0x11efcc..0x11efe0), giving level field
**save+0x1fb24+8*skill** and XP **save+0x1fb20+8*skill**. First learning additionally
sets save+0x21f20 bit **skill+0xd3** (`0x2ff7b0..0x2ff7e0`, index helper
`0x5b7130`, type 2 -> `0x5b7178`). This is direct persistent skill state,
not a notice or an inferred reward callback. No current-Life or quest-phase test
occurs on this setter path. The opening already has the active player; no runtime
patch is needed.

Native **191(ability,1)** (`0x39a5a4 -> 0x567950 -> 0x238bdc`) writes
**save+0x22464+4*(ability>>5)**, bit **ability&31**, at **0x238c30** and dispatches
notification type 13. This is a separate ability bitset. Both setters also append
to script-local eight-slot report queues (`0x450818` / `0x450720`); these queues
are updated **after** the persistent writes and do not gate granting 31 skills.

v3 called **173**, the rank setter, and treated its rank-table ability unlocks
as skill-level grants. **0x2c8920** stores the rank; **0x2c8990..0x2c89a0** reads
eight technique IDs per rank and calls the same **ability-bit** writer 0x238bdc.
It never calls the skill-level writer 0x287ff0. Selecting each Life with 171 cannot
supply those missing explicit 183 calls. 0x1d6d34 is a notification path. Native
**481** (`0x3a4750 -> 0x23875c -> 0x28dfc0`) builds a craft rank-row **UI notice**
(type 14); its handler flags are script-manager fields, not save fields. The old
symbol/command interpretations remain above as historical entries and are
corrected by appended research notes.

The normal finish helper 4019 calls **78(1)** against the active quest/actor and
checks the current Life/rank for an optional presentation path. Teardown helper
126 performs **367, 322(2), 41(-100)**. The quest end entry (slot 1) clears actor
companion slots with **56/78**, then calls **173(Life,1)**. These are not hidden
skill grants. Directly transplanting 78 or -100 completion into the opening would
operate on the opening quest. Instead v4 uses explicit player reward setters,
explicit challenge **87(row,1,0)**, and **173(Life,1)** for rank, techniques and
craft recipe refresh (`0x242d3c`); the existing SYS003 completion flags and native
62 terminal phases cover all 36 intro variants. The opening retains its own
chapter exit and completion. No intro is started just to complete it.

### What v4 replays

Immediately inside the guarded Free Life branch, each Life's persistent rewards
run in source order: **181 items, 183 skills, 191 abilities, 178 Dosh**, followed
by that Life's Novice challenge and terminal rank equivalent. These operations
use explicit IDs and do not require Life switching. The v3 172/171 loop is removed.
Only after rewards are installed does the existing story/intro completion preset
run. This grants the source starter items and **6000 Dosh** (12 x 500), in addition
to the unchanged **8000 Bliss**, Novice ranks, unreported challenges, conditional
Origin Island skip, and settlement music restore. Inventory overflow follows the
normal native-181 handling and may yield.

Cinematic actor movement/camera/input locks, debug output and UI-only reward
notices (326/345/336/484/347/481) are not replayed. Magician's **492(-1,4336,4334,
4335,4337)** at PC5276 is likewise a notice: 0x240200 packs those message rows into
UI type11 and calls 0x28dfc0. Its actual magic skills and abilities are replayed.
Story Mode and cancellation execute the relocated original opening stream; no
new reward setter is reachable on those branches. Existing saves are not repaired.

Offline checks include the full corpus suite, an independent 31-skill expectation,
all twelve starting Lives, exact reward ordering and single execution, original
Story Mode instruction-stream preservation, and the existing Bliss/DLC/music
assertions. VM stubs verify authored instruction flow, not gameplay. Use a **new
Free Life save** and the v4 checklist before accepting the result.


V4 offline validation: **109 tests passed, no skips** with `FL_EU_ARCHIVE` pointing
to the main extraction by absolute path. Overlay: **12 resources, 207178 bytes**;
`check-stack` reports **Stack OK**, **118 resources** with the requested three
merged overlays. Test install publication uses a detached clean package worktree
and label `free-life-skills-v4 <SHA>`; verify that label before the gameplay checks.
