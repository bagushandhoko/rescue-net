app_name = "rescue_net"
app_title = "Rescue-Net"
app_publisher = "Rescue-Net"
app_description = "Rescue-Net shadow migration app"
app_email = "bagushandhoko@gmail.com"
app_license = "MIT"

# Rescue-Net authenticated identity bridge
on_login = "rescue_net.identity_bridge.handle_identity_on_login"

after_install = [
    "rescue_net.setup.normalization_defaults.install_defaults",
    "rescue_net.setup.unit_conversion_defaults.install_defaults",
    "rescue_net.setup.org_brand_defaults.install_defaults",
    "rescue_net.setup.membership_defaults.install_defaults",
    "rescue_net.setup.verifier_defaults.install_defaults",
    "rescue_net.setup.rehab_forum_defaults.install_defaults",
    "rescue_net.setup.tender_defaults.install_defaults",
    "rescue_net.setup.notification_defaults.install_defaults",
]

# Frappe core's own backup jobs (dropbox/S3/Google Drive) are all no-ops
# unless that cloud storage is configured — this site had none, so zero
# backups were ever taken. See rescue_net.setup.db_backup for the caveats
# (still same host volume, not genuine off-box backup).
scheduler_events = {
    "daily": [
        "rescue_net.setup.db_backup.run_daily_backup",
    ],
}

# Re-seed the editable rule tables after every migrate. All installers are
# idempotent — they skip any row whose name already exists (org_brand_defaults
# also skips any org whose brand_color was set by hand in Desk).
after_migrate = [
    "rescue_net.setup.normalization_defaults.install_defaults",
    "rescue_net.setup.unit_conversion_defaults.install_defaults",
    "rescue_net.setup.org_brand_defaults.install_defaults",
    "rescue_net.setup.membership_defaults.install_defaults",
    "rescue_net.setup.verifier_defaults.install_defaults",
    "rescue_net.setup.rehab_forum_defaults.install_defaults",
    "rescue_net.setup.tender_defaults.install_defaults",
    "rescue_net.setup.notification_defaults.install_defaults",
]
