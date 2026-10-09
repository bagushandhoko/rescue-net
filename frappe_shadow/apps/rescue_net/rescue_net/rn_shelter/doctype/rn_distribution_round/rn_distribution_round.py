from frappe.model.document import Document


class RNDistributionRound(Document):
    """Putaran distribusi: ditetapkan koordinator (pengelola posko/organisasi). Satu keluarga menerima paling banyak
    satu kali per putaran (RN Aid Receipt, kunci unik)."""
