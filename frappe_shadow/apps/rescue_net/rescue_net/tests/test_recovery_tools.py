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


class TestUsageAndSupport(RNTestCase):
    """Masa pakai + dukungan per alat, and the recovery -> work object link."""

    def setUp(self):
        super().setUp()
        self.event = make_event()
        self.org = make_org(title=uid("PU"))
        self.res = _insert("RN Resource Profile", disaster_event=self.event.name, owner_type="organization",
                           owner_id=self.org.name, resource_name="Ekskavator Uji", resource_type="ekskavator",
                           category="ekskavator", quantity=1)

    def test_owner_sets_usage_window_and_support(self):
        from rescue_net.api_resource_tools import update_resource_profile
        update_resource_profile(self.res.name, available_from="2026-10-20", available_until="2026-10-30",
                                support_transport=1, support_fuel="true", support_operator=0,
                                daily_operating_cost=2500000, support_notes="butuh trailer")
        with as_guest():
            data = api_call("rescue_net.api_resource_tools.tools_board", disaster_event=self.event.name)
        r = next(x for x in data["asset_registry"] if x["code"] == self.res.name)
        self.assertEqual(str(r["available_until"]), "2026-10-30")
        self.assertEqual(sorted(r["support"]), ["bbm", "transport"])
        self.assertEqual(r["daily_cost"], 2500000)
        self.assertEqual(r["support_notes"], "butuh trailer")

    def test_until_before_from_is_refused(self):
        import frappe
        from rescue_net.api_resource_tools import update_resource_profile
        with self.assertRaisesRegex(frappe.ValidationError, "sebelum tanggal mulai"):
            update_resource_profile(self.res.name, available_from="2026-10-30", available_until="2026-10-20")

    def test_work_object_links_to_recovery_project_and_counts_tools(self):
        from rescue_net.api_resource_tools import create_work_object
        proj = _insert("RN Recovery Project", disaster_event=self.event.name, project_name=uid("Jalan"))
        wo = create_work_object(title=uid("Longsor"), object_type="longsoran", size_value=300,
                                disaster_event=self.event.name, recovery_project=proj.name)["work_object"]
        _insert("RN Work Tool Request", disaster_event=self.event.name, tool_name="Ekskavator",
                tool_type="ekskavator", quantity=3, work_object=wo, request_status="requested",
                requested_by_type="other")
        with as_guest():
            data = api_call("rescue_net.api_recovery.recovery_board", disaster_event=self.event.name)
        p = next(x for x in data["projects"] if x["name"] == proj.name)
        self.assertEqual(p["alat"]["obyek"], 1)
        self.assertEqual(p["alat"]["diminta"], 3)

    def test_work_object_refuses_project_of_another_disaster(self):
        import frappe
        from rescue_net.api_resource_tools import create_work_object
        other = _insert("RN Recovery Project", disaster_event=make_event().name, project_name=uid("Lain"))
        with self.assertRaisesRegex(frappe.ValidationError, "bencana lain"):
            create_work_object(title=uid("Banjir"), object_type="longsoran", size_value=10,
                               disaster_event=self.event.name, recovery_project=other.name)
