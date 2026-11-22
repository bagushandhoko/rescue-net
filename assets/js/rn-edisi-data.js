(() => {
  "use strict";

  const { load, getJSON, api } = window.RNDmsMenus;
  const federation = "Data akan masuk dari node instansi (federasi)";
  const pendingSave = "Formulir siap; penyimpanan aktif setelah node instansi tersambung";

  async function read(method, args = {}) {
    const query = new URLSearchParams(args);
    const { message } = await getJSON(api + "rescue_net." + method + "?" + query);
    if (!message || typeof message !== "object") throw new Error("Respons RN tidak valid");
    return message;
  }

  // Scope operational feeds to a public, active real event, never an unscoped inventory.
  async function activeEvents() {
    const data = await read("api_control_centre.active_disasters_board", { rn_tampilan: "riil" });
    return data.events;
  }

  async function withEvent(readEvent) {
    const events = await activeEvents();
    const id = new URLSearchParams(location.search).get("event");
    const event = id ? events.find((row) => row.id === id || row.event_id === id) : events[0];
    return event ? readEvent(event) : [];
  }

  function poskos(types, service) {
    return () => withEvent(async (event) => {
      const { points } = await read("api_control_centre.event_poskos", { disaster_event: event.event_id });
      return points.filter((point) => types.includes(point.posko_type) || point.functions?.includes(service))
        .map((point) => ({ nama: point.name, wilayah: event.location, status: point.status }));
    });
  }

  const sources = {
    "posko-komando": poskos(["command", "command_center", "coordination"]),
    "posko-logistik": poskos(["logistics", "collection_hub"], "logistics"),
    "posko-medis": poskos(["medical"]),
    "posko-shelter": poskos(["shelter"], "shelter"),
    "posko-distribusi": poskos(["transport", "distribution"]),
    relawan: poskos(["volunteer"]),
    async bencana() {
      const { disasters } = await read("api_events.disasters", { include_drill: 0 });
      return disasters.map((row) => ({ nama: row.title, wilayah: row.location_summary, status: row.event_status }));
    },
    async korban() {
      return (await activeEvents()).map((event) => ({ nama: event.name, wilayah: event.location, jumlah: event.jiwa_berisiko }));
    },
    laporan: () => withEvent(async (event) => {
      const reports = await read("api_frontend_bridge.community_reports", { disaster_event: event.event_id });
      return reports.map((row) => ({ judul: row.title, wilayah: row.location_text, status: row.status }));
    }),
    kebutuhan: () => withEvent(async (event) => {
      const { needs } = await read("api_public_needs.board", { event: event.event_id });
      return needs.map((row) => ({ nama: row.item, jumlah: row.gap, satuan: row.unit }));
    }),
    sitrep: () => withEvent(async (event) => {
      const row = await read("api_sitrep.sitrep", { disaster_event: event.event_id });
      return [{ nama: row.bencana.title, mulai: row.periode.dari, selesai: row.periode.sampai }];
    }),
    async bmkg() {
      const data = await read("api_early_warning.banner");
      if (data.source_ok === false && !data.warnings.length) throw new Error("BMKG belum terjangkau");
      return data.warnings.map((row) => ({ nama: row.title, wilayah: row.area_desc, waktu: row.issued_at }));
    },
    async recovery() {
      const rows = await read("api_recovery.list_projects");
      return rows.map((row) => ({ nama: row.project_name, wilayah: row.location, status: row.status }));
    },
    alat: () => withEvent(async (event) => {
      const { asset_registry: rows } = await read("api_resource_tools.tools_board", { disaster_event: event.event_id });
      return rows.map((row) => ({ nama: row.resource_name, wilayah: row.location, status: row.status }));
    }),
    akses: () => withEvent(async (event) => {
      const { items } = await read("api_access_status.board", { disaster_event: event.event_id });
      return items.map((row) => ({ nama: row.place_name, wilayah: event.location, status: row.status }));
    }),
    pencarian: () => withEvent(async (event) => {
      const { kpis } = await read("api_search_found.dashboard", { disaster_event: event.event_id });
      return [{ nama: event.name, hilang: kpis.orang_hilang.n, ditemukan: kpis.korban_ditemukan.n }];
    }),
    donor: () => withEvent(async (event) => {
      const { programs } = await read("api_donor_program.program_board", { disaster_event: event.event_id });
      return programs.map((row) => ({ nama: row.program_name, wilayah: row.location, status: row.status }));
    })
  };

  const adapters = {
    RN: {
      async list(menuId) {
        const menu = (await load()).find((entry) => entry.id === menuId);
        const source = menu?.sumber_rn;
        if (!Object.hasOwn(sources, source)) return { rows: [], notice: federation };
        try {
          const rows = await sources[source]();
          const label = source === "bmkg" ? "Sumber: BMKG melalui Rescue-Net." : "Sumber: Rescue-Net.";
          return { rows, notice: rows.length ? label : label + " Belum ada data yang dapat ditampilkan." };
        } catch (_) {
          return { rows: [], notice: "Data RN belum dapat dimuat. Periksa koneksi dan izin akun." };
        }
      },
      async save(_menuId, _record) {
        return { saved: false, notice: pendingSave };
      }
    }
  };
  window.RNEdisiData = adapters.RN;
})();
