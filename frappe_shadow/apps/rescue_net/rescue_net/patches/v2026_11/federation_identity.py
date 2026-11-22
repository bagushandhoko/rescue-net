"""Assign identity in batches without renaming rows or generating historical events."""

import frappe

from rescue_net.federation.outbox import initialize, local_id, new_id
from rescue_net.federation.policy import POLICIES


def execute():
    initialize()
    origin = local_id()
    for doctype in POLICIES:
        table = frappe.qb.DocType(doctype)
        while True:
            names = (frappe.qb.from_(table).select(table.name)
                     .where(table.uid.isnull() | (table.uid == "")).limit(500)).run(pluck=True)
            if not names:
                break
            cases = " ".join("WHEN %s THEN %s" for _ in names)
            placeholders = ", ".join("%s" for _ in names)
            values = [value for name in names for value in (name, new_id())]
            frappe.db.sql(
                f"""UPDATE `tab{doctype}` SET uid=CASE name {cases} END,
                    origin_server_id=COALESCE(NULLIF(origin_server_id, ''), %s)
                    WHERE name IN ({placeholders}) AND (uid IS NULL OR uid='')""",
                (*values, origin, *names),
            )
        (frappe.qb.update(table).set(table.origin_server_id, origin)
         .where(table.origin_server_id.isnull() | (table.origin_server_id == ""))).run()
