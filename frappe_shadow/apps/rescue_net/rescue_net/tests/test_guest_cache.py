"""Guest cache for heavy public feeds (load test S10, 2026-10-26)."""

from unittest import mock

import frappe

from rescue_net.services.guest_cache import guest_cache
from rescue_net.tests.factories import RNTestCase, as_guest, as_user, make_actor

CALLS = []


@guest_cache(30)
def _feed(x=1):
    CALLS.append(x)
    return {"x": x, "n": len(CALLS)}


class TestGuestCache(RNTestCase):
    def setUp(self):
        super().setUp()
        CALLS.clear()
        store = {}
        fake = mock.Mock()
        fake.get_value.side_effect = store.get
        fake.set_value.side_effect = lambda k, v, expires_in_sec=None: store.__setitem__(k, v)
        self._p = mock.patch.object(frappe, "cache", return_value=fake)
        self._p.start()
        self._in_test, frappe.flags.in_test = frappe.flags.in_test, False

    def tearDown(self):
        frappe.flags.in_test = self._in_test
        self._p.stop()
        super().tearDown()

    def test_guest_gets_cached_copy_per_args(self):
        with as_guest():
            self.assertEqual(_feed(x=1)["n"], 1)
            self.assertEqual(_feed(x=1)["n"], 1)
            self.assertEqual(_feed(x=2)["n"], 2)
        self.assertEqual(CALLS, [1, 2])

    def test_logged_in_user_always_fresh(self):
        self._p.stop()
        u = make_actor().user
        self._p.start()
        with as_user(u):
            _feed(x=1)
            _feed(x=1)
        self.assertEqual(CALLS, [1, 1])
