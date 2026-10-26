"""Host-only Free Life validation. No guest CPU, services, or game are started."""
import copy
import os
from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import fl_story_skip as ss
import fl_data
from test_fl_script import vm as fixture


class PresetTests(unittest.TestCase):
    def test_choice_matches_shipped_control_shape(self):
        expected = ('f5ffffff34000000ffffffff020000000800000014000000'
                    '01000000080008005900650073000000'
                    '02000000080008004e006f0000000000')
        self.assertEqual(ss.choice(('Yes', 'No'))['control'], expected)
        for _, story, free, _ in ss.PROMPTS:
            token = ss.choice((story, free))
            encoded = ss.scr.write_string(['Choose', token])
            self.assertIn(story.encode('utf-16le'), encoded)
            self.assertIn(free.encode('utf-16le'), encoded)

    def test_injection_relocates_original_calls_entries_globals(self):
        raw = fixture()
        before = ss.layout(raw)
        after = ss.layout(ss.inject(raw, 2, '  push 0x2a\n  alu drop\n'))
        self.assertEqual(after['labels'], before['labels'])
        self.assertEqual(after['globals'], [0, 8])
        self.assertEqual(after['ops'][4], (16, 8 << 8 | 3))
        self.assertEqual(after['ops'][5], (10, 8 << 8 | 2))
        self.assertEqual(after['pool'], before['pool'])
        with self.assertRaisesRegex(ValueError, 'outside script'):
            ss.inject(raw, 999, '  end 0\n')

    def test_version_and_revision_fail_closed(self):
        self.assertEqual(ss.VERSION, 4)
        for options in ({'version': 1}, {'version': 2}, {'version': 3}, {'version': 4, 'extra': 1}):
            with self.assertRaisesRegex(ValueError, 'version'):
                ss.apply(None, options)
        class Data:
            def path(self, _):
                return type('File', (), {'read_bytes': lambda _: fixture()})()
        with self.assertRaisesRegex(ValueError, 'audited EU v00'):
            ss.audit(Data())



