import hashlib
import json
import re

import frappe
from frappe.model.document import Document

from rescue_net.services import llm

PLATFORM_OWNER = "__platform__"  # same owner id as the platform key (rescue_net/ai/common.py)
SCOPE_BY_LEVEL = {"personal": "user_permission", "organization": "organization", "platform": "aggregate"}
KEY_OWNER_TYPE = {"personal": "user", "organization": "organization", "platform": "platform"}
TOOL_NAME = re.compile(r"^[a-z][a-z0-9_]{1,63}$")


def profile_name(level, owner_id):
    raw = f"{level}|{(owner_id or '').strip().lower()}"
    return "rn-aiprof-" + hashlib.sha256(raw.encode()).hexdigest()[:24]


class RNAIProfile(Document):
    """One AI profile per owner (one engine, many profiles - ADR-0002 section 4).

    The profile never holds a secret: the key stays in RN AI User Setting
    (Password field) and is referenced through `key_setting`. The rules here
    hold for Desk, imports and the API alike."""

    def autoname(self):
        self.name = profile_name(self.level, self.owner_id)

    def validate(self):
        self.owner_id = (self.owner_id or "").strip()
        if self.level == "platform":
            self.owner_id = PLATFORM_OWNER
        elif not self.owner_id:
            frappe.throw("Pemilik profil AI wajib diisi.")
        self.data_scope = SCOPE_BY_LEVEL[self.level]

        try:
            self.provider = llm.normalize_provider(self.provider)
        except llm.LLMError:
            frappe.throw("Provider AI tidak didukung.")
        self.model_name = (self.model_name or "").strip() or llm.default_model(self.provider)
        self._check_endpoint()
        self._check_key()
        self._check_tools()
        for f in ("daily_budget_tokens", "monthly_budget_tokens"):
            if int(self.get(f) or 0) < 0:
                frappe.throw("Batas anggaran tidak boleh negatif.")
        daily, monthly = int(self.daily_budget_tokens or 0), int(self.monthly_budget_tokens or 0)
        if daily and monthly and daily > monthly:
            frappe.throw("Batas harian tidak boleh lebih besar dari batas bulanan.")

    def _check_endpoint(self):
        if self.provider == "local":
            try:
                self.base_url = llm.validate_base_url(self.base_url)
            except llm.LLMError:
                frappe.throw("Alamat model lokal tidak valid (http/https, tanpa kredensial, bukan alamat link-local).")
        else:
            self.base_url = None

    def _check_key(self):
        if self.provider == "local":
            self.key_setting = None  # a local endpoint needs no BYOK key
            return
        from rescue_net.ai.common import _setting_name
        from rescue_net.ai.keys import _org_setting_name

        if self.level == "personal":
            name = _setting_name(self.owner_id, self.provider)
        else:
            name = _org_setting_name(self.owner_id, self.provider)
        setting = frappe.db.get_value(
            "RN AI User Setting", name, ["status", "owner_type", "owner_id"], as_dict=True)
        if not setting or setting.status != "active":
            frappe.throw("Belum ada kunci AI aktif untuk provider ini pada pemilik profil.")
        if setting.owner_type != KEY_OWNER_TYPE[self.level] or (
                setting.owner_id or "") != self.owner_id:
            frappe.throw("Kunci AI bukan milik pemilik profil ini.")
        self.key_setting = name

    def _check_tools(self):
        try:
            tools = json.loads(self.allowed_tools or "[]")
        except ValueError:
            tools = None
        if not isinstance(tools, list) or not all(isinstance(t, str) and TOOL_NAME.match(t) for t in tools):
            frappe.throw("Daftar tool yang diizinkan harus berupa JSON list nama tool.")
        self.allowed_tools = json.dumps(sorted(set(tools)))
