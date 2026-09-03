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
]

# Re-seed the editable rule tables after every migrate. Both installers are
# idempotent — they skip any row whose name already exists.
after_migrate = [
    "rescue_net.setup.normalization_defaults.install_defaults",
    "rescue_net.setup.unit_conversion_defaults.install_defaults",
]
