# Frappe Shadow Runtime Ops

This directory mirrors the runtime compose file used by /volume1/docker/osiun-frappe-shadow.

The Rescue-Net Frappe app is mounted persistently from pps/rescue_net into backend, worker, and scheduler containers. Each container installs the app editable before starting its Frappe process so recreated containers can import 
escue_net without manual docker copy.

Current mode remains shadow-only. This file does not authorize production reroute or cutover.
