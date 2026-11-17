"""Public, allowlisted incoming activity for one receiving posko."""
from urllib.parse import urlencode

import frappe
from frappe.utils import flt, nowdate
from rescue_net.access_policy import public_posko_allowed
from rescue_net.services import drill

LABELS = {
    'planned': 'Direncanakan', 'loaded': 'Sudah dimuat',
    'pickup_claimed': 'Penjemputan diambil', 'assigned_pickup': 'Penjemputan ditugaskan', 'dispatched': 'Diberangkatkan',
    'in_transit': 'Dalam perjalanan', 'arrived_at_posko': 'Tiba di posko',
    'partially_received': 'Diterima sebagian', 'reserved': 'Sudah dibooking',
    'available': 'Ditawarkan ke posko', 'need_pickup': 'Menunggu penjemputan',
    'requested': 'Menunggu persetujuan', 'confirmed': 'Disetujui',
    'assigned': 'Ditugaskan', 'arrived': 'Tiba',
}


def incoming(posko, event=None):
    from rescue_net.reference_resolver import resolve_posko
    from rescue_net.control_centre.common import canonical_event
    posko = resolve_posko(posko)
    if not posko or not public_posko_allowed(posko):
        frappe.throw('Detail posko tidak dibuka untuk publik.', frappe.PermissionError)
    out = {'posko': posko, 'in_transit': [], 'booked': [], 'arrivals': []}
    p = frappe.db.get_value('RN Posko', posko, ['name', 'title', 'disaster_event'], as_dict=True)
    if not drill.drop_hidden_rows([p], posko_keys=('name',)):
        return out
    ef = {'disaster_event': canonical_event(event)} if event else {}

    def rows(dt, filters, fields, or_filters=None):
        return drill.drop_hidden_rows(frappe.get_all(
            dt, filters={**filters, **ef}, fields=fields, or_filters=or_filters,
            order_by='modified desc', limit_page_length=500),
            posko_keys=drill.HIDE_POSKO_KEYS + ('target_posko',))

    # No free-text contact, note, code, PIN, or payload field is returned.
    def safe(value):
        from rescue_net.api_public_needs import _CONTACT_LIKE
        return _CONTACT_LIKE.sub('[kontak disembunyikan]', str(value or ''))[:180]

    def title(dt, name, field='title'):
        if not name:
            return ''
        if dt == 'RN Posko' and not public_posko_allowed(name):
            return 'Posko pengirim'
        return safe(frappe.db.get_value(dt, name, field) or '')

    def link(page, **kw):
        return page + '?' + urlencode({k: v for k, v in kw.items() if v})

    def row(kind, r, status, item, href, **kw):
        return dict(kind=kind, id=r.name, item=safe(item), status=safe(status),
                    status_label=LABELS.get(status, 'Dalam proses'), href=href, **kw)

    flows = rows('RN Distribution Flow',
                 {'destination_posko': posko, 'flow_status': ['not in', ['received', 'cancelled']]},
                 ['name', 'title', 'disaster_event', 'source_posko', 'destination_posko',
                  'item_name', 'quantity', 'unit', 'flow_status', 'eta_final', 'transport_space', 'aid_offer'])
    # All linked flows, including completed ones, prevent stale offers/bookings resurfacing.
    linked = rows('RN Distribution Flow', {'destination_posko': posko},
                  ['name', 'title', 'disaster_event', 'source_posko', 'destination_posko', 'aid_offer', 'flow_status'])
    flow_map = {f.name: f for f in linked}
    aid_ids = {f.aid_offer for f in linked if f.aid_offer}
    for f in flows:
        out['in_transit'].append(row('flow', f, f.flow_status, f.item_name,
            link('lacak-logistik.html', flow=f.name), quantity=flt(f.quantity), unit=safe(f.unit),
            sender=title('RN Posko', f.source_posko), eta=safe(f.eta_final),
            armada=title('RN Transport Space', f.transport_space, 'provider_name')))

    from rescue_net.rn_logistics.doctype.rn_aid_offer.rn_aid_offer import FINAL_OFFER_STATES
    offers = rows('RN Aid Offer', {'target_posko': posko,
                  'offer_status': ['not in', sorted(FINAL_OFFER_STATES)]},
                  ['name', 'title', 'disaster_event', 'target_posko', 'item_name', 'quantity', 'unit', 'offer_status', 'ready_at'])
    for a in offers:
        if a.name not in aid_ids:
            out['booked'].append(row('aid', a, a.offer_status, a.item_name,
                link('kebutuhan-publik.html', event=a.disaster_event),
                quantity=flt(a.quantity), unit=safe(a.unit), eta=str(a.ready_at or '')))

    # Legacy destination fields are free text. Accept exact ID, or a unique exact title only.
    targets = [posko]
    if p.title and frappe.db.count('RN Posko', {'title': p.title}) == 1:
        targets.append(p.title)
    bookings = rows('RN Transport Booking', {'status': ['in', ['requested', 'confirmed']]},
                    ['name', 'disaster_event', 'transport_space', 'distribution_flow', 'aid_offer',
                     'dropoff_location', 'status', 'qty_weight_kg', 'qty_volume_m3', 'requested_window'],
                    or_filters=[['distribution_flow', 'in', list(flow_map) or ['']],
                                ['aid_offer', 'in', [a.name for a in offers] or ['']],
                                ['dropoff_location', 'in', targets]])
    space_ids = {f.transport_space for f in flows if f.transport_space}
    space_ids.update(b.transport_space for b in bookings if b.transport_space)
    spaces = rows('RN Transport Space', {'transport_status': ['not in', ['completed', 'cancelled']]},
                  ['name', 'title', 'disaster_event', 'coordination_posko', 'provider_name',
                   'route_destination', 'eta_at', 'transport_status'],
                  or_filters=[['route_destination', 'in', targets], ['name', 'in', list(space_ids) or ['']]])
    space_map = {s.name: s for s in spaces if public_posko_allowed(s.coordination_posko)}
    heading = {s.name for s in space_map.values() if s.route_destination in targets}
    for sid in sorted(heading):
        s = space_map[sid]
        out['arrivals'].append(row('transport', s, s.transport_status, s.provider_name,
            link('posko-distribusi.html', id=s.coordination_posko, event=s.disaster_event, armada=s.name),
            eta=str(s.eta_at or '')))
    offer_map = {a.name: a for a in offers}
    for b in bookings:
        f = flow_map.get(b.distribution_flow)
        # A flow destination overrides free-text/armada routes (including first-mile legs).
        goes_here = (bool(f) if b.distribution_flow else
                     bool(b.aid_offer in offer_map or b.dropoff_location in targets))
        if not goes_here or (f and f.flow_status in ('received', 'cancelled')):
            continue
        s = space_map.get(b.transport_space)
        if not s:
            continue
        href = (link('lacak-logistik.html', flow=f.name) if f else
                link('posko-distribusi.html', id=s.coordination_posko, event=s.disaster_event, armada=s.name))
        out['booked'].append(row('cargo_booking', b, b.status, 'Booking ruang muat', href,
            quantity=flt(b.qty_weight_kg) or flt(b.qty_volume_m3),
            unit='kg' if flt(b.qty_weight_kg) else 'm³', armada=safe(s.provider_name), eta=safe(b.requested_window)))
    volunteers = rows('RN Volunteer Booking', {'status': ['in', ['requested', 'confirmed']]},
                     ['name', 'disaster_event', 'posko', 'transport_space', 'volunteer',
                      'booking_kind', 'status', 'date_from', 'date_to', 'trip_leg'],
                     or_filters=[['posko', '=', posko], ['transport_space', 'in', list(heading) or ['']]])
    for b in volunteers:
        if b.date_to and str(b.date_to) < nowdate():
            continue
        if b.booking_kind == 'transport':
            matches = b.transport_space in heading and b.trip_leg != 'pulang'
        else:
            matches = b.posko == posko
        if not matches:
            continue
        out['arrivals'].append(row('volunteer', b, b.status,
            title('RN Volunteer Profile', b.volunteer, 'volunteer_name') or 'Relawan',
            link('management-relawan.html', event=b.disaster_event), eta=str(b.date_from or '')))
    return out
