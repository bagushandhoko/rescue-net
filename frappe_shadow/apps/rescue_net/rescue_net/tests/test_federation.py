import hashlib
import hmac
import json
import secrets
import time
from unittest.mock import patch
from uuid import UUID

import frappe
from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Request

from rescue_net import api_federation as api
from rescue_net.federation import outbox, policy
from rescue_net.patches.v2026_11 import federation_identity
from rescue_net.services.admin_areas import import_rows
from rescue_net.tests.factories import RNTestCase, _insert, api_call, as_guest, as_user, make_event, make_org, make_posko, make_user

SENTINEL = "PRIVATE-SENTINEL"
FORBIDDEN = ("reporter_name", "reporter_phone", "reporter_email", "patient_name", "medical_record",
             "donor_contact", "donor_name", "officer_in_charge_phone", "officer_in_charge_email",
             "legacy_payload", "notes", "trace_token", "edit_code_hash", "private_file", "raw_item_text", "title")


class TestFederation(RNTestCase):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")
        self.start = outbox.last_seq()
        self.event = make_event(title=SENTINEL, event_status="active", federation_share=1)
        self.org = make_org(privacy_mode="open", allow_posko_public_choice=1)
        self.posko = make_posko(self.event, self.org, title=SENTINEL, posko_type="shelter",
                                public_detail="public", federation_share=1,
                                officer_in_charge_phone=SENTINEL, officer_in_charge_email=SENTINEL)
        self.peer_id = outbox.new_id()
        self.secret = secrets.token_hex(32)

    def events(self):
        return frappe.get_all(outbox.OUTBOX, filters={"seq": [">", self.start]}, fields=["*"], order_by="seq asc")

    def test_allowlist_and_sequence_for_every_type(self):
        common = dict(title=SENTINEL, disaster_event=self.event.name, quantity=3, unit="kg",
                      federation_share=1, raw_item_text=SENTINEL, legacy_payload=json.dumps({"phone": SENTINEL}))
        _insert(policy.NEED, **common, posko=self.posko.name, need_status="open", reporter_label=SENTINEL)
        _insert(policy.OFFER, **common, target_posko=self.posko.name, donor_name=SENTINEL, donor_contact=SENTINEL)
        _insert(policy.FLOW, **common, destination_posko=self.posko.name, flow_status="planned", receipt_note=SENTINEL)
        _insert(policy.AREA, code="96", area_name=SENTINEL, level="province")
        rows = self.events()
        self.assertEqual({r.object_type for r in rows}, set(policy.POLICIES))
        self.assertEqual([r.seq for r in rows], list(range(self.start + 1, self.start + len(rows) + 1)))
        self.assertEqual(len({r.event_id for r in rows}), len(rows))
        for row in rows:
            payload = json.loads(row.payload)
            rule = policy.POLICIES[row.object_type]
            self.assertTrue(payload)
            self.assertEqual(row.classification, policy.FULL)
            self.assertLessEqual(set(payload), set(rule.fields))
            for field in FORBIDDEN:
                self.assertEqual(rule.field_classification(field), policy.NEVER)
                self.assertNotIn(field, payload)
            self.assertNotIn(SENTINEL, row.payload)
            self.assertEqual(row.payload_checksum, hashlib.sha256(row.payload.encode()).hexdigest())
            self.assertIn(UUID(row.event_id).version, {4, 7})
            self.assertIn(UUID(row.object_uid).version, {4, 7})
            self.assertEqual(row.origin_server_id, outbox.local_id())
            self.assertEqual(len(row.actor_ref), 64)

    def test_policy_denies_unlisted_type_private_records_and_free_text(self):
        before = len(self.events())
        unlisted = make_org(title=SENTINEL)
        outbox.record(unlisted)
        make_posko(self.event, self.org, public_detail="private", federation_share=1, posko_type="shelter")
        make_event(event_status="draft", federation_share=1)
        make_event(event_status="active", is_drill=1, federation_share=1)
        self.assertEqual(len(self.events()), before)
        poison = frappe._dict(doctype=policy.NEED, unit=f"kg {SENTINEL}", need_status=SENTINEL,
                              title=SENTINEL, quantity="11.123@personal.example")
        self.assertEqual(policy.project(poison), {})

    def test_unchanged_save_and_bulk_import_are_idempotent(self):
        before = len(self.events())
        original_uid = self.event.uid
        self.event.title = "Judul baru"
        self.event.uid = outbox.new_id()
        self.event.save(ignore_permissions=True)
        self.assertEqual(self.event.uid, original_uid)
        self.assertEqual(len(self.events()), before)
        self.event.severity = "high"
        self.event.save(ignore_permissions=True)
        self.event.save(ignore_permissions=True)
        self.assertEqual(len(self.events()), before + 1)
        rows = [{"code": "97", "area_name": "Wilayah Uji", "level": "province", "parent_code": ""}]
        self.assertTrue(import_rows(rows, source="uji", dry_run=False)["applied"])
        self.assertTrue(import_rows(rows, source="uji", dry_run=False)["applied"])
        self.assertEqual(len(self.events()), before + 2)

    def test_identity_backfill_leaves_existing_name_and_outbox_alone(self):
        legacy = make_event(event_status="active")
        name = legacy.name
        before = len(self.events())
        frappe.db.set_value(policy.EVENT, name, {"uid": None, "origin_server_id": None})
        federation_identity.execute()
        legacy.reload()
        self.assertEqual(legacy.name, name)
        self.assertIn(UUID(legacy.uid).version, {4, 7})
        self.assertEqual(legacy.origin_server_id, outbox.local_id())
        federation_identity.execute()
        self.assertEqual(frappe.db.get_value(policy.EVENT, name, "uid"), legacy.uid)
        self.assertEqual(len(self.events()), before)

    def test_status_cascade_projects_only_allowed_value(self):
        before = len(self.events())
        outbox.update_fields(policy.EVENT, self.event.name, {"event_status": "closed", "review_note": SENTINEL})
        outbox.update_fields(policy.EVENT, self.event.name, {"event_status": "closed", "review_note": "changed"})
        self.assertEqual(len(self.events()), before + 1)
        event = self.events()[-1]
        self.assertEqual(event.operation, "status")
        self.assertEqual(json.loads(event.payload)["event_status"], "closed")
        self.assertNotIn(SENTINEL, event.payload)

    def test_atomic_rollback_restores_outbox_and_sequence(self):
        count = len(self.events())
        frappe.db.savepoint("federation_atomic")
        transient = make_event(event_status="active", federation_share=1)
        seq = self.events()[-1].seq
        frappe.db.rollback(save_point="federation_atomic")
        self.assertFalse(frappe.db.exists(policy.EVENT, transient.name))
        self.assertEqual(len(self.events()), count)
        make_event(event_status="active", federation_share=1)
        self.assertEqual(self.events()[-1].seq, seq)

    def _register(self, scope=None):
        return api.register_peer(self.peer_id, "Peer Uji", "https://uji.example",
                                 outbox.secret_digest(self.secret), self.secret, scope or [policy.EVENT])

    def _request(self, nonce=None, timestamp=None, secret=None, since=None, limit=100, peer_id=None):
        nonce = nonce or secrets.token_hex(16)
        ts = str(timestamp if timestamp is not None else int(time.time()))
        sender = peer_id or self.peer_id
        body = outbox.encode({"since_seq": self.start if since is None else since, "limit": limit}).encode()
        message = api.signing_bytes(outbox.local_id(), sender, ts, nonce, body)
        signature = hmac.new(bytes.fromhex(secret or self.secret), message, hashlib.sha256).hexdigest()
        return Request(EnvironBuilder(method="POST", data=body, content_type="application/json", headers={
            "X-RN-Peer": sender, "X-RN-Timestamp": ts, "X-RN-Nonce": nonce, "X-RN-Signature": signature,
        }).get_environ())

    def _pull(self, request):
        with as_guest(), patch.object(frappe.local, "request", request, create=True):
            return api_call("rescue_net.api_federation.pull")

    def test_authentication_replay_and_revocation(self):
        with self.assertRaises(frappe.PermissionError):
            self._pull(self._request())
        self.assertEqual(self._register()["status"], "pending")
        with self.assertRaises(frappe.PermissionError):
            self._pull(self._request())
        api.approve_peer(self.peer_id)
        for request in (self._request(secret=secrets.token_hex(32)), self._request(peer_id=outbox.new_id()),
                        self._request(timestamp=int(time.time()) - 301),
                        self._request(timestamp=int(time.time()) + 301)):
            with self.assertRaises(frappe.PermissionError):
                self._pull(request)
        request = self._request()
        result = self._pull(request)
        self.assertEqual([r["object_type"] for r in result["events"]], [policy.EVENT])
        with self.assertRaises(frappe.PermissionError):
            self._pull(request)
        self._pull(self._request(since=result["next_seq"]))
        self.assertEqual(api.status()["peers"][0]["send_cursor"], result["next_seq"])
        api.revoke_peer(self.peer_id)
        with self.assertRaises(frappe.PermissionError):
            self._pull(self._request())
        with self.assertRaises(frappe.ValidationError):
            api.approve_peer(self.peer_id)

    def test_visibility_rechecked_during_pull_and_pages_advance(self):
        self._register([policy.EVENT, policy.POSKO])
        api.approve_peer(self.peer_id)
        self.event.severity = "low"
        self.event.save(ignore_permissions=True)
        self.posko.public_detail = "private"
        self.posko.save(ignore_permissions=True)
        first = self._pull(self._request(limit=1))
        self.assertTrue(first["has_more"])
        second = self._pull(self._request(since=first["next_seq"], limit=1))
        self.assertEqual(second["events"], [])
        self.assertTrue(second["has_more"])
        last = self._pull(self._request(since=second["next_seq"], limit=1))
        self.assertEqual([row["operation"] for row in last["events"]], ["update"])
        self.assertFalse(last["has_more"])

    def test_api_access_and_secret_not_exposed(self):
        ordinary = make_user()
        self._register()
        for user in ("Guest", ordinary):
            with as_user(user):
                for method in ("status", "approve_peer", "revoke_peer", "register_peer"):
                    args = {} if method == "status" else {"server_id": self.peer_id}
                    if method == "register_peer":
                        args.update(name="Nama", url="https://uji.example", key_fingerprint="0" * 64,
                                    shared_secret=self.secret, scope=[policy.EVENT])
                    with self.assertRaises(frappe.PermissionError):
                        api_call(f"rescue_net.api_federation.{method}", **args)
        with as_guest():
            info = api_call("rescue_net.api_federation.node_info")
            self.assertEqual(set(info), {"server_id", "name", "schema_version", "fingerprint"})
            self.assertNotIn(outbox.local_secret(), json.dumps(info))
        self.assertNotIn(self.secret, json.dumps(api.status()))

    def test_only_manager_can_opt_in(self):
        user = make_user()
        with as_user(user):
            event = make_event(event_status="active", federation_share=1)
        self.assertFalse(event.federation_share)
        self.assertFalse(frappe.db.exists(outbox.OUTBOX, {"object_uid": event.uid}))
