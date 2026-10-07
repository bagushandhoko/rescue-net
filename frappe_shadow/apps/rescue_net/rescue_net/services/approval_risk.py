"""Verification & Approval: trust / risk of a queue item from real signals.

Three signals, each 0-100, plain average (no model, no hidden weights):
  identity  - the creator is a registered account with phone and e-mail
  track     - share of the creator's earlier decided items that were approved
  evidence  - how much evidence is linked to the item
Risk label: score >= 75 Rendah, >= 50 Sedang, else Tinggi.
"""

import frappe

APPROVED = {"approved", "verified", "official_verified", "community_verified"}
REJECTED = {"rejected"}
SIGNALS = (
    ("identity", "Identitas Pembuat"),
    ("track", "Rekam Jejak"),
    ("evidence", "Kelengkapan Bukti"),
)


def risk_label(score):
    return "Rendah" if score >= 75 else "Sedang" if score >= 50 else "Tinggi"


def evidence_signal(count):
    return {0: 0, 1: 50, 2: 75}.get(int(count or 0), 100)


class Context:
    """Per-request caches so a 300-row queue costs a handful of queries."""

    def __init__(self, families):
        self._accounts = {}
        self._track = None
        self._families = families

    def identity(self, owner):
        if not owner or owner == "-":
            return 20
        if owner == "Administrator":
            return 100
        if owner not in self._accounts:
            self._accounts[owner] = frappe.db.get_value(
                "RN User Account", {"frappe_user": owner}, ["phone", "email"], as_dict=True)
        acc = self._accounts[owner]
        if not acc:
            return 20
        return 40 + (30 if acc.phone else 0) + (30 if acc.email else 0)

    def track(self, owner):
        if self._track is None:
            self._track = {}
            for doctype, field in self._families:
                try:
                    rows = frappe.get_all(doctype, fields=["owner", field + " as st", "count(name) as n"],
                                          group_by="owner, " + field, limit_page_length=5000)
                except Exception:
                    continue
                for r in rows:
                    t = self._track.setdefault(r.owner, [0, 0])
                    if r.st in APPROVED:
                        t[0] += r.n
                    elif r.st in REJECTED:
                        t[1] += r.n
        ok, bad = self._track.get(owner, [0, 0])
        return 50 if ok + bad == 0 else round(100 * ok / (ok + bad))

    def score(self, owner, evidence_count):
        sig = {"identity": self.identity(owner), "track": self.track(owner), "evidence": evidence_signal(evidence_count)}
        total = round(sum(sig.values()) / len(sig))
        return total, sig
