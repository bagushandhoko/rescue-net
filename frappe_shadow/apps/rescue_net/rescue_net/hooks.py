app_name = "rescue_net"
app_title = "Rescue-Net"
app_publisher = "Rescue-Net"
app_description = "Rescue-Net shadow migration app"
app_email = "bagushandhoko@gmail.com"
app_license = "MIT"

# Rescue-Net authenticated identity bridge
on_login = "rescue_net.migration.identity_bridge.handle_identity_on_login"

after_install = [
    "rescue_net.setup.normalization_defaults.install_defaults",
    "rescue_net.setup.unit_conversion_defaults.install_defaults",
    "rescue_net.setup.org_brand_defaults.install_defaults",
    "rescue_net.setup.membership_defaults.install_defaults",
    "rescue_net.setup.verifier_defaults.install_defaults",
    "rescue_net.setup.rehab_forum_defaults.install_defaults",
    "rescue_net.setup.tender_defaults.install_defaults",
]

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
]