class Model:
    """Bounded VM model of authored writes, deliberately not a game emulator.

    Native stubs implement only the statically traced contracts. This catches
    stack mistakes, bad jumps, unintended grants and duplicate-credit behavior;
    actual UI scheduling, map transitions and quest callbacks need user testing.
    """
    def __init__(self, plan, flags=None, level=1, poll_open=0, quests=None, current=2):
        self.plan = plan
        self.stack, self.variables = [], {}
        # 1963 is the game's own DLC test: set for a save where the expansion is
        # owned, clear when it is absent.
        self.flags = {1963: True, 1931: False, 1932: False, 154: False, 49: False}
        if flags:
            self.flags.update(flags)
        self.quests = {159: 0, 160: 0}
        if quests:
            self.quests.update(quests)
        self.ranks, self.challenges, self.achievements = {}, {}, {}
        self.bliss, self.report_count = 0, 0
        self.other = {'level': level, 'dosh': 1000, 'bag': 50, 'pets': 0}
        # Settlement credits whatever the authored branch marked unclaimed.
        self.rewards = {r['row']: r['bliss'] for r in plan['bliss'] + plan['dlc']['bliss']}
        self.claimed = {}
        self.sounds, self.waits, self.started = [], [], []
        self.poll_open, self.polls = poll_open, 0
        self.reached_original = False
        self.natives = []
        # Rank and skill levels are distinct native contracts (v3 confused these).
        self.current = current
        self.life_grants = []
        self.skills, self.abilities, self.items = {}, {}, {}

    def run(self, raw, entry, result=2):
        ops = ss.layout(raw)['ops']
        self.stack.clear()
        pc = entry
        commands = ss.vm.commands()
        for _ in range(20000):
            op, value = ops[pc]
            pc += 1
            if op in (13, 14):
                continue
            if op == 1:
                self.stack.append(value)
            elif op == 0:
                self.stack.append(self.variables[value])
            elif op == 5:
                self.variables[value] = self.stack.pop()
            elif op == 8:
                if value == 0x600:
                    del self.stack[-2:]
                elif value != 0x800:
                    raise AssertionError(f'Unexpected global {value}')
            elif op == 7:
                command = value >> 8
                n = commands[command]['argc']
                args = self.stack[-n:] if n else []
                if n:
                    del self.stack[-n:]
                self.natives.append((command, args))
                if command == 66:
                    self.stack.append(int(self.flags.get(args[0], False)))
                elif command == 65:
                    self.flags[args[0]] = bool(args[1])
                elif command == 99:
                    self.stack.append(result)
                elif command == 62:
                    self.quests[args[0]] = args[1]
                elif command == 63:
                    self.stack.append(3 if self.quests.get(args[0]) == 3 else 0)
                elif command == 172:
                    self.stack.append(self.current)
                elif command == 171:
                    self.current = args[0]
                elif command == 173:
                    self.ranks[args[0]] = args[1]
                elif command == 183:
                    self.skills[args[0]] = args[1]
                    self.life_grants.append(args[0])
                elif command == 191:
                    self.abilities[args[0]] = bool(args[1])
                elif command == 181:
                    self.items[args[0]] = self.items.get(args[0], 0) + args[1]
                elif command == 178:
                    self.other['dosh'] += args[0]
                elif command == 87:
                    self.challenges[args[0]] = (True, True, False)
                elif command == 79:
                    self.achievements[args[0]] = (bool(args[1]), bool(args[2]),
                                                  self.claimed.get(args[0], False))
                elif command == 344:
                    for row in list(self.achievements):
                        award = self.rewards.get(row)
                        if award is not None and not self.claimed.get(row, False):
                            self.bliss += award
                            self.claimed[row] = True
                            self.achievements[row] = (True, True, True)
                    self.report_count += 1
                elif command == 487:
                    # fl_has_unclaimed_bliss: the report still owns the screen.
                    self.polls += 1
                    self.stack.append(int(self.polls <= self.poll_open))
                elif command == 382:
                    self.sounds.append((args[0], args[1]))
                elif command == 2:
                    self.waits.append(args[0])
                elif command == 569:
                    self.stack.append(self.other['level'])
                elif command in (52, 53, 453):
                    self.stack.append(0)
                elif command == 40:
                    self.started.append(args[0])
                elif command == 41:
                    self.quests[0] = 3
                elif command == 367:
                    self.reached_original = True
                    return
                elif command not in (98, 72, 350, 90, 130, 330, 101, 73, 432, 119):
                    raise AssertionError(f'Unexpected native {command}')
            elif op == 15:
                pc = value >> 8
            elif op == 16:
                if self.stack.pop() == 0:
                    pc = value >> 8
            elif op == 17:
                if value == 13:
                    self.stack.append(int(not self.stack.pop()))
                else:
                    b, a = self.stack.pop(), self.stack.pop()
                    if value == 15:
                        self.stack.append(int(a == b))
                    elif value == 16:
                        self.stack.append(int(a != b))
                    elif value == 10:
                        self.stack.append(a & b)
                    elif value == 20:
                        self.stack.append(int(a >= b))
                    else:
                        raise AssertionError(f'Unexpected ALU {value}')
            elif op == 11:
                self.assert_empty()
                return
            elif op == 12:
                self.assert_empty()
                return
            else:
                raise AssertionError(f'Unexpected opcode {op}')
        raise AssertionError('Authored VM did not terminate')

    def assert_empty(self):
        if self.stack:
            raise AssertionError(f'Unbalanced stack: {self.stack}')


