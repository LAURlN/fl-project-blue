#!/usr/bin/env python3
"""Build/audit the EU v00 Free Life script preset, without executing the game.

Only authored instructions and translated text live in git. Original scripts,
their debug pools and message attributes are read from the private extraction.

Version 2 also skips the Origin Island story (Tale of Lunares EX 1/EX 2), but only
when the game's own DLC check (`flag_test 1963`, EC-backed and write-protected)
says the expansion is owned. The entitlement is never forged: no 5780 row, no
ECFlag bit and no 1963 write exists in the overlay.
"""
import argparse
import base64
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import struct


def local(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


vm = local('fl_script')
scr = vm.fl_scr
require = vm.require
STORY = (0, 1, 5, 10, 15, 20, 25, 30, 35)
FLUTTER = tuple(range(79, 118))
LIVES = (2, 3, 5, 7, 8, 9, 11, 13, 14, 16, 17, 18)
INTRO = tuple(range(43, 79))
MARKER = 49  # 000_0050, unused quest-related reserve; only written for Free Life.
VERSION = 4
OPENING_PC = 5133  # first-dream event (27060) PC the choice block replaces
TEXT_IDS = (27059,) + tuple(range(27063, 27085, 3))
SOURCE_HASHES = {
    21172: 'e5df7a1846a510e45c487c2d27d31915a3a9b4a90f71f4923a3bf3bcf898b90e',
    27060: 'e63af4ac82cdf398762c940470dbd1df6791f8a14e0557342471fdacb0cc9938',
    27679: '4afdc8fa924bc023c72fb868b5fd1e32a0db81974e99da0cc715003d3a3e898c',
    5780: '8e686eec7fd371a1545debc179196e61f3b574e9b8ae134834ce58c522718182',
    5791: '9b0be8b3a22b51f5784e8db639029e1d1f3a3784382c6eb3c2de220ae0b592ec',
    5809: '8db65dd11a8a44ef63ad37a07499b4d608e832b12df6cda7622325e2fd746d71',
    5827: '66e1b1d6cea5581587f7d879755ca8f7a0adb0314dd2d07a7028f4bf4779ad5b',
}

# The Origin Island story is base-story episode 8 ("Tale of Lunares: EX 1/EX 2",
# chapter-label rows 159/160) plus its own request line. Quest IDs are the
# native-62 phase space (0x70359c + quest, bound 174), the same space the base
# preset already uses; each is < 174.
DLC_CHAPTERS = (159, 160)
DLC_REQUESTS = (118,) + tuple(range(119, 129)) + (164, 165, 166)   # Flutter 040-053
DLC_QUESTS = DLC_REQUESTS + DLC_CHAPTERS
# Literal flag_set writes inside SYS003 (27679) completion cases, keyed by quest.
DLC_FLAG_EVIDENCE = {
    119: ((42, 10217),),
    120: ((43, 10223),),
    121: ((44, 10229),),
    122: ((45, 10235),),
    123: ((46, 10241),),
    124: ((47, 10247),),
    125: ((48, 10253), (147, 10258)),
    126: ((1970, 10264), (1988, 10269)),
    127: ((1971, 10275), (1998, 10280)),
    128: ((1972, 10290), (1999, 10295)),
    159: ((1931, 9842), (154, 9847), (155, 9852), (156, 9857), (158, 9862),
          (159, 9867), (1928, 9872), (118, 9877)),
    160: ((1932, 9883), (157, 9888)),
    164: ((1973, 10301), (2000, 10306)),
    165: ((1974, 10312), (2001, 10317)),
    166: ((1975, 10323), (2002, 10328)),
}   # quest 118 (Flutter 040) has no SYS003 completion case; it is the story start.
DLC_FLAGS = tuple(sorted({flag for rows in DLC_FLAG_EVIDENCE.values() for flag, _ in rows}))
# Story entry gate in SYS003: DLC owned, Flutter 038/039 done, level >= 50, then
# cmd_040(118) starts the story. Free Life replaces that with this preset.
DLC_GATE_PC = 5518
# Bliss rows of type 35 whose required flag is not 65535: the expansion's rows.
DLC_BLISS = (200, 201, 202, 203, 204, 205, 206, 207,
             223, 224, 225, 226, 227, 228, 229, 230)
DLC_BLISS_TOTAL = 4600
LANDING_BGM = 0x90029   # audio_cue row: world theme restored at 27060 PC 5183 and 27090 PC 6433
SETTLE_POLLS = 60       # bounded report wait: 60 x 30 frames ~ 30 s at 60 fps
SETTLE_FRAMES = 30

# Additional persistent gates outside the chapter-completion switch. Each is
# reviewed separately; Bliss purchases, DLC, levels and rank shops are excluded.
EXTRA_FLAGS = {
    73: 'party feature; ordinary companion invitation remains individual',
    75: 'Dark Tome library route; normally unlocked at level 35 (SYS003 PC 10671)',
    91: 'Other Requests feature',
    108: 'post-story world access (SYS003 PCs 6287, 6421, 10701)',
    132: 'Lunares route; normal game additionally waits for level 40 (SYS003 PC 10686)',
    139: 'restored Flightstone; post-story Levitania access',
    144: 'Gigante ruins route; SYS003 PC 10884, requires sufficiently advanced Life rank',
    249: 'Mt Snowpeak summit map visibility',
}

# ja, es-419, fr-CA, de, en-US, es, fr, it, en-GB. Kept deliberately short
# enough for the original system message window and two-choice selector.
PROMPTS = (
    ('物語の遊び方を選んでください。', 'ストーリーモード', 'フリーライフ',
     '物語とライフの入門クエストを省略します。\nハッピー８０００を受け取れます。\nすべてのライフが「みならい」から始まります。'),
    ('¿Cómo quieres comenzar tu aventura?', 'Modo historia', 'Vida libre',
     'Vida libre omite la historia y las misiones iniciales.\nRecibirás 8000 puntos de felicidad. Los rangos empiezan en novato.'),
    ('Comment veux-tu commencer ton aventure ?', 'Mode histoire', 'Vie libre',
     'Vie libre passe l’histoire et les quêtes d’initiation.\nTu recevras 8000 points de bonheur. Les rangs commencent à novice.'),
    ('Wie möchtest du dein Abenteuer beginnen?', 'Story-Modus', 'Freies Leben',
     'Freies Leben überspringt Geschichte und Einführungsquests.\nDu erhältst 8000 Wonne. Alle Leben beginnen als Neuling.'),
    ('How would you like to begin your adventure?', 'Story Mode', 'Free Life',
     'Skip the story and Life introductions.\nReceive 8000 Bliss.\nEvery Life begins at Novice.'),
    ('¿Cómo quieres comenzar tu aventura?', 'Modo historia', 'Vida libre',
     'Vida libre omite la historia y las misiones iniciales.\nRecibirás 8000 puntos de felicidad. Los rangos empiezan en novato.'),
    ('Comment veux-tu commencer ton aventure ?', 'Mode histoire', 'Vie libre',
     'Vie libre passe l’histoire et les quêtes d’initiation.\nTu recevras 8000 points de bonheur. Les rangs commencent à novice.'),
    ('Come vuoi iniziare la tua avventura?', 'Modalità storia', 'Vita libera',
     'Vita libera salta la storia e le missioni introduttive.\nRiceverai 8000 felicità. Ogni mestiere inizia da novizio.'),
    ('How would you like to begin your adventure?', 'Story Mode', 'Free Life',
     'Skip the story and Life introductions.\nReceive 8000 Bliss.\nEvery Life begins at Novice.'),
)


def layout(raw):
    first, second = vm.sections(raw)
    return vm.vm_layout(first, second)


def literals(ops, pc, command, count):
    if ops[pc][0] != 7 or ops[pc][1] >> 8 != command or pc < count:
        return None
    args = ops[pc-count:pc]
    return [value for op, value in args] if all(op == 1 for op, _ in args) else None


def chapter_cases(ops):
    """Decode SYS003's literal switch, not a speculative whole-script flag union."""
    cases = {}
    for pc in range(10333, 10593 - 5):
        if (ops[pc][0] == 17 and ops[pc][1] == 21 and ops[pc+1][0] == 1
                and ops[pc+2] == (17, 15) and ops[pc+3][0] == 16
                and ops[pc+4] == (17, 22) and ops[pc+5][0] == 15):
            cases[ops[pc+1][1]] = ops[pc+5][1] >> 8
    require(len(cases) >= 30, 'Unrecognized SYS003 completion switch')
    return cases


def case_flags(ops, cases, quest):
    """Contiguous literal flag_set(id,1) calls inside one completion case."""
    if quest not in cases:
        return ()
    boundaries = sorted(set(cases.values()) | {10333})
    start = cases[quest]
    end = next(pc for pc in boundaries if pc > start)
    found = []
    for pc in range(start, end):
        args = literals(ops, pc, 65, 2)
        if args and args[1] == 1:
            found.append((args[0], pc))
    return tuple(found)


def audit(data):
    for id_, sha in SOURCE_HASHES.items():
        require(hashlib.sha256(data.path(id_).read_bytes()).hexdigest() == sha,
                f'Free Life requires the audited EU v00 resource {id_}')
    raw = data.path(27679).read_bytes()
    ops = layout(raw)['ops']
    cases = chapter_cases(ops)
    flags = {}
    for quest in STORY + FLUTTER + tuple(range(43, 79, 3)):
        for flag, pc in case_flags(ops, cases, quest):
            flags.setdefault(flag, []).append(dict(resource=27679, pc=pc, quest=quest))
    for flag, reason in EXTRA_FLAGS.items():
        flags.setdefault(flag, []).append(dict(reason=reason))
    # Main story and Life intro completion markers must all be present in the
    # actual shipped switch. This catches changes to its bounds or interpretation.
    require(set(range(21)) <= flags.keys(), 'Incomplete story/Life completion flag derivation')
    require(all(flag < 147 or 239 <= flag <= 250 for flag in flags),
            'Base preset would touch an unaudited or DLC flag')
    rewards = []
    for row, record in enumerate(data.rows(5809)):
        if record['c01'] == 35 and record['c06'] == 65535:
            quest = record['c02'][0]
            require(quest in STORY + FLUTTER, f'Unreviewed story Bliss objective {quest}')
            rewards.append(dict(row=row, quest=quest, bliss=record['c03']))
    require(len(rewards) == 47 and sum(r['bliss'] for r in rewards) == 8000,
            'Base story Bliss ledger changed')
    challenges = [i for i, r in enumerate(data.rows(5827))
                  if r['rank'] == 1 and r['life_id'] in LIVES]
    require(len(challenges) == 12, 'Expected one Novice challenge per playable Life')
    return dict(format='fl-free-life-audit-v2', source_sha256=hashlib.sha256(raw).hexdigest(),
                story=list(STORY), flutter=list(FLUTTER), intros=list(INTRO), lives=list(LIVES),
                flags=[dict(id=i, evidence=v) for i, v in sorted(flags.items())],
                bliss=rewards, total_bliss=8000, novice_challenges=challenges,
                marker=MARKER, life_skips=intro_skip_audit(data),
                dlc=dlc_audit(data, ops, cases))


def intro_skip_audit(data):
    """Pin the actual yes/no skip branches and their played-intro equivalents.

    These are authored facts (IDs/PCs), not preserved game bytecode. Native 183
    writes skill levels; native 191 writes combat ability bits. Notices are UI,
    not grants. Keep the shipped persistent reward order within each Life.
    """
    path = Path(__file__).parent / 're/free_life_intro_skips.json'
    records = json.loads(path.read_text(encoding='utf-8'))['lives']
    require(tuple(r['life'] for r in records) == LIVES, 'Incomplete Life skip evidence')
    skills = []
    for record in records:
        raw = data.path(record['resource']).read_bytes()
        require(hashlib.sha256(raw).hexdigest() == record['sha256'],
                f"Free Life requires the audited EU v00 resource {record['resource']}")
        ops = layout(raw)['ops']
        require(literals(ops, record['offer_function'] + 8, 90, 1) == [record['offer_row']]
                or any(literals(ops, pc, 90, 1) == [record['offer_row']]
                       for pc in range(record['offer_function'], record['offer_function']+20)),
                'Life skip offer changed')
        for effect in record['effects']:
            pc, args = effect['pc'], effect['args']
            if 'helper' in effect:
                target = effect['helper']
                require(effect['native'] == {4168: 181, 4219: 183, 4234: 191, 4338: 178}.get(target),
                        'Unknown Life reward helper/native mapping')
                require(ops[pc] == (10, target << 8), 'Life reward helper changed')
                original = (args + [1, 0xffffffff] if target == 4168 else
                            [args[0], 0xffffffff])
                require(ops[pc-len(original):pc] == [(1, a) for a in original],
                        'Life reward arguments changed')
            else:
                require(literals(ops, pc, effect['native'], len(args)) == args,
                        'Life reward native changed')
            if effect['native'] == 183:
                skills.append(args[0])
                for pc in effect['intro_pcs']:
                    require(ops[pc-2:pc+1] == [(1, args[0]), (1, 0xffffffff), (10, 4219 << 8)],
                            'Played intro skill equivalent changed')
        require(ops[record['challenge_pc']] == (10, 4549 << 8)
                and ops[record['finish_pc']-3:record['finish_pc']+1] ==
                [(1, 2), (1, 2), (1, 0xffffffff), (10, 4019 << 8)],
                'Life skip completion changed')
    require(len(skills) == len(set(skills)) == 31, 'Duplicate/missing intro skill')
    # All twelve scripts carry the same reward helper implementations.
    for record in records:
        ops = layout(data.path(record['resource']).read_bytes())['ops']
        require(ops[4225:4230] == [(0, 0xfffffe01), (7, 345 << 8),
                (0, 0xfffffe01), (1, 1), (7, 183 << 8)],
                'Skill helper no longer writes level 1')
        require(ops[4212:4215] == [(0, 0xfffffc01), (0, 0xfffffd01), (7, 181 << 8)],
                'Item helper changed')
        require(ops[record['offer_caller_pc']] == (10, record['offer_function'] << 8),
                'Skip offer caller changed')
        require(literals(ops, record['completion']['rank_pc'], 173, 2)
                == [record['life'], 1], 'Intro end rank changed')
        for effect in record.get('ui_only', []):
            require(literals(ops, effect['pc'], effect['native'], len(effect['args']))
                    == effect['args'], 'Skip UI-only evidence changed')
    return records


def dlc_audit(data, ops, cases):
    """Audit the Origin Island story and its requests, and the entitlement rule."""
    evidence, flags = {}, {}
    for quest, rows in DLC_FLAG_EVIDENCE.items():
        derived = case_flags(ops, cases, quest)
        require(derived == rows, f'Origin Island completion case {quest} changed')
        evidence[quest] = [dict(flag=flag, pc=pc) for flag, pc in derived]
        for flag, pc in derived:
            flags.setdefault(flag, []).append(dict(resource=27679, pc=pc, quest=quest))
    require(case_flags(ops, cases, 118) == (),
            'Origin Island start quest 118 unexpectedly has a completion case')
    require(len(DLC_QUESTS) == 16 and set(DLC_QUESTS) <= set(range(174)),
            'Origin Island quest IDs must stay inside the quest-phase table')
    # Barrier provenance: 147-157 are the God Tower / God Island gates.
    require({147, 154, 155, 156, 157, 158, 159} <= set(flags),
            'Origin Island access flags are not fully derived')
    # 148/149 are the God Tower level gates (75/100) and 151/152 their notified
    # companions, all written by the route function at SYS003 PCs 10722, 10746,
    # 10753 and 10777; 153 belongs to the PC 8031 route. None is a completion
    # write, so the preset must leave every one of them closed.
    require(not (flags.keys() & {148, 149, 150, 151, 152, 153}),
            'Preset would bypass the God Tower level gates or their routes')
    # Entitlement: row 1963 is EC-controlled and write-protected; never forged.
    ec = data.rows(5780)
    require(ec[1963]['c00'] == 0 and ec[1963]['c01'] == 1,
            'Origin Island entitlement flag is no longer EC-backed/read-only')
    require(all(ec[flag]['c01'] == 0 for flag in flags),
            'Origin Island preset would write an EC-controlled flag')
    require(not ({1963, 1968} & set(flags)), 'Preset must never write an entitlement flag')
    # The DLC story's entry gate must still be recognizable.
    gate = [pc for pc in range(5510, 5530) if literals(ops, pc, 66, 1) == [1963]]
    require(gate == [DLC_GATE_PC + 2], 'Origin Island entry gate changed')
    require(any(literals(ops, pc, 40, 1) == [118] for pc in range(5518, 5570)),
            'Origin Island start call cmd_040(118) changed')
    rewards = []
    for row in DLC_BLISS:
        record = data.rows(5809)[row]
        require(record['c01'] == 35 and record['c06'] == 1963,
                f'Origin Island Bliss row {row} changed')
        rewards.append(dict(row=row, quest=record['c02'][0], bliss=record['c03']))
    require(sorted(r['quest'] for r in rewards) == sorted(DLC_QUESTS),
            'Origin Island Bliss rows no longer cover Flutter 040-053 + both chapters')
    require(sum(r['bliss'] for r in rewards) == DLC_BLISS_TOTAL,
            'Origin Island Bliss total changed')
    base_rows = {r for r, record in enumerate(data.rows(5809))
                 if record['c01'] == 35 and record['c06'] == 65535}
    require(not (set(DLC_BLISS) & base_rows), 'Origin Island Bliss rows overlap the base rows')
    return dict(chapters=list(DLC_CHAPTERS), requests=list(DLC_REQUESTS),
                quests=list(DLC_QUESTS),
                flags=[dict(id=i, evidence=v) for i, v in sorted(flags.items())],
                case_evidence=evidence, gate_pc=DLC_GATE_PC,
                level_requirement=50, tower_level_gates=[148, 149],
                routes_left_closed=[150, 151, 152, 153],
                bliss=rewards, total_bliss=DLC_BLISS_TOTAL,
                entitlement_flag=1963, entitlement_writable=False)


def choice(labels):
    """SCR f5: offsets are relative to each offset word, strings padded to four."""
    records = []
    for result, label in enumerate(labels, 1):
        text = label.encode('utf-16le') + b'\0\0'
        text += b'\0' * (-len(text) % 4)
        records.append(struct.pack('<IHH', result, len(text), len(text)) + text)
    offsets, cursor = [], 8 + 4 * len(records)
    for i, record in enumerate(records):
        offsets.append(cursor - (8 + 4*i))
        cursor += len(record)
    payload = struct.pack('<II', 0xffffffff, len(records))
    payload += struct.pack('<' + 'I'*len(records), *offsets) + b''.join(records)
    return dict(control=(bytes.fromhex('f5ffffff') + struct.pack('<I', len(payload)+4) + payload).hex())


def lines(text):
    parts = []
    for line in text.split('\n'):
        if parts:
            parts.append(dict(control='f0ffffff04000000'))
        parts.append(line)
    return parts


def call(command, *args):
    return ''.join(f'  push 0x{a & 0xffffffff:08x}\n' for a in args) + f'  native {command} 0x0\n'


def dlc_state(plan):
    """Origin Island bookkeeping: same writes a completed story/request would make."""
    text = ''
    for flag in plan['dlc']['flags']:
        text += call('flag_set', flag['id'], 1)
    for quest in plan['dlc']['quests']:
        text += call('cmd_062', quest, 3)
    for reward in plan['dlc']['bliss']:
        # Achieved + notified, unclaimed: settlement credits through the normal path.
        text += call('cmd_079', reward['row'], 1, 0)
    return text


def settlement():
    """Open the normal settlement, let it finish, then re-assert the world BGM.

    Native 344 only *requests* the Bliss report UI for the UI manager (handler
    0x39cb24 -> 0x23edc8 -> 0x28f5b4(ui, 40, -1)), so the caller keeps running and
    owns the music. Both shipped landing sequences switch the BGM back to 0x90029
    with cmd_382 after the report (27060 PC 5183, 27090 PC 6433). The Free Life
    branch jumps over 27060's sequence and used to tear the chapter down right
    after 344, so the settlement track was never replaced: that is the reported
    "Bliss music never stops". Native 487 returns fl_has_unclaimed_bliss (handler
    0x3aa018 -> 0x244188 -> 0x5b68ac), the same predicate 344 uses and 27679 tests
    with `487 == 1` before opening the report; it stays 1 until the player has
    claimed every row, so polling it is an exact "report still open" test.
    """
    text = 'FREE_LIFE_SETTLE:\n' + call('cmd_344')
    for _ in range(SETTLE_POLLS):
        text += call('bliss_unclaimed_test')
        text += '  jump_zero FREE_LIFE_SETTLE_DONE 0x0\n'
        text += call('wait_frames', SETTLE_FRAMES)
    text += 'FREE_LIFE_SETTLE_DONE:\n'
    text += call('audio_cue', LANDING_BGM, 0)
    text += call('wait_frames', SETTLE_FRAMES)
    return text


def initializer(plan):
    text = 'FREE_LIFE_BEGIN:\n'
    text += call('flag_test', MARKER)
    text += '  jump_zero FREE_LIFE_APPLY 0x0\n  jump FREE_LIFE_LEAVE 0x0\n'
    text += 'FREE_LIFE_APPLY:\n'
    # Reward setters take explicit skill/ability IDs and target the player. Replay
    # before completing intro phases; never transplant native 78 (quest actor).
    # Notice-only helpers and cinematic actor work do not change progression.
    for record in plan['life_skips']:
        for effect in record['effects']:
            text += call(effect['native'], *effect['args'])
        text += call('cmd_087', record['challenge'], 1, 0)
        # End-entry equivalent; rank grants techniques, not skill levels.
        text += call('cmd_173', record['life'], 1)
    for flag in plan['flags']:
        text += call('flag_set', flag['id'], 1)
    for quest in STORY[1:] + FLUTTER + INTRO:
        text += call('cmd_062', quest, 3)
    for reward in plan['bliss']:
        # Achieved + notified, unclaimed. Normal settlement marks claimed and
        # grants the table reward, including normal Bliss-bonus thresholds.
        text += call('cmd_079', reward['row'], 1, 0)
    # Origin Island only when the game itself reports the expansion as owned.
    text += call('flag_test', 1963)
    text += '  jump_zero FREE_LIFE_NO_DLC 0x0\n'
    text += call('flag_test', 1932)
    text += '  jump_zero FREE_LIFE_DLC 0x0\n  jump FREE_LIFE_NO_DLC 0x0\n'
    text += 'FREE_LIFE_DLC:\n'
    text += dlc_state(plan)
    text += 'FREE_LIFE_NO_DLC:\n'
    text += call('flag_set', MARKER, 1)
    text += call('message', 569)
    text += settlement()
    text += 'FREE_LIFE_LEAVE:\n'
    text += call('cmd_130', 0)
    for option in (0, 7, 5, 2, 1, 3, 10, 20, 21):
        text += call('cmd_330', option, 1)
    text += call('cmd_101')
    text += '  call_global 0x00000800\n'
    # Use the chapter's own end landing and normal quest teardown. Native 121
    # kills the thread, so a raw warp followed by quest_complete is incorrect.
    text += call('cmd_073', 1)
    text += call('cmd_041', -100)
    text += '  end 0x00000000\n'
    return text


def dlc_gate(plan):
    """Apply the Origin Island preset where the DLC story first becomes reachable.

    SYS003 PC 5518 is the shipped story-entry check (DLC owned, Flutter 038/039
    cleared, level >= 50): it would start quest 118. A Free Life save replaces
    that start with the completed state, so a DLC installed after the choice is
    skipped the first time the game offers the story - and never again, because
    completing quest 118 makes the original gate false.
    """
    text = 'FREE_LIFE_DLC_GATE:\n'
    text += call('flag_test', MARKER)
    text += '  jump_zero FREE_LIFE_GATE_END 0x0\n'
    text += call('flag_test', 1963)
    text += '  jump_zero FREE_LIFE_GATE_END 0x0\n'
    text += call('flag_test', 1932)
    text += '  jump_zero FREE_LIFE_GATE_APPLY 0x0\n  jump FREE_LIFE_GATE_END 0x0\n'
    text += 'FREE_LIFE_GATE_APPLY:\n'
    text += dlc_state(plan)
    text += 'FREE_LIFE_GATE_END:\n'
    return text


def inject(raw, pc, code):
    """Insert before one original PC; assembler relocates calls, entries, globals."""
    assembly = vm.disassemble(raw)
    # Ensure this PC is a label even if the base has no branch/entry to it.
    code_start = assembly.index('.code ')
    head, tail = assembly[:code_start], assembly[code_start:]
    output, instruction = [], -1
    inserted = False
    for line in tail.splitlines():
        if line.startswith('  ') and line.strip() and not line.lstrip().startswith('#'):
            instruction += 1
            if instruction == pc:
                output.append(code.rstrip())
                inserted = True
        output.append(line)
    require(inserted, f'Insertion PC {pc} outside script')
    result = vm.assemble(head + '\n'.join(output) + '\n')
    require(vm.assemble(vm.disassemble(result)) == result, 'Patched VM failed round trip')
    return result


def apply(data, options):
    require(options == {'version': VERSION}, 'Unsupported story_skip preset version/options')
    plan = audit(data)
    opening = data.path(27060).read_bytes()
    require(layout(opening)['ops'][OPENING_PC-1:OPENING_PC+1] == [(8, 0x600), (7, 367 << 8)],
            'Opening event setup anchor changed')
    # Leave the original opening setup in place. Story Mode falls through to its
    # original instruction; Free Life ends the chapter through its own teardown.
    prompt = call('screen_fade', 30) + call('message', 567) + call('message_result')
    prompt += '  push 0x00000002\n  alu eq\n  jump_zero FREE_LIFE_STORY 0x0\n'
    prompt += initializer(plan) + 'FREE_LIFE_STORY:\n'
    updates = {27060: inject(opening, OPENING_PC, prompt)}
    # The guild's rank<=1 refusal is independent of flag 50. Retain it for
    # Story Mode, permit the deliberately Novice Free Life preset to change Life.
    shared = data.path(21172).read_bytes()
    ops = layout(shared)['ops']
    matches = [pc for pc in range(len(ops)-4)
               if ops[pc:pc+4] == [(0, 0x701), (1, 1), (17, 19), (16, 5668 << 8)]]
    require(len(matches) == 1, 'Guild Novice refusal anchor changed')
    gate = call('flag_test', MARKER) + '  alu not\n  alu and\n'
    updates[21172] = inject(shared, matches[0]+3, gate)
    # Origin Island: the shipped entry gate applies the preset on late installs.
    system = data.path(27679).read_bytes()
    updates[27679] = inject(system, DLC_GATE_PC + 1, dlc_gate(plan))
    for id_, (question, story, free, description) in zip(TEXT_IDS, PROMPTS):
        doc = copy.deepcopy(data.document(id_))
        rows = doc['sections'][0]['rows']
        require(len(rows) == 626, 'Opening message layout changed')
        rows[566]['c00'], rows[568]['c00'] = 'SYSTEM', 'SYSTEM'
        rows[567]['c00'] = [question, choice((story, free))]
        rows[569]['c00'] = lines(description)
        # This wrapper has one signed speaker ID per message pair. Use the
        # existing system speaker (-1), retaining all other message attributes.
        attrs = bytearray(base64.b64decode(doc['sections'][1]['original']))
        require(struct.unpack_from('<I', attrs)[0] == 313 and len(attrs) == 4+313*4,
                'Opening message attributes changed')
        struct.pack_into('<i', attrs, 4+283*4, -1)
        struct.pack_into('<i', attrs, 4+284*4, -1)
        doc['sections'][1]['original'] = base64.b64encode(attrs).decode('ascii')
        updates[id_] = scr.build(doc)
        require(scr.build(scr.dump(updates[id_], id_)) == updates[id_], 'Message round trip failed')
    return updates, plan


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('report', type=Path)
    args = parser.parse_args()
    data = local('fl_data').Data(args.archive)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(audit(data), ensure_ascii=False, indent=2) + '\n')
    print(f'47 story/Flutter rewards: 8000 Bliss; 16 Origin Island rewards: '
          f'4600 Bliss; audit: {args.report}')


if __name__ == '__main__':
    main()
