"""AI — budget, rate limit, rollup and retention (ADR-0002 sections 5 and 8).

Every provider call goes through `check_allowed` before and `record_usage`
after (`ai/chat.py::_llm_chat`, platform intake). Budgets are in tokens per
owner (user / organization / platform) and are read from the owner's RN AI
Profile; 0 = no limit. The daily rollup (RN AI Usage Daily) outlives the
7-day detail log, so a monthly budget keeps working after the detail is gone.
"""

import json

import frappe
from frappe.utils import add_days, getdate, now_datetime, nowdate

from rescue_net.rn_intelligence.doctype.rn_ai_profile.rn_ai_profile import PLATFORM_OWNER, profile_name
from rescue_net.rn_intelligence.doctype.rn_ai_usage_daily.rn_ai_usage_daily import daily_name

DETAIL_RETENTION_DAYS = 7
# requests per owner per hour; a runaway loop must not drain a key
HOURLY_LIMIT = {"user": 60, "organization": 300, "platform": 600}
LEVEL_OF = {"user": "personal", "organization": "organization", "platform": "platform"}


class AIUnavailable(Exception):
    """The call must not go to the provider. `kind`: disabled / budget / rate."""

    def __init__(self, kind, message):
        super().__init__(message)
        self.kind, self.message = kind, message


def _profile(owner_type, owner_id):
    level = LEVEL_OF[owner_type]
    name = profile_name(level, PLATFORM_OWNER if owner_type == "platform" else owner_id)
    return frappe.db.get_value(
        "RN AI Profile", name, ["status", "daily_budget_tokens", "monthly_budget_tokens"], as_dict=True)


def usage_totals(owner_type, owner_id):
    """(tokens today, tokens this calendar month) from the daily rollup."""
    today = getdate(nowdate())
    month_start = today.replace(day=1)
    rows = frappe.get_all(
        "RN AI Usage Daily", filters={"owner_type": owner_type, "owner_id": owner_id,
                                      "usage_date": [">=", month_start]},
        fields=["usage_date", "total_tokens"], limit_page_length=40)
    day = sum(int(r.total_tokens or 0) for r in rows if getdate(r.usage_date) == today)
    return day, sum(int(r.total_tokens or 0) for r in rows)


def budget_status(owner_type, owner_id):
    prof = _profile(owner_type, owner_id)
    day, month = usage_totals(owner_type, owner_id)
    return {"daily_limit": int(prof.daily_budget_tokens or 0) if prof else 0, "daily_used": day,
            "monthly_limit": int(prof.monthly_budget_tokens or 0) if prof else 0, "monthly_used": month,
            "disabled": bool(prof and prof.status == "disabled")}


def check_allowed(owner_type, owner_id, user_id=None):
    """Raise AIUnavailable when this owner's AI is switched off, out of budget
    or over the hourly rate limit. No profile = no limits except the rate limit."""
    st = budget_status(owner_type, owner_id)
    if st["disabled"]:
        raise AIUnavailable("disabled", "AI dinonaktifkan oleh pengelola untuk konteks ini.")
    for limit, used, label in ((st["daily_limit"], st["daily_used"], "harian"),
                               (st["monthly_limit"], st["monthly_used"], "bulanan")):
        if limit and used >= limit:
            raise AIUnavailable("budget", f"Anggaran AI {label} habis. Perbarui batas atau tunggu periode berikutnya.")
    since = add_days(now_datetime(), -1 / 24)
    recent = frappe.db.count("RN AI Usage Log", {"owner_type": owner_type, "owner_id": owner_id,
                                                 "creation": [">=", since]})
    by_user = frappe.db.count("RN AI Usage Log", {"user_id": user_id, "creation": [">=", since]}) if user_id else 0
    if recent >= HOURLY_LIMIT[owner_type] or by_user >= HOURLY_LIMIT["user"]:
        raise AIUnavailable("rate", "Terlalu banyak permintaan AI dalam satu jam. Coba lagi nanti.")


def record_usage(owner_type, owner_id, tokens, cost, ok):
    """Add one call to today's rollup (atomic increment) and warn at 80% / exhausted."""
    name = daily_name(nowdate(), owner_type, owner_id)
    if not frappe.db.exists("RN AI Usage Daily", name):
        try:
            frappe.get_doc({"doctype": "RN AI Usage Daily", "usage_date": nowdate(), "owner_type": owner_type,
                            "owner_id": owner_id}).insert(ignore_permissions=True)
        except frappe.DuplicateEntryError:
            pass
    frappe.db.sql(
        """update `tabRN AI Usage Daily` set requests = requests + 1, errors = errors + %s,
           total_tokens = total_tokens + %s, est_cost_usd = est_cost_usd + %s where name = %s""",
        (0 if ok else 1, int(tokens or 0), float(cost or 0), name))
    _warn_if_needed(owner_type, owner_id, name)


def _warn_if_needed(owner_type, owner_id, daily_row):
    st = budget_status(owner_type, owner_id)
    flags = frappe.db.get_value("RN AI Usage Daily", daily_row, ["warned_80", "warned_100"], as_dict=True)
    for limit, used, label in ((st["daily_limit"], st["daily_used"], "harian"),
                               (st["monthly_limit"], st["monthly_used"], "bulanan")):
        if not limit:
            continue
        if used >= limit and not flags.warned_100:
            _notify(owner_type, owner_id, f"Anggaran AI {label} habis ({used}/{limit} token).")
            frappe.db.set_value("RN AI Usage Daily", daily_row, "warned_100", 1)
            flags.warned_100 = 1
        elif used >= 0.8 * limit and not flags.warned_80:
            _notify(owner_type, owner_id, f"Anggaran AI {label} mencapai 80% ({used}/{limit} token).")
            frappe.db.set_value("RN AI Usage Daily", daily_row, "warned_80", 1)
            flags.warned_80 = 1


def _notify(owner_type, owner_id, subject):
    """In-app Notification Log to whoever manages that key: the user, the
    organisation owners, or the System Managers for the platform key."""
    users = set()
    try:
        if owner_type == "user":
            users.add(owner_id)
        elif owner_type == "organization":
            accounts = frappe.get_all("RN Organization Membership", filters={
                "organization": owner_id, "membership_role": "owner", "status": "approved"},
                pluck="user_account", limit_page_length=50)
            for a in accounts:
                u = frappe.db.get_value("RN User Account", a, "frappe_user")
                if u:
                    users.add(u)
        else:
            users.update(frappe.get_all("Has Role", filters={"role": "System Manager", "parenttype": "User"},
                                        pluck="parent", limit_page_length=50))
        for u in users:
            if u and u not in ("Guest",) and frappe.db.exists("User", u):
                frappe.get_doc({"doctype": "Notification Log", "for_user": u, "type": "Alert",
                                "subject": subject}).insert(ignore_permissions=True)
    except Exception:
        frappe.log_error(title="rn_ai budget notify failed")


def purge_usage_logs():
    """Daily job: delete RN AI Usage Log detail older than the retention
    window. The rollup keeps the totals. The cutoff is a date, never a list."""
    cutoff = add_days(now_datetime(), -DETAIL_RETENTION_DAYS)
    frappe.db.delete("RN AI Usage Log", {"creation": ["<", cutoff]})
    return cutoff