@unittest.skipUnless(os.environ.get('FL_EU_ARCHIVE'), 'Set FL_EU_ARCHIVE for private corpus checks')
class PrivateCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = fl_data.Data(os.environ['FL_EU_ARCHIVE'])
        cls.updates, cls.plan = ss.apply(cls.data, {'version': 4})

    def test_default_story_and_cancel_leave_original_path(self):
        for result in (0, 1, 0xffffffff):
            model = Model(self.plan)
            old = copy.deepcopy(model.__dict__)
            model.run(self.updates[27060], ss.OPENING_PC, result)
            self.assertTrue(model.reached_original)
            for key in ('flags', 'quests', 'ranks', 'bliss', 'other'):
                self.assertEqual(getattr(model, key), old[key])

    def test_free_life_replays_each_skip_reward_once_in_source_order(self):
        expected_skills = {
            2: [8], 3: [27], 5: [20, 23, 10, 11], 7: [12],
            8: [18, 4, 21, 2], 9: [32, 33], 11: [1, 14, 0],
            13: [5, 22, 17, 13], 14: [35], 16: [3, 9, 25, 24],
            17: [34, 29, 36, 30, 26], 18: [15],
        }
        for current in ss.LIVES:
            model = Model(self.plan, current=current)
            model.run(self.updates[27060], ss.OPENING_PC)
            expected = []
            for record in self.plan['life_skips']:
                life = record['life']
                self.assertEqual([e['args'][0] for e in record['effects']
                                  if e['native'] == 183], expected_skills[life])
                expected.extend((e['native'], e['args']) for e in record['effects'])
                expected.extend([(87, [record['challenge'], 1, 0]), (173, [life, 1])])
            actual = [(c, a) for c, a in model.natives if c in (181, 183, 191, 178, 87, 173)]
            self.assertEqual(actual, expected)
            self.assertEqual(len(model.life_grants), 31)
            self.assertEqual(len(set(model.life_grants)), 31)
            self.assertEqual(model.skills, {i: 1 for ids in expected_skills.values() for i in ids})
            self.assertEqual(model.current, current)
            self.assertEqual(model.ranks, dict.fromkeys(ss.LIVES, 1))
            self.assertEqual(model.other['dosh'], 7000)  # 1000 + twelve native-178(500)
            self.assertFalse({c for c, _ in model.natives} & {171, 172, 78, 56, 481, 492})
            before = copy.deepcopy((model.life_grants, model.skills, model.abilities,
                                    model.items, model.other))
            model.run(self.updates[27060], ss.OPENING_PC)
            self.assertEqual((model.life_grants, model.skills, model.abilities,
                              model.items, model.other), before)

    def test_story_original_opening_stream_is_preserved(self):
        original = ss.layout(self.data.path(27060).read_bytes())['ops']
        patched = ss.layout(self.updates[27060])['ops']
        delta = len(patched) - len(original)
        def relocate(instruction):
            op, value = instruction
            if op in (10, 15, 16) and value >> 8 >= ss.OPENING_PC:
                value += delta << 8
            return op, value
        self.assertEqual(patched[:ss.OPENING_PC], original[:ss.OPENING_PC])
        self.assertEqual(patched[ss.OPENING_PC + delta:],
                         [relocate(x) for x in original[ss.OPENING_PC:]])

    def test_skip_setters_precede_intro_phase_completion(self):
        model = Model(self.plan)
        model.run(self.updates[27060], ss.OPENING_PC)
        reward_pcs = [i for i, (c, _) in enumerate(model.natives) if c in (181, 183, 191, 178)]
        phase_pcs = [i for i, (c, a) in enumerate(model.natives) if c == 62 and a[0] in ss.INTRO]
        self.assertLess(max(reward_pcs), min(phase_pcs))
        # Revision pinning includes every skip resource and shared helper body.
        self.assertEqual(len(self.plan['life_skips']), 12)
        for record in self.plan['life_skips']:
            self.assertEqual(len(record['sha256']), 64)
            self.assertTrue(all(e.get('intro_pcs') for e in record['effects'] if e['native'] == 183))

    def test_story_mode_never_selects_lives_or_grants_skills(self):
        for result in (0, 1, 0xffffffff):
            model = Model(self.plan, current=9)
            model.run(self.updates[27060], ss.OPENING_PC, result)
            self.assertTrue(model.reached_original)
            self.assertEqual(model.life_grants, [])
            self.assertFalse({c for c, _ in model.natives} & {171, 172, 173, 178, 181, 183, 191, 87})

    def test_free_life_without_dlc_is_unchanged(self):
        model = Model(self.plan, flags={1963: False})
        old = copy.deepcopy(model.other)
        model.run(self.updates[27060], ss.OPENING_PC)
        self.assertEqual(model.bliss, 8000)
        self.assertFalse(model.reached_original)
        self.assertEqual(model.ranks, dict.fromkeys(ss.LIVES, 1))
        self.assertEqual(len(model.challenges), 12)
        self.assertTrue(all(model.quests[i] == 3 for i in ss.STORY+ss.FLUTTER+ss.INTRO))
        self.assertEqual({i: model.quests[i] for i in (159, 160)}, {159: 0, 160: 0})
        self.assertEqual({i: model.flags[i] for i in (1963, 1931, 1932, 154)},
                         {1963: False, 1931: False, 1932: False, 154: False})
        self.assertEqual(model.other, dict(old, dosh=old['dosh'] + 6000))
        self.assertTrue(all(not model.flags.get(i, False) for i in (52, 53, 61, 62, 63, 1924)))
        before = copy.deepcopy(model.achievements)
        model.run(self.updates[27060], ss.OPENING_PC)
        self.assertEqual(model.bliss, 8000)
        self.assertEqual(model.report_count, 1)
        self.assertEqual(model.achievements, before)

    def test_free_life_skips_origin_island_when_owned(self):
        model = Model(self.plan, flags={1963: True})
        model.run(self.updates[27060], ss.OPENING_PC)
        self.assertEqual(model.bliss, 8000 + ss.DLC_BLISS_TOTAL)
        self.assertFalse(model.reached_original)
        self.assertEqual(model.report_count, 1, 'both ledgers settle in one report')
        # Origin Island story and its requests are terminal, not merely started.
        self.assertTrue(all(model.quests[q] == 3 for q in ss.DLC_QUESTS))
        for flag in ss.DLC_FLAGS:
            self.assertTrue(model.flags.get(flag, False), f'DLC flag {flag} not set')
        self.assertEqual(model.flags[1963], True, 'entitlement is only read')
        # The God Tower's own level gates stay closed.
        self.assertFalse(model.flags.get(148, False))
        self.assertFalse(model.flags.get(149, False))
        # No independent credit: only the 63 authored rows are marked, and a
        # second run adds nothing.
        self.assertEqual(set(model.achievements), {r['row'] for r in self.plan['bliss']}
                                              | set(ss.DLC_BLISS))
        before = copy.deepcopy(model.achievements)
        model.run(self.updates[27060], ss.OPENING_PC)
        self.assertEqual(model.bliss, 12600)
        self.assertEqual(model.report_count, 1)
        self.assertEqual(model.achievements, before)

    def test_dlc_installed_after_the_choice_is_skipped_at_the_gate(self):
        model = Model(self.plan, flags={1963: False})
        model.run(self.updates[27060], ss.OPENING_PC)
        self.assertEqual(model.bliss, 8000)
        self.assertEqual(model.quests[159], 0)
        self.assertFalse(model.flags[1963])
        # The expansion becomes owned later; the shipped SYS003 gate runs.
        model.flags[1963] = True
        model.sounds.clear()
        model.run(self.updates[27679], ss.DLC_GATE_PC + 1)
        self.assertFalse(model.reached_original, 'the original story start ran anyway')
        self.assertEqual(model.started, [])
        self.assertTrue(all(model.quests[q] == 3 for q in ss.DLC_QUESTS))
        self.assertTrue(all(model.flags.get(flag, False) for flag in ss.DLC_FLAGS))
        # The gate never opens the report itself: settlement stays with the UI.
        self.assertEqual(model.report_count, 1)

    def test_gate_is_inert_for_story_mode_and_on_repeat(self):
        # No marker 49: the shipped story start is untouched at level 50.
        model = Model(self.plan, flags={1963: True}, level=50, quests={116: 3, 117: 3})
        model.run(self.updates[27679], ss.DLC_GATE_PC + 1)
        self.assertEqual(model.started, [], 'gate must not write quests')
        self.assertTrue(model.reached_original, 'shipped start should still be reached')
        # Marker set (Free Life) but the expansion arrives at level 1: the gate
        # applies the completed state instead of the level-gated story start.
        model = Model(self.plan, flags={1963: True, 49: True})
        model.run(self.updates[27679], ss.DLC_GATE_PC + 1)
        self.assertEqual(model.started, [])
        self.assertTrue(all(model.quests[q] == 3 for q in ss.DLC_QUESTS))
        writes = [n for n in model.natives if n[0] in (65, 62, 79)]
        self.assertTrue(writes, 'the first gate run should write the DLC state')
        model.run(self.updates[27679], ss.DLC_GATE_PC + 1)
        self.assertEqual([n for n in model.natives if n[0] in (65, 62, 79)], writes,
                         'the gate reapplied its state')

    def test_settlement_waits_for_the_report_then_restores_music(self):
        model = Model(self.plan, poll_open=3)
        model.run(self.updates[27060], ss.OPENING_PC)
        settle = [i for i, (c, _) in enumerate(model.natives) if c == 344]
        self.assertEqual(len(settle), 1)
        after = model.natives[settle[0]:]
        order = [c for c, _ in after]
        self.assertIn(487, order, 'settlement was not polled for completion')
        self.assertLess(order.index(487), order.index(382),
                        'the landing BGM must be re-asserted after the report closes')
        self.assertLess(order.index(382), order.index(130),
                        'music restore must precede the chapter teardown')
        self.assertEqual(model.sounds[-1], (ss.LANDING_BGM, 0))
        self.assertNotIn(382, [c for c, _ in model.natives[:settle[0]]])
        # Each poll waits real frames instead of spinning on the VM.
        self.assertGreaterEqual(model.waits.count(ss.SETTLE_FRAMES), 3)
        # A report that never closes cannot hang the script.
        model = Model(self.plan, poll_open=10 ** 6)
        model.run(self.updates[27060], ss.OPENING_PC)
        self.assertLessEqual(model.polls, ss.SETTLE_POLLS)
        self.assertEqual(model.sounds[-1], (ss.LANDING_BGM, 0))

    def test_nine_language_reward_tables_match_and_messages_round_trip(self):
        for id_ in (5791,) + tuple(range(5802, 5810)):
            rows = self.data.rows(id_)
            self.assertEqual(sum(rows[r['row']]['c03'] for r in self.plan['bliss']), 8000)
            self.assertEqual(sum(rows[row]['c03'] for row in ss.DLC_BLISS),
                             ss.DLC_BLISS_TOTAL)
        for id_ in ss.TEXT_IDS:
            raw = self.updates[id_]
            self.assertEqual(ss.scr.build(ss.scr.dump(raw, id_)), raw)
            before, _ = ss.vm.sections(self.data.path(id_).read_bytes())
            after, _ = ss.vm.sections(raw)
            original, patched = ss.scr.decode_section(before)['rows'], ss.scr.decode_section(after)['rows']
            for i in range(626):
                if i not in (566, 567, 568, 569):
                    self.assertEqual(original[i], patched[i])

    def test_guild_gate_and_original_vm_relocation(self):
        raw = self.updates[21172]
        after = ss.layout(raw)
        before = ss.layout(self.data.path(21172).read_bytes())
        self.assertEqual(before['pool'], after['pool'])
        self.assertEqual(len(after['ops'])-len(before['ops']), 4)
        # Check every original instruction survives in order with only branch
        # operands relocated. The four inserted gate instructions are the only
        # new instructions, preserving multiplayer/selection/report paths.
        native = [(op, val) for op, val in after['ops'] if op == 7 and val >> 8 == 66]
        self.assertEqual(len(native), sum(op == 7 and val >> 8 == 66 for op, val in before['ops'])+1)
        old = [(op, None if op in ss.vm.BRANCHES else val) for op, val in before['ops']]
        new = [(op, None if op in ss.vm.BRANCHES else val) for op, val in after['ops']]
        insert = next(i for i in range(len(new)-3)
                      if new[i:i+4] == [(1, 49), (7, 66 << 8), (17, 13), (17, 10)])
        self.assertEqual(new[:insert]+new[insert+4:], old)
        self.assertEqual(ss.vm.assemble(ss.vm.disassemble(raw)), raw)

    def test_entitlement_table_and_flags_are_never_written(self):
        self.assertNotIn(5780, self.updates, 'the EC table must stay untouched')
        for id_ in (27060, 21172, 27679):
            raw = self.updates[id_]
            ops = ss.layout(raw)['ops']
            for pc in range(len(ops)):
                args = ss.literals(ops, pc, 65, 2)
                if args:
                    self.assertNotIn(args[0], (1963, 1968),
                                     f'resource {id_} PC {pc} writes an entitlement flag')

    def test_dlc_gate_is_a_pure_insertion_before_the_shipped_check(self):
        raw = self.updates[27679]
        before = ss.layout(self.data.path(27679).read_bytes())['ops']
        after = ss.layout(raw)['ops']
        old = [(op, None if op in ss.vm.BRANCHES else val) for op, val in before]
        new = [(op, None if op in ss.vm.BRANCHES else val) for op, val in after]
        # The shipped chain that decides "DLC owned, requests done, level >= 50,
        # story not started" starts at PC 5518 with `alloc 2`; the gate is
        # inserted right after it and before the first flag test.
        self.assertEqual(old[ss.DLC_GATE_PC], (14, 2))
        self.assertEqual(old[ss.DLC_GATE_PC + 1:ss.DLC_GATE_PC + 3],
                         [(1, 1963), (7, 66 << 8)])
        insert = ss.DLC_GATE_PC + 1
        extra = len(new) - len(old)
        self.assertEqual(new[:insert] + new[insert+extra:], old)
        self.assertTrue(extra > 0)
        self.assertEqual(ss.vm.assemble(ss.vm.disassemble(raw)), raw)


if __name__ == '__main__':
    unittest.main()
