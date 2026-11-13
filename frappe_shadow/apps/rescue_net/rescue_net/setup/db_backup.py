import os
import shutil
from datetime import datetime, timedelta

import frappe

# Frappe core ships backup jobs, but every one of them (dropbox_settings.
# take_backups_daily, s3_backup_settings.take_backups_daily, google_drive.
# daily_backup) is a no-op unless the matching cloud-storage Settings
# doctype is configured and enabled — none are here, so this site had zero
# backups ever taken. This registers a plain local daily backup instead.
#
# Backups land in two places:
#   1. sites/<site>/private/backups/  (Frappe's own default location —
#      frappe.utils.backups.delete_temp_backups prunes this by
#      keep_backups_for_hours, default 6h, so nothing here is durable).
#   2. sites/backups_retained/<site>/<timestamp>/  — a sibling directory
#      outside any single site's own folder, so it survives an accidental
#      `rm -rf sites/<site>` or a misconfigured keep_backups_for_hours.
#      Both are still on the same bind-mounted host path
#      (/volume1/docker/osiun-frappe-shadow/sites), i.e. NOT genuine
#      off-box/off-volume backup — see HANDOVER.md for that caveat.

RETENTION_DAYS = 30


def _retained_backup_dir():
    sites_dir = os.path.dirname(
        frappe.utils.get_site_path()
    )
    path = os.path.join(
        sites_dir,
        "backups_retained",
        frappe.local.site,
    )
    os.makedirs(path, exist_ok=True)
    return path


def run_daily_backup():
    return run_backup("lengkap")


def run_backup(jenis="lengkap"):
    """jenis "lengkap" = database + berkas publik/privat + konfigurasi situs (berisi kunci enkripsi; bisa
    dipulihkan di server lain). "data" = database saja (owner 2026-11-13)."""
    from frappe.utils.backups import new_backup

    data_only = jenis == "data"
    odb = new_backup(
        ignore_files=data_only,
        force=True,
    )

    dest_root = _retained_backup_dir()
    stamp = datetime.now().strftime(
        "%Y%m%d-%H%M%S"
    )
    run_dir = os.path.join(dest_root, stamp)
    os.makedirs(run_dir, exist_ok=True)

    attrs = ("backup_path_db",) if data_only else (
        "backup_path_db",
        "backup_path_files",
        "backup_path_private_files",
        "backup_path_conf",
    )
    for attr in attrs:
        src = getattr(odb, attr, None)
        if src and os.path.isfile(src):
            shutil.copy2(src, run_dir)
    with open(os.path.join(run_dir, "JENIS.txt"), "w") as fh:
        fh.write("data" if data_only else "lengkap")

    _prune_old_backups(dest_root)
    return stamp


def _prune_old_backups(
    dest_root,
    retention_days=RETENTION_DAYS,
):
    cutoff = datetime.now() - timedelta(
        days=retention_days
    )

    for name in os.listdir(dest_root):
        full = os.path.join(dest_root, name)

        if not os.path.isdir(full):
            continue

        try:
            stamp = datetime.strptime(
                name, "%Y%m%d-%H%M%S"
            )
        except ValueError:
            continue

        if stamp < cutoff:
            shutil.rmtree(
                full, ignore_errors=True
            )
