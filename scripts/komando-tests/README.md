# Komando terpusat — tests (real login, live site)

Run order (container `osiun-frappe-backend`, site `osiun.localhost`):

    docker exec -i -w /home/frappe/frappe-bench/sites osiun-frappe-backend ../env/bin/python - < clean_test_data.py
    docker exec -i -w /home/frappe/frappe-bench/sites osiun-frappe-backend ../env/bin/python - < setup_test_users.py
    python3 api_e2e.py                 # 86 checks (incl. wakil pusat, set_posko_functions gate), real sessions over 127.0.0.1:8095
    docker exec ... < check_notify.py  # 4 checks: WhatsApp rows in RN Notification Log (run right after api_e2e.py)
    node page_jsdom.js                 # 41 checks; needs `npm i jsdom@22` next to it; runs the real page JS in jsdom
    docker exec ... < clean_test_data.py

Test data is only `@cmdtest.local` accounts and orgs titled `[UJI-KOMANDO] ...`.
`clean_test_data.py` skips any delete whose id list is empty (a previous version without that
guard wiped 5 real poskos — see HANDOVER 2026-09-20 incident). Never remove the guard.
