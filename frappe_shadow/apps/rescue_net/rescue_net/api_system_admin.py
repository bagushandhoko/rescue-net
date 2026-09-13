import json
import os
import shlex
import subprocess
from datetime import datetime

import frappe


def _require_system_manager():
    if frappe.session.user in (None, "", "Guest"):
        frappe.throw("Silakan login dahulu.", frappe.AuthenticationError)
    if "System Manager" not in frappe.get_roles(frappe.session.user):
        frappe.throw(
            "Hanya System Manager (Administrator) yang boleh mengakses backup/restore database.",
            frappe.PermissionError,
        )


def _retained_dir():
    from rescue_net.setup.db_backup import _retained_backup_dir

    return _retained_backup_dir()


def _status_path():
    return os.path.join(_retained_dir(), "restore_status.json")


def _backup_files(backup_dir):
    files = {}
    for fn in os.listdir(backup_dir):
        if fn.endswith("database.sql.gz"):
            files["database"] = fn
        elif fn.endswith("private-files.tar"):
            files["private_files"] = fn
        elif fn.endswith("-files.tar"):
            # only the plain "-files.tar" (not "-private-files.tar")
            if "private-files" not in fn:
                files["files"] = fn
        elif fn.endswith("site_config_backup.json"):
            files["site_config"] = fn
    return files


@frappe.whitelist()
def list_backups():
    """Every retained daily-backup snapshot on disk, newest first.

    System Manager only. Same directory the `daily` scheduler job
    (rescue_net.setup.db_backup.run_daily_backup) already writes to —
    see HANDOVER.md for why this local-disk location exists.
    """
    _require_system_manager()

    root = _retained_dir()
    rows = []

    for name in sorted(os.listdir(root), reverse=True):
        full = os.path.join(root, name)
        if not os.path.isdir(full):
            continue
        try:
            datetime.strptime(name, "%Y%m%d-%H%M%S")
        except ValueError:
            continue

        files = _backup_files(full)
        total = sum(
            os.path.getsize(os.path.join(full, fn)) for fn in files.values()
        )

        rows.append({
            "timestamp": name,
            "size_bytes": total,
            "has_database": "database" in files,
            "files": files,
        })

    return {
        "site": frappe.local.site,
        "backups": rows,
        "restore_status": _read_status(),
    }


@frappe.whitelist()
def trigger_backup():
    """Run an on-demand backup right now (in addition to the daily one)."""
    _require_system_manager()

    from rescue_net.setup.db_backup import run_daily_backup

    run_daily_backup()

    frappe.logger().info(
        f"[system-admin] manual backup triggered by {frappe.session.user}"
    )

    return list_backups()


def _read_status():
    p = _status_path()
    if not os.path.exists(p):
        return {"state": "idle"}
    try:
        with open(p) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"state": "idle"}


@frappe.whitelist()
def restore_status():
    _require_system_manager()
    return _read_status()


@frappe.whitelist()
def restore_backup(backup_timestamp, confirm_site_name):
    """Restore the site's database (+files, if present) from a retained
    snapshot. System Manager only, extremely destructive by nature:

    1. Refuses unless `confirm_site_name` is typed exactly (the site name).
    2. Takes one more safety snapshot of the CURRENT state first, so a
       restore can itself always be undone.
    3. Runs `bench --site <site> --force restore ...` as a detached OS
       process (never in-process) — bench's own restore path calls
       frappe.init()/drops+recreates the schema, which must never happen
       inside the live worker handling this very request.
    4. Writes progress to restore_status.json; poll restore_status().

    Caveat surfaced to the operator in the UI: after a restore completes,
    the already-running backend/worker/scheduler containers are still
    holding pre-restore state (redis cache, in-memory metadata) and
    should be restarted from the host (`docker restart osiun-frappe-*`)
    for a fully clean state — this method has no docker-socket access to
    do that itself from inside the container.
    """
    _require_system_manager()

    site = frappe.local.site
    if confirm_site_name != site:
        frappe.throw(f"Nama situs tidak cocok. Ketik persis: {site}")

    root = _retained_dir()
    backup_dir = os.path.join(root, backup_timestamp)
    if not os.path.isdir(backup_dir):
        frappe.throw("Snapshot backup tidak ditemukan.")

    files = _backup_files(backup_dir)
    if "database" not in files:
        frappe.throw("File database (.sql.gz) tidak ada di snapshot ini.")

    status_path = _status_path()
    current = _read_status()
    if current.get("state") == "running":
        frappe.throw("Ada proses restore lain yang masih berjalan.")

    # Safety snapshot of what's live RIGHT NOW, before we overwrite it.
    from rescue_net.setup.db_backup import run_daily_backup

    run_daily_backup()

    started_at = frappe.utils.now_datetime().isoformat()
    with open(status_path, "w") as f:
        json.dump({
            "state": "running",
            "restoring_from": backup_timestamp,
            "started_at": started_at,
            "started_by": frappe.session.user,
        }, f)

    bench_dir = frappe.utils.get_bench_path()
    sql_gz = os.path.join(backup_dir, files["database"])
    log_path = os.path.join(root, f"restore-{backup_timestamp}.log")

    cmd = ["bench", "--site", site, "--force", "restore", sql_gz]
    if "private_files" in files:
        cmd += ["--with-private-files", os.path.join(backup_dir, files["private_files"])]
    if "files" in files:
        cmd += ["--with-public-files", os.path.join(backup_dir, files["files"])]

    cmd_str = " ".join(shlex.quote(c) for c in cmd)

    script = f"""
cd {shlex.quote(bench_dir)} && {{
  echo "=== restore started $(date -Is), by {shlex.quote(frappe.session.user)} ==="
  {cmd_str}
  code=$?
  bench --site {shlex.quote(site)} clear-cache >/dev/null 2>&1
  echo "=== restore finished $(date -Is) exit=$code ==="
  python3 - "$code" <<'PYEOF'
import json, sys, datetime
code = int(sys.argv[1])
with open({json.dumps(status_path)}, "w") as fh:
    json.dump({{
        "state": "done" if code == 0 else "failed",
        "restoring_from": {json.dumps(backup_timestamp)},
        "exit_code": code,
        "started_at": {json.dumps(started_at)},
        "started_by": {json.dumps(frappe.session.user)},
        "finished_at": datetime.datetime.now().isoformat(),
        "log_file": {json.dumps(log_path)},
    }}, fh)
PYEOF
}} >> {shlex.quote(log_path)} 2>&1
"""

    subprocess.Popen(
        ["bash", "-lc", script],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    frappe.logger().info(
        f"[system-admin] restore from {backup_timestamp} started by {frappe.session.user}"
    )

    return {"state": "running", "restoring_from": backup_timestamp}
