/* rn-inarisk-layers.js — lapisan peta indeks bahaya/risiko InaRISK BNPB (data publik gis.bnpb.go.id).
 * Pemakaian: RNInaRisk.attach(map)  -> menambah kontrol "Lapisan InaRISK" (pilih satu lapisan, transparan).
 * Gambar diminta langsung oleh browser dari server BNPB (ArcGIS ImageServer exportImage), tidak lewat server RN.
 * Bila server BNPB tidak menjawab, peta RN tetap berjalan; hanya lapisan itu yang kosong. */
(function () {
  "use strict";
  var BASE = "https://gis.bnpb.go.id/server/rest/services/inarisk/";
  var LAYERS = [
    ["INDEKS_BAHAYA_BANJIR", "Bahaya banjir"],
    ["INDEKS_BAHAYA_BANJIRBANDANG", "Bahaya banjir bandang"],
    ["INDEKS_BAHAYA_TANAHLONGSOR", "Bahaya tanah longsor"],
    ["INDEKS_BAHAYA_GEMPABUMI", "Bahaya gempa bumi"],
    ["INDEKS_BAHAYA_TSUNAMI", "Bahaya tsunami"],
    ["INDEKS_BAHAYA_GUNUNGAPI", "Bahaya letusan gunung api"],
    ["INDEKS_BAHAYA_KARHUTLA", "Bahaya kebakaran hutan & lahan"],
    ["INDEKS_BAHAYA_LIKUEFAKSI", "Bahaya likuefaksi"],
    ["INDEKS_MULTI_BAHAYA", "Multi bahaya"]
  ];
  // Cuaca ekstrem, kekeringan, risiko multi: server BNPB tidak menjawab saat diuji 23 Nov -> tidak dipasang.
  // Indeks 0-1 diwarnai di server BNPB: rendah (<0,333) hijau, sedang kuning, tinggi (>0,666) merah.
  var RULE = encodeURIComponent(JSON.stringify({
    rasterFunction: "Colormap",
    rasterFunctionArguments: {
      Colormap: [[1, 56, 168, 0], [2, 255, 210, 0], [3, 220, 30, 30]],
      Raster: { rasterFunction: "Remap", outputPixelType: "U8",
        rasterFunctionArguments: { InputRanges: [0.001, 0.333, 0.333, 0.666, 0.666, 1.01], OutputValues: [1, 2, 3], NoDataRanges: [-1, 0.001] } }
    }
  }));
  var ATTR = 'Indeks bahaya/risiko: <a href="https://inarisk.bnpb.go.id" target="_blank" rel="noopener">InaRISK BNPB</a>';

  function makeLayer(service) {
    var Layer = L.Layer.extend({
      onAdd: function (map) {
        this._map = map;
        this._overlay = null;
        this._refresh = this._update.bind(this);
        map.on("moveend zoomend resize", this._refresh);
        this._update();
      },
      onRemove: function (map) {
        map.off("moveend zoomend resize", this._refresh);
        if (this._overlay) map.removeLayer(this._overlay);
        this._overlay = null;
      },
      getAttribution: function () { return ATTR; },
      _update: function () {
        var map = this._map;
        if (!map) return;
        var b = map.getBounds(), size = map.getSize();
        var sw = L.CRS.EPSG3857.project(b.getSouthWest()), ne = L.CRS.EPSG3857.project(b.getNorthEast());
        var w = Math.min(2048, Math.max(64, Math.round(size.x))), h = Math.min(2048, Math.max(64, Math.round(size.y)));
        var url = BASE + encodeURIComponent(service) + "/ImageServer/exportImage?f=image&format=png32" +
          "&bbox=" + [sw.x, sw.y, ne.x, ne.y].map(function (v) { return v.toFixed(1); }).join(",") +
          "&bboxSR=3857&imageSR=3857&size=" + w + "," + h + "&renderingRule=" + RULE;
        var next = L.imageOverlay(url, b, { opacity: 0.6, interactive: false, crossOrigin: false, zIndex: 250 });
        var prev = this._overlay;
        this._overlay = next;
        next.once("load error", function () { if (prev && map.hasLayer(prev)) map.removeLayer(prev); });
        next.addTo(map);
      }
    });
    return new Layer();
  }

  function attach(map, opts) {
    if (!map || !window.L || map._rnInaRisk) return null;
    opts = opts || {};
    var overlays = { "Tanpa lapisan InaRISK": L.layerGroup() };
    LAYERS.forEach(function (l) { overlays[l[1]] = makeLayer(l[0]); });
    overlays["Tanpa lapisan InaRISK"].addTo(map);
    // baseLayers = pilihan tunggal (radio): satu lapisan bahaya sekaligus supaya peta tetap terbaca
    var ctl = L.control.layers(null, null, { collapsed: true, position: opts.position || "topleft" });
    Object.keys(overlays).forEach(function (k) { ctl.addBaseLayer(overlays[k], k); });
    ctl.addTo(map);
    var el = ctl.getContainer();
    el.setAttribute("title", "Lapisan InaRISK BNPB");
    el.classList.add("rn-inarisk-ctl");
    var head = L.DomUtil.create("div", "rn-inarisk-head");
    head.innerHTML = "<b>Lapisan InaRISK BNPB</b><br><small><span style='color:#2e7d00'>■</span> rendah <span style='color:#b38f00'>■</span> sedang <span style='color:#c62828'>■</span> tinggi</small>";
    var list = el.querySelector(".leaflet-control-layers-list");
    if (list) list.insertBefore(head, list.firstChild);
    map._rnInaRisk = ctl;
    return ctl;
  }

  window.RNInaRisk = { attach: attach, layers: LAYERS.slice() };
})();
