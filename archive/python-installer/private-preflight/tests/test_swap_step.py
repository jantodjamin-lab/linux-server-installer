import unittest
from dataclasses import replace
from unittest.mock import patch
from infrastructure.installer.swap_step import Plan, Observation, Context, Stop, simulate, conditions
from infrastructure.installer.swap_validation import validate_post, compare_runs


class SwapTests(unittest.TestCase):
    def setUp(self):
        self.plan = Plan('/fictional-swap', 4096, 3072, 8192, '# fictional\n', 'fixture-release')
        self.pre = Observation(('fake-host', 'fake-pin', 'fake-provider', 'g1', 'm1', 'b1'),
                               100, True, 'PASS', True, 65536, '# fictional\n',
                               0, 0, 0, 0, (), None, ('config-v1', 'services-v1', 'ports-v1'))
        self.ctx = Context(self.pre.identity, 101, 10, True, 'FICTIONAL-GO')

    def test_transition_is_pure_and_idempotent(self):
        with patch('subprocess.run', side_effect=AssertionError), patch('socket.socket', side_effect=AssertionError):
            post, actions = simulate(self.plan, self.pre, self.ctx)
            again, no_actions = simulate(self.plan, post, self.ctx)
        self.assertEqual(len(actions), 6)
        self.assertEqual(again, post)
        self.assertEqual(no_actions, ())
        self.assertEqual(self.pre.file_bytes, 0)
        self.assertEqual(validate_post(self.plan, self.pre, post, self.ctx)['status'], 'PASS')

    def test_pre_stop_conditions(self):
        for changes in ({'complete': False}, {'preflight': 'WARN'}, {'preflight': 'FAIL'},
                        {'compatible': False}, {'observed_at': 0}, {'observed_at': 102},
                        {'identity': ('other',)}, {'free_bytes': 8192}, {'file_bytes': 1},
                        {'active': (('/other', 10),)}, {'fstab': '# drift\n'}, {'backup': 'partial'}):
            with self.subTest(changes=changes), self.assertRaises(Stop):
                conditions(self.plan, replace(self.pre, **changes), self.ctx)
        for changes in ({'human_present': False}, {'go_reference': ''}, {'max_age': 0}):
            with self.subTest(changes=changes), self.assertRaises(Stop):
                conditions(self.plan, self.pre, replace(self.ctx, **changes))

    def test_partial_install_never_retries(self):
        post, _ = simulate(self.plan, self.pre, self.ctx)
        for changes in ({'mode': 0o644}, {'uid': 1}, {'active': ()}, {'backup': None},
                        {'fstab': self.pre.fstab}, {'file_bytes': 4095}):
            with self.subTest(changes=changes), self.assertRaises(Stop):
                simulate(self.plan, replace(post, **changes), self.ctx)

    def test_independent_post_rejects_effects_and_wrong_results(self):
        post, _ = simulate(self.plan, self.pre, self.ctx)
        for changes in ({'mode': 0o644}, {'gid': 1}, {'active': (('/fictional-swap', 3000),)},
                        {'file_bytes': 4095}, {'backup': 'wrong'}, {'fstab': 'wrong'},
                        {'unchanged': ('changed',)}, {'identity': ('other',)},
                        {'complete': False}, {'observed_at': 102}, {'free_bytes': 1}):
            with self.subTest(changes=changes):
                self.assertEqual(validate_post(self.plan, self.pre, replace(post, **changes), self.ctx)['status'], 'FAIL')

    def test_post_rejects_invalid_pre_and_unexplained_space_change(self):
        post, _ = simulate(self.plan, self.pre, self.ctx)
        for pre in (replace(self.pre, complete=False), replace(self.pre, active=(('/old', 1),))):
            self.assertEqual(validate_post(self.plan, pre, post, self.ctx)['status'], 'FAIL')
        self.assertEqual(validate_post(self.plan, self.pre, replace(post, free_bytes=post.free_bytes+1),
                                      self.ctx)['status'], 'FAIL')

    def test_restore_comparison_preserves_configuration(self):
        post1, _ = simulate(self.plan, self.pre, self.ctx)
        pre2 = replace(self.pre, identity=('fake-host', 'fake-pin', 'fake-provider', 'g2', 'm1', 'b2'), observed_at=200)
        ctx2 = replace(self.ctx, identity=pre2.identity, now=201)
        post2, _ = simulate(self.plan, pre2, ctx2)
        self.assertEqual(compare_runs(self.plan, self.pre, post1, self.ctx, pre2, post2, ctx2)['status'], 'PASS')
        changed_pre = replace(pre2, unchanged=('version-2',))
        changed_post = replace(post2, unchanged=('version-2',))
        self.assertEqual(compare_runs(self.plan, self.pre, post1, self.ctx, changed_pre, changed_post, ctx2)['status'], 'FAIL')
        with self.assertRaises(Stop):
            compare_runs(self.plan, self.pre, post1, self.ctx, self.pre, post1, self.ctx)

    def test_invalid_open_plan_values(self):
        for changes in ({'path': '/a/../b'}, {'path': '/etc/fstab'}, {'path': '/a b'},
                        {'size_bytes': True}, {'active_bytes': 0}, {'reserve_bytes': -1},
                        {'fstab_before': '/old none swap sw 0 0\n'}, {'release': ''}):
            with self.subTest(changes=changes), self.assertRaises(Stop):
                replace(self.plan, **changes)
