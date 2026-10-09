from frappe.model.document import Document


class RNHouseholdCard(Document):
    """Kartu QR keluarga. QR hanya memuat token buram; nama anggota tidak pernah ada di kartu atau endpoint tamu."""
