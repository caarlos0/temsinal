// ── Constants ──────────────────────────────────────────────────────────────
const TECH_COLOR = {
  "5G": "#f04",
  "4G": "#0c9",
  "3G": "#fa0",
  "2G": "#88f",
};
const TECH_PRIORITY = ["5G", "4G", "3G", "2G"];
const ICON_RSS = `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M6 5c7.18 0 13 5.82 13 13M6 11a7 7 0 017 7m-6 0a1 1 0 11-2 0 1 1 0 012 0z"/></svg>`;
const ICON_CHIP = `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z"/></svg>`;
const PMTILES_URL =
  location.hostname === "localhost" || location.hostname === "127.0.0.1"
    ? "/data/towers.pmtiles"
    : "https://data.temsinal.org/towers.pmtiles";
const BASEMAP_STYLE =
  "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";

// ── URL hash ───────────────────────────────────────────────────────────────
function parseHash() {
  const m = location.hash.match(/^#(-?\d+\.?\d*),(-?\d+\.?\d*),(\d+\.?\d*)z$/);
  if (!m) return null;
  return { lat: +m[1], lon: +m[2], zoom: +m[3] };
}

const DEFAULT_VIEW = { lat: -14.2, lon: -51.9, zoom: 4 };
const { lat, lon, zoom } = parseHash() || DEFAULT_VIEW;
const hasHashView = location.hash.length > 1;

// ── PMTiles protocol ───────────────────────────────────────────────────────
const protocol = new pmtiles.Protocol();
maplibregl.addProtocol("pmtiles", protocol.tile);

// ── Map ────────────────────────────────────────────────────────────────────
const map = new maplibregl.Map({
  container: "map",
  style: BASEMAP_STYLE,
  center: [lon, lat],
  zoom: zoom,
  attributionControl: false,
});
map.addControl(
  new maplibregl.AttributionControl({ compact: true }),
  "bottom-left",
);
map.addControl(new maplibregl.NavigationControl(), "bottom-right");

function syncHash() {
  const c = map.getCenter();
  history.replaceState(
    null,
    "",
    `#${c.lat.toFixed(4)},${c.lng.toFixed(4)},${map.getZoom().toFixed(0)}z`,
  );
}
map.on("moveend", syncHash);

// ── State ──────────────────────────────────────────────────────────────────
let activeTech = localStorage.getItem("temsinal-tech") || "Todos";
if (activeTech === "nova") activeTech = "Todos";
let activeOp = localStorage.getItem("temsinal-op") || "";
let municipalitiesIndex = null;

function saveFilters() {
  localStorage.setItem("temsinal-tech", activeTech);
  localStorage.setItem("temsinal-op", activeOp);
}

// ── Build filter expression ────────────────────────────────────────────────
function buildFilter() {
  const conditions = [];

  if (activeTech !== "Todos") {
    conditions.push(["in", activeTech, ["get", "techs"]]);
  }

  if (activeOp) {
    conditions.push(["in", activeOp, ["get", "ops"]]);
  }

  if (conditions.length === 0) return null;
  if (conditions.length === 1) return conditions[0];
  return ["all", ...conditions];
}

function applyFilters() {
  if (!map.getSource("towers")) return;
  const filter = buildFilter();
  [
    "clusters",
    "cluster-count",
    "unclustered-point",
    "unclustered-label",
  ].forEach((id) => {
    if (map.getLayer(id)) map.setFilter(id, filter);
  });
}

// ── Filter buttons ─────────────────────────────────────────────────────────
const techBtns = document.querySelectorAll(".filter-btn[data-tech]");
techBtns.forEach((btn) => {
  const isActive = btn.dataset.tech === activeTech;
  btn.classList.toggle("active", isActive);
  btn.setAttribute("aria-pressed", String(isActive));
  btn.addEventListener("click", () => {
    techBtns.forEach((b) => {
      b.classList.remove("active");
      b.setAttribute("aria-pressed", "false");
    });
    btn.classList.add("active");
    btn.setAttribute("aria-pressed", "true");
    activeTech = btn.dataset.tech;
    saveFilters();
    applyFilters();
  });
});

// Operator buttons — pre-populate all three
const opGroup = document.getElementById("op-filter-group");
["Vivo", "Claro", "TIM"].forEach((op) => {
  const btn = document.createElement("button");
  const isActive = op === activeOp;
  btn.className = "filter-btn" + (isActive ? " active" : "");
  btn.dataset.op = op;
  btn.textContent = op;
  btn.setAttribute("aria-pressed", String(isActive));
  opGroup.appendChild(btn);
});
if (!activeOp) {
  const todosBtn = opGroup.querySelector('[data-op=""]');
  todosBtn?.classList.add("active");
  todosBtn?.setAttribute("aria-pressed", "true");
}
opGroup.addEventListener("click", (e) => {
  const btn = e.target.closest(".filter-btn[data-op]");
  if (!btn) return;
  opGroup.querySelectorAll(".filter-btn").forEach((b) => {
    b.classList.remove("active");
    b.setAttribute("aria-pressed", "false");
  });
  btn.classList.add("active");
  btn.setAttribute("aria-pressed", "true");
  activeOp = btn.dataset.op;
  saveFilters();
  applyFilters();
});

// ── Popup ──────────────────────────────────────────────────────────────────
function buildPopup(props) {
  const ops = (props.ops || "").split(",").filter(Boolean);
  const techs = (props.techs || "").split(",").filter(Boolean);

  const opLines = ops
    .map((op) => {
      const techBadges = techs
        .map(
          (t) =>
            `<span style="color:${TECH_COLOR[t] || "#888"};font-weight:600">${t}</span>`,
        )
        .join(" ");
      return `<div class="popup-row">${ICON_RSS}<strong>${op}</strong> <span style="margin-left:4px">${techBadges}</span></div>`;
    })
    .join("");

  const novaTag = props.nova
    ? ` &nbsp;<span style='color:#f73'>nova</span>`
    : "";

  return `
          ${opLines}
          <div class="popup-row">${ICON_CHIP}${props.municipio || "—"} – ${props.uf || ""}</div>
          ${props.data ? `<div class="popup-row">${ICON_CHIP}${props.data}${novaTag}</div>` : ""}
        `;
}

// ── Map layers ─────────────────────────────────────────────────────────────
map.on("load", () => {
  map.addSource("towers", {
    type: "vector",
    url: `pmtiles://${PMTILES_URL}`,
    promoteId: { towers: "id" },
  });

  // Clustered circle layer
  map.addLayer({
    id: "unclustered-point",
    type: "circle",
    source: "towers",
    "source-layer": "towers",
    paint: {
      "circle-color": [
        "match",
        ["get", "tech"],
        "5G",
        TECH_COLOR["5G"],
        "4G",
        TECH_COLOR["4G"],
        "3G",
        TECH_COLOR["3G"],
        "2G",
        TECH_COLOR["2G"],
        "#888",
      ],
      "circle-radius": [
        "interpolate",
        ["linear"],
        ["zoom"],
        4,
        1.5,
        8,
        3,
        12,
        5,
        16,
        8,
      ],
      "circle-opacity": 0.85,
      "circle-stroke-width": [
        "interpolate",
        ["linear"],
        ["zoom"],
        4,
        0,
        10,
        0.5,
        14,
        1,
      ],
      "circle-stroke-color": "rgba(0,0,0,0.3)",
    },
  });

  // Label at high zoom
  map.addLayer({
    id: "unclustered-label",
    type: "symbol",
    source: "towers",
    "source-layer": "towers",
    minzoom: 13,
    layout: {
      "text-field": ["get", "tech"],
      "text-size": 10,
      "text-font": ["Open Sans Bold", "Arial Unicode MS Bold"],
      "text-offset": [0, -1.2],
      "text-allow-overlap": false,
    },
    paint: {
      "text-color": "#fff",
      "text-halo-color": "rgba(0,0,0,0.7)",
      "text-halo-width": 1,
    },
  });

  // Click → popup
  map.on("click", "unclustered-point", (e) => {
    if (!e.features || !e.features.length) return;
    const f = e.features[0];
    const coords = f.geometry.coordinates.slice();
    new maplibregl.Popup({ offset: 10, maxWidth: "280px" })
      .setLngLat(coords)
      .setHTML(buildPopup(f.properties))
      .addTo(map);
  });

  map.on("mouseenter", "unclustered-point", () => {
    map.getCanvas().style.cursor = "pointer";
  });
  map.on("mouseleave", "unclustered-point", () => {
    map.getCanvas().style.cursor = "";
  });

  applyFilters();
});

// ── Search ─────────────────────────────────────────────────────────────────
function initSearch() {
  const input = document.getElementById("search-input");
  const results = document.getElementById("search-results");
  if (!input || !results || !municipalitiesIndex) return;

  const stripAccents = (s) =>
    s.normalize("NFD").replace(/[\u0300-\u036f]/g, "");

  const entries = Object.values(municipalitiesIndex)
    .filter((m) => m.lat)
    .map((m) => ({
      label: `${m.nome} – ${m.uf}`,
      search: stripAccents(`${m.nome} ${m.uf}`.toLowerCase()),
      lat: m.lat,
      lon: m.lon,
      antenas: m.antenas || 0,
    }));

  let debounceTimer;
  let activeIdx = -1;

  function setActive(idx) {
    const items = results.querySelectorAll(".search-item[data-lat]");
    items.forEach((el) => el.classList.remove("active"));
    activeIdx = idx;
    if (idx >= 0 && idx < items.length) {
      items[idx].classList.add("active");
      items[idx].scrollIntoView({ block: "nearest" });
    }
  }

  function selectItem(item) {
    if (!item || !item.dataset.lat) return;
    map.flyTo({
      center: [parseFloat(item.dataset.lon), parseFloat(item.dataset.lat)],
      zoom: 13,
    });
    input.value = "";
    results.style.display = "none";
    activeIdx = -1;
  }

  input.addEventListener("input", () => {
    clearTimeout(debounceTimer);
    activeIdx = -1;
    debounceTimer = setTimeout(() => {
      const q = stripAccents(input.value.trim().toLowerCase());
      if (q.length < 2) {
        results.style.display = "none";
        return;
      }

      const matches = entries
        .filter((e) => e.search.includes(q))
        .sort((a, b) => b.antenas - a.antenas)
        .slice(0, 8);

      if (matches.length === 0) {
        results.innerHTML =
          '<div class="search-item"><span style="color:#555">Nenhum resultado</span></div>';
        results.style.display = "block";
        return;
      }

      results.innerHTML = matches
        .map(
          (m) => `
              <div class="search-item" data-lat="${m.lat}" data-lon="${m.lon}">
                <span class="search-name">${m.label}</span>
              </div>`,
        )
        .join("");
      results.style.display = "block";
    }, 150);
  });

  results.addEventListener("click", (e) => {
    selectItem(e.target.closest(".search-item"));
  });

  document.addEventListener("click", (e) => {
    if (!e.target.closest("#search-container")) {
      results.style.display = "none";
    }
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "/" && document.activeElement !== input) {
      e.preventDefault();
      input.focus();
      return;
    }
  });

  input.addEventListener("keydown", (e) => {
    const items = results.querySelectorAll(".search-item[data-lat]");
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive(Math.min(activeIdx + 1, items.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive(Math.max(activeIdx - 1, 0));
    } else if (e.key === "Enter" && activeIdx >= 0) {
      e.preventDefault();
      selectItem(items[activeIdx]);
    } else if (e.key === "Escape") {
      input.value = "";
      results.style.display = "none";
      activeIdx = -1;
      input.blur();
    }
  });
}

// ── Geolocation ────────────────────────────────────────────────────────────
function isInBrazil(lat, lon) {
  return lat >= -34 && lat <= 6 && lon >= -74 && lon <= -34;
}

function tryGeolocation() {
  if (!window.isSecureContext || !navigator.geolocation) return;
  navigator.geolocation.getCurrentPosition(
    (pos) => {
      const { latitude, longitude } = pos.coords;
      if (isInBrazil(latitude, longitude)) {
        map.flyTo({ center: [longitude, latitude], zoom: 12 });
      }
    },
    () => {},
    { enableHighAccuracy: false, timeout: 10000, maximumAge: 300000 },
  );
}

// ── Init ───────────────────────────────────────────────────────────────────
async function init() {
  try {
    municipalitiesIndex = await fetch("data/municipalities.json").then((r) =>
      r.json(),
    );
    initSearch();
    if (!hasHashView) tryGeolocation();
  } catch (err) {
    console.error("erro ao inicializar", err);
  }
}

init();
