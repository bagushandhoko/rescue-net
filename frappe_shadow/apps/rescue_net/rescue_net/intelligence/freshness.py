from frappe.utils import get_datetime, now_datetime


DEFAULT_POLICY = {
    "report": 360,
    "need": 180,
    "posko": 180,
    "evidence": 1440,
}


def freshness(
    source_updated_at=None,
    observed_at=None,
    modified=None,
    policy_minutes=None,
    data_type="need",
):
    # Frappe modified adalah waktu perubahan record sistem,
    # BUKAN bukti kapan kondisi lapangan terakhir diperbarui.
    timestamp = (
        source_updated_at
        or observed_at
    )

    if not timestamp:
        return {
            "status": "unknown",
            "age_minutes": None,
            "timestamp": None,
            "policy_minutes": (
                policy_minutes
                or DEFAULT_POLICY.get(data_type, 180)
            ),
        }

    stamp = get_datetime(timestamp)
    age = max(
        0,
        (now_datetime() - stamp).total_seconds() / 60,
    )

    policy = int(
        policy_minutes
        or DEFAULT_POLICY.get(data_type, 180)
    )

    if age <= policy:
        status = "fresh"
    elif age <= policy * 2:
        status = "aging"
    else:
        status = "stale"

    return {
        "status": status,
        "age_minutes": round(age, 1),
        "timestamp": str(stamp),
        "policy_minutes": policy,
    }
