"""Recovery dan Alat Kerja (owner 2026-10-19): guest boards show the plan,
its progress and who provides each tool — never a PIC's name or phone, a
private owner's account, or a drill (latihan) project."""

from rescue_net.tests.factories import (
    RNTestCase,
    _insert,
    api_call,
    as_guest,
    contains_value,
    make_actor,
    make_event,
    make_org,
    uid,
)

PIC = "Pak Joko PIC Rahasia"
PIC_PHONE = "+62811-0000-6262"


class TestRecoveryBoard(RNTestCase):
    def setUp(self):
        super().setUp()
        self.event = make_event()
        self.org = make_org(title=uid("Dinas PU"), organization_type="government")
        self.proj = _insert("RN Recovery Project", disaster_event=self.event.name,
                            project_name=uid("Jembatan Darurat"), owner_type="organization",
                            owner_id=self.org.name, progress_percent=40, status="in_progress",
                            pic_name=PIC, pic_phone=PIC_PHONE, notes="catatan internal " + PIC)
        _insert("RN Recovery Project Update", project=self.proj.name, disaster_event=self.event.name,
                update_title="Pondasi selesai", progress_percent=40)
        drill = make_event(is_drill=1)
        self.drill_proj = _insert("RN Recovery Project", disaster_event=drill.name,
                                  project_name=uid("Proyek Latihan"))

    def board(self, **kw):
        with as_guest():
            return api_call("rescue_net.api_recovery.recovery_board", **kw)

    def test_guest_sees_plan_progress_and_owner(self):
        data = self.board(disaster_event=self.event.name)
        p = data["projects"][0]
        self.assertEqual(p["progress"], 40)
        self.assertEqual(p["owner"], self.org.title)
        self.assertEqual(p["last_update"]["title"], "Pondasi selesai")
        self.assertEqual(data["totals"]["projects"], 1)

    def test_guest_never_sees_pic_or_notes(self):
        data = self.board(disaster_event=self.event.name)
        for secret in (PIC, PIC_PHONE, "catatan internal"):
            self.assertFalse(contains_value(data, secret), secret)

    def test_drill_project_hidden_from_guest_listing(self):
        names = [p["name"] for p in self.board()["projects"]]
        self.assertIn(self.proj.name, names)
        self.assertNotIn(self.drill_proj.name, names)


class TestToolProviders(RNTestCase):
    def test_registry_names_org_provider_but_not_private_person(self):
        event = make_event()
        org = make_org(title=uid("BPBD Alat"))
        person = make_actor()
        _insert("RN Resource Profile", disaster_event=event.name, owner_type="organization",
                owner_id=org.name, resource_name="Ekskavator PC200", resource_type="ekskavator",
                category="ekskavator", quantity=1, coverage_area="Kec. Woyla")
        _insert("RN Resource Profile", disaster_event=event.name, owner_type="individual",
                owner_id=person.account, resource_name="Genset 5 kVA", resource_type="genset",
                category="genset", quantity=1)
        with as_guest():
            data = api_call("rescue_net.api_resource_tools.tools_board", disaster_event=event.name)
        reg = {r["resource_name"]: r for r in data["asset_registry"]}
        self.assertEqual(reg["Ekskavator PC200"]["provider"], org.title)
        self.assertEqual(reg["Ekskavator PC200"]["coverage"], "Kec. Woyla")
        self.assertEqual(reg["Genset 5 kVA"]["provider"], "Perorangan")
        self.assertFalse(contains_value(data, person.account))
