// ── Icons ────────────────────────────────────────────────────────────────────
const ICON_TROPHY = `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M16 4h2a2 2 0 012 2v1c0 2.97-2.143 5.449-5 5.91V15h2a1 1 0 010 2H7a1 1 0 010-2h2v-2.09C6.143 12.449 4 9.97 4 7V6a2 2 0 012-2h2m8 0V3a1 1 0 00-1-1H9a1 1 0 00-1 1v1m8 0H8"/></svg>`;
const ICON_TREND_DOWN = `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M13 17h8m0 0V9m0 8l-8-8-4 4-6-6"/></svg>`;
const ICON_SIGNAL = `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/></svg>`;
const ICON_SPARK = `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z"/></svg>`;

// ── Constants ────────────────────────────────────────────────────────────────
const POP_THRESHOLD = 5000;
const TECH_COLOR = {
  "5G": "#ff0044",
  "4G": "#00cc99",
  "3G": "#ffaa00",
  "2G": "#8888ff",
};
const OP_COLOR = { Claro: "#e05c2a", TIM: "#0050a0", Vivo: "#660099" };
const ALL_TECHS = ["5G", "4G", "3G", "2G"];
const ALL_UFS = [
  "AC",
  "AL",
  "AM",
  "AP",
  "BA",
  "CE",
  "DF",
  "ES",
  "GO",
  "MA",
  "MG",
  "MS",
  "MT",
  "PA",
  "PB",
  "PE",
  "PI",
  "PR",
  "RJ",
  "RN",
  "RO",
  "RR",
  "RS",
  "SC",
  "SE",
  "SP",
  "TO",
];
const UF_NAMES = {
  AC: "Acre",
  AL: "Alagoas",
  AM: "Amazonas",
  AP: "Amapá",
  BA: "Bahia",
  CE: "Ceará",
  DF: "Distrito Federal",
  ES: "Espírito Santo",
  GO: "Goiás",
  MA: "Maranhão",
  MG: "Minas Gerais",
  MS: "Mato Grosso do Sul",
  MT: "Mato Grosso",
  PA: "Pará",
  PB: "Paraíba",
  PE: "Pernambuco",
  PI: "Piauí",
  PR: "Paraná",
  RJ: "Rio de Janeiro",
  RN: "Rio Grande do Norte",
  RO: "Rondônia",
  RR: "Roraima",
  RS: "Rio Grande do Sul",
  SC: "Santa Catarina",
  SE: "Sergipe",
  SP: "São Paulo",
  TO: "Tocantins",
};

// ── Utilities ───────────────────────────────────────────────────────────────
const fmt = (n) => n.toLocaleString("pt-BR");
const fmtF = (n, d = 1) =>
  n.toLocaleString("pt-BR", {
    minimumFractionDigits: d,
    maximumFractionDigits: d,
  });
const stripAccents = (s) => s.normalize("NFD").replace(/[\u0300-\u036f]/g, "");

const CHART_SCALES = {
  x: {
    grid: { color: "rgba(255,255,255,.05)" },
    ticks: { color: "#8b949e" },
  },
  y: {
    grid: { display: false },
    ticks: { color: "#e6edf3", font: { size: 11 } },
  },
};

function stackBar(counts, palette, total) {
  if (!total) return '<span style="color:var(--muted)">—</span>';
  return (
    '<div class="stack">' +
    Object.entries(counts)
      .sort((a, b) => b[1] - a[1])
      .map(([k, v]) => {
        const w = Math.max(1, Math.round((v / total) * 100));
        const c = palette[k] || "#555";
        return `<span style="width:${w}%;background:${c}" title="${k}: ${v}"></span>`;
      })
      .join("") +
    "</div>"
  );
}

// ── State ───────────────────────────────────────────────────────────────────
const selection = { states: new Set(), cities: [] };
const MAX_CITIES = 10;
let viewMode = "national"; // national | single-state | comparison
let activeTech = localStorage.getItem("temsinal-tech") || "Todos";
if (activeTech === "nova") activeTech = "Todos";
let activeOp = localStorage.getItem("temsinal-op") || "";
let allRows = [];
let chartPerCapita, chartTech;
let sortCol = "per10k",
  sortDir = -1;
let municipalitiesIndex = null;
const stateDataCache = {};
let searchIndex = [];
let renderChips = () => { };

function getMode() {
  if (selection.cities.length > 0) return "comparison";
  if (selection.states.size > 1) return "comparison";
  if (selection.states.size === 1) return "single-state";
  return "national";
}

function saveFilters() {
  localStorage.setItem("temsinal-tech", activeTech);
  localStorage.setItem("temsinal-op", activeOp);
}

function syncUrl() {
  const url = new URL(location);
  url.searchParams.delete("uf");
  url.searchParams.delete("states");
  url.searchParams.delete("cities");
  if (selection.cities.length > 0) {
    url.searchParams.set(
      "cities",
      selection.cities.map((c) => `${c.name}|${c.uf}`).join(","),
    );
  } else if (selection.states.size > 0) {
    if (selection.states.size === 1) {
      url.searchParams.set("uf", [...selection.states][0]);
    } else {
      url.searchParams.set("states", [...selection.states].join(","));
    }
  }
  history.replaceState(null, "", url);
}

function loadFromUrl() {
  const p = new URLSearchParams(location.search);
  if (p.has("cities")) {
    p.get("cities")
      .split(",")
      .forEach((s) => {
        const [name, uf] = s.split("|");
        if (name && uf && selection.cities.length < MAX_CITIES)
          selection.cities.push({ name, uf });
      });
  } else if (p.has("states")) {
    p.get("states")
      .split(",")
      .forEach((uf) => {
        if (uf && ALL_UFS.includes(uf)) selection.states.add(uf);
      });
  } else if (p.has("uf")) {
    const uf = p.get("uf");
    if (uf && ALL_UFS.includes(uf)) selection.states.add(uf);
  }
}

// ── Scope selector ──────────────────────────────────────────────────────────
function buildSearchIndex() {
  searchIndex = [];
  ALL_UFS.forEach((uf) => {
    searchIndex.push({
      type: "state",
      label: `${uf} – ${UF_NAMES[uf]}`,
      uf,
      search: stripAccents(`${uf} ${UF_NAMES[uf]}`).toLowerCase(),
    });
  });
  if (municipalitiesIndex) {
    for (const m of Object.values(municipalitiesIndex)) {
      if (!m.lat) continue;
      searchIndex.push({
        type: "city",
        label: `${m.nome} – ${m.uf}`,
        name: m.nome,
        uf: m.uf,
        pop: m.populacao || 0,
        search: stripAccents(`${m.nome} ${m.uf}`).toLowerCase(),
      });
    }
  }
}

function initScopeSelector() {
  const wrap = document.getElementById("scope-wrap");
  const input = document.getElementById("scope-input");
  const results = document.getElementById("scope-results");
  let activeIdx = -1;

  renderChips = function() {
    wrap.querySelectorAll(".scope-chip").forEach((c) => c.remove());
    for (const uf of selection.states) {
      const chip = document.createElement("span");
      chip.className = "scope-chip state";
      chip.innerHTML = `${uf} <button data-type="state" data-uf="${uf}" aria-label="Remover ${uf}">\u00d7</button>`;
      wrap.insertBefore(chip, input);
    }
    selection.cities.forEach((c, i) => {
      const chip = document.createElement("span");
      chip.className = "scope-chip city";
      chip.innerHTML = `${c.name} <span style="color:var(--muted)">(${c.uf})</span> <button data-type="city" data-idx="${i}" aria-label="Remover ${c.name}">\u00d7</button>`;
      wrap.insertBefore(chip, input);
    });
  };

  function addItem(type, data) {
    if (type === "state") {
      selection.cities.length = 0;
      selection.states.add(data.uf);
    } else {
      if (selection.cities.length >= MAX_CITIES) return;
      selection.states.clear();
      selection.cities.push({ name: data.name, uf: data.uf });
    }
    input.value = "";
    results.style.display = "none";
    activeIdx = -1;
    renderChips();
    syncUrl();
    loadScope();
  }

  function removeItem(type, data) {
    if (type === "state") {
      selection.states.delete(data.uf);
    } else {
      selection.cities.splice(data.idx, 1);
    }
    renderChips();
    syncUrl();
    loadScope();
  }

  wrap.addEventListener("click", (e) => {
    const btn = e.target.closest("button");
    if (!btn) {
      input.focus();
      return;
    }
    const type = btn.dataset.type;
    if (type === "state") removeItem("state", { uf: btn.dataset.uf });
    else if (type === "city")
      removeItem("city", { idx: parseInt(btn.dataset.idx) });
  });

  let debounceTimer;
  input.addEventListener("input", () => {
    clearTimeout(debounceTimer);
    activeIdx = -1;
    debounceTimer = setTimeout(() => {
      const q = stripAccents(input.value.trim()).toLowerCase();
      if (q.length < 1) {
        results.style.display = "none";
        return;
      }
      const stateMatches = searchIndex
        .filter(
          (e) =>
            e.type === "state" &&
            !selection.states.has(e.uf) &&
            e.search.includes(q),
        )
        .slice(0, 5);
      const cityMatches = searchIndex
        .filter(
          (e) =>
            e.type === "city" &&
            !selection.cities.some((c) => c.name === e.name && c.uf === e.uf) &&
            e.search.includes(q),
        )
        .sort((a, b) => b.pop - a.pop)
        .slice(0, 8);

      if (!stateMatches.length && !cityMatches.length) {
        results.innerHTML =
          '<div style="padding:8px 10px;color:var(--muted);font-size:0.8rem">Nenhum resultado</div>';
        results.style.display = "block";
        return;
      }

      let html = "";
      if (stateMatches.length) {
        html += '<div class="scope-group-label">Estados</div>';
        html += stateMatches
          .map(
            (e) =>
              `<div class="scope-item" data-type="state" data-uf="${e.uf}">${e.label}</div>`,
          )
          .join("");
      }
      if (cityMatches.length) {
        html += '<div class="scope-group-label">Cidades</div>';
        html += cityMatches
          .map(
            (e) =>
              `<div class="scope-item" data-type="city" data-name="${e.name}" data-uf="${e.uf}">${e.label}</div>`,
          )
          .join("");
      }
      results.innerHTML = html;
      results.style.display = "block";
    }, 150);
  });

  results.addEventListener("click", (e) => {
    const item = e.target.closest(".scope-item");
    if (!item) return;
    if (item.dataset.type === "state")
      addItem("state", { uf: item.dataset.uf });
    else
      addItem("city", {
        name: item.dataset.name,
        uf: item.dataset.uf,
      });
  });

  function setActive(idx) {
    const items = results.querySelectorAll(".scope-item");
    items.forEach((el) => el.classList.remove("active"));
    activeIdx = idx;
    if (idx >= 0 && idx < items.length) {
      items[idx].classList.add("active");
      items[idx].scrollIntoView({ block: "nearest" });
    }
  }

  input.addEventListener("keydown", (e) => {
    const items = results.querySelectorAll(".scope-item");
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive(Math.min(activeIdx + 1, items.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive(Math.max(activeIdx - 1, 0));
    } else if (e.key === "Enter" && activeIdx >= 0 && items[activeIdx]) {
      e.preventDefault();
      items[activeIdx].click();
    } else if (e.key === "Escape") {
      input.value = "";
      results.style.display = "none";
      activeIdx = -1;
      input.blur();
    } else if (e.key === "Backspace" && input.value === "") {
      if (selection.cities.length > 0) {
        removeItem("city", { idx: selection.cities.length - 1 });
      } else if (selection.states.size > 0) {
        const lastUf = [...selection.states].pop();
        removeItem("state", { uf: lastUf });
      }
    }
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "/" && document.activeElement !== input) {
      e.preventDefault();
      input.focus();
    }
  });

  document.addEventListener("click", (e) => {
    if (!e.target.closest("#scope-selector")) results.style.display = "none";
  });

  renderChips();
}

// ── Data loading ────────────────────────────────────────────────────────────
async function loadMunicipalities() {
  if (municipalitiesIndex) return;
  municipalitiesIndex = await fetch("../data/municipalities.json").then((r) =>
    r.json(),
  );
}

async function loadStateAntennas(uf) {
  if (stateDataCache[uf]) return stateDataCache[uf];
  const data = await fetch(`../data/antennas/${uf}.json`).then((r) => r.json());
  stateDataCache[uf] = data;
  return data;
}

// ── Row builders ────────────────────────────────────────────────────────────
function buildAntennaAggregates(antennas) {
  const siteMap = new Map();
  for (const a of antennas) {
    const key = `${a.lat.toFixed(3)},${a.lon.toFixed(3)}`;
    if (!siteMap.has(key))
      siteMap.set(key, {
        techs: new Set(),
        ops: new Set(),
        isNew: false,
      });
    const s = siteMap.get(key);
    s.techs.add(a.tecnologia);
    s.ops.add(a.operadora);
    if (a.nova) s.isNew = true;
  }
  const techs = {};
  const ops = {};
  for (const a of antennas) {
    techs[a.tecnologia] = (techs[a.tecnologia] || 0) + 1;
    ops[a.operadora] = (ops[a.operadora] || 0) + 1;
  }
  return { techs, ops, sites: [...siteMap.values()] };
}

function buildSingleStateRows(uf, antData) {
  const filtered = antData.filter((a) => ALL_TECHS.includes(a.tecnologia));
  const byCity = {};
  for (const a of filtered) {
    if (!byCity[a.municipio]) byCity[a.municipio] = [];
    byCity[a.municipio].push(a);
  }
  const muns = Object.entries(municipalitiesIndex).filter(
    ([, m]) => m.uf === uf,
  );
  allRows = muns.map(([, info]) => {
    const cityAntennas = byCity[info.nome] || [];
    const { techs, ops, sites } = buildAntennaAggregates(cityAntennas);
    return {
      city: info.nome,
      pop: info.populacao || 0,
      techs,
      ops,
      _sites: sites,
    };
  });
}

async function buildMultiStateRows(states) {
  await Promise.all(states.map((uf) => loadStateAntennas(uf)));
  allRows = states.map((uf) => {
    const antennas = stateDataCache[uf].filter((a) =>
      ALL_TECHS.includes(a.tecnologia),
    );
    const muns = Object.values(municipalitiesIndex).filter((m) => m.uf === uf);
    const pop = muns.reduce((s, m) => s + (m.populacao || 0), 0);
    const { techs, ops, sites } = buildAntennaAggregates(antennas);
    return {
      city: `${UF_NAMES[uf]} (${uf})`,
      uf,
      pop,
      techs,
      ops,
      _sites: sites,
    };
  });
}

async function buildCityRows(cities) {
  const uniqueStates = [...new Set(cities.map((c) => c.uf))];
  await Promise.all(uniqueStates.map((uf) => loadStateAntennas(uf)));
  allRows = cities.map(({ name, uf }) => {
    const antennas = stateDataCache[uf].filter(
      (a) => a.municipio === name && ALL_TECHS.includes(a.tecnologia),
    );
    const info = Object.values(municipalitiesIndex).find(
      (m) => m.nome === name && m.uf === uf,
    );
    const pop = info?.populacao || 0;
    const { techs, ops, sites } = buildAntennaAggregates(antennas);
    return {
      city: cities.length > 1 ? `${name} (${uf})` : name,
      uf,
      pop,
      techs,
      ops,
      _sites: sites,
    };
  });
}

// ── Routing ─────────────────────────────────────────────────────────────────
function toggleFilters(show) {
  const d = show ? "" : "none";
  for (const id of ["tech-sep", "tech-filter-row", "op-sep", "op-filter-row"]) {
    document.getElementById(id).style.display = d;
  }
}

async function loadScope() {
  const main = document.querySelector("main");
  main.innerHTML =
    '<div class="stats-loading"><div class="stats-spinner"></div>Carregando…</div>';
  try {
    await loadMunicipalities();
    buildSearchIndex();
    const mode = getMode();
    viewMode = mode;

    if (mode === "national") {
      toggleFilters(false);
      renderNationalView();
    } else if (mode === "single-state") {
      toggleFilters(true);
      const uf = [...selection.states][0];
      await loadStateAntennas(uf);
      buildSingleStateRows(uf, stateDataCache[uf]);
      renderDetailView(`Tabela completa — ${UF_NAMES[uf]}`, "Município");
    } else if (selection.cities.length > 0) {
      toggleFilters(true);
      await buildCityRows(selection.cities);
      renderDetailView("Comparação entre cidades", "Cidade");
    } else {
      toggleFilters(true);
      await buildMultiStateRows([...selection.states]);
      renderDetailView("Comparação entre estados", "Estado");
    }
  } catch (err) {
    main.innerHTML = `<p style="color:#f85149;padding:2rem">Erro ao carregar dados: ${err.message}</p>`;
  }
}

// ── National view ───────────────────────────────────────────────────────────
function renderNationalView() {
  const stateAgg = {};
  for (const [, m] of Object.entries(municipalitiesIndex)) {
    const uf = m.uf;
    if (!stateAgg[uf]) stateAgg[uf] = { pop: 0, antenas: 0, municipalities: 0 };
    stateAgg[uf].pop += m.populacao || 0;
    stateAgg[uf].antenas += m.antenas || 0;
    stateAgg[uf].municipalities++;
  }

  let totalPop = 0,
    totalAnt = 0,
    totalMun = 0;
  for (const a of Object.values(stateAgg)) {
    totalPop += a.pop;
    totalAnt += a.antenas;
    totalMun += a.municipalities;
  }
  const globalPer = +((totalAnt / totalPop) * 10000).toFixed(2);

  allRows = ALL_UFS.filter((uf) => stateAgg[uf]).map((uf) => {
    const a = stateAgg[uf];
    return {
      city: UF_NAMES[uf],
      uf,
      pop: a.pop,
      total: a.antenas,
      per10k: a.pop ? +((a.antenas / a.pop) * 10000).toFixed(1) : 0,
      municipalities: a.municipalities,
      techs: {},
      ops: {},
      has5g: false,
      new: 0,
      newPct: 0,
    };
  });

  document.querySelector("main").innerHTML = `
          <div class="cards" id="summary-cards"></div>
          <section>
            <h2>Torres por estado</h2>
            <div class="charts">
              <div class="chart-box">
                <h3>Torres por 10 mil hab. — por estado</h3>
                <canvas id="chart-per-capita" height="500"></canvas>
              </div>
              <div class="chart-box">
                <h3>Total de torres por estado</h3>
                <canvas id="chart-total" height="500"></canvas>
              </div>
            </div>
          </section>
          <section>
            <h2>Destaques</h2>
            <div class="ranking" id="ranking"></div>
          </section>
          <section>
            <h2>Tabela por estado</h2>
            <div class="table-wrap">
              <table id="main-table">
                <thead>
                  <tr>
                    <th data-col="city" data-type="str">Estado <span class="sort-icon">↕</span></th>
                    <th data-col="pop" data-type="num" class="num">População <span class="sort-icon">↕</span></th>
                    <th data-col="total" data-type="num" class="num">Torres <span class="sort-icon">↕</span></th>
                    <th data-col="per10k" data-type="num" class="num sorted">/ 10 mil hab. <span class="sort-icon">↓</span></th>
                    <th data-col="municipalities" data-type="num" class="num">Municípios <span class="sort-icon">↕</span></th>
                  </tr>
                </thead>
                <tbody id="table-body"></tbody>
              </table>
            </div>
          </section>
          <footer><p>Selecione um estado para ver estatísticas detalhadas por município.</p></footer>
        `;

  document.getElementById("summary-cards").innerHTML = [
    { label: "Estados", value: ALL_UFS.length, sub: "" },
    { label: "Municípios", value: fmt(totalMun), sub: "" },
    { label: "Torres", value: fmt(totalAnt), sub: "" },
    { label: "População total", value: fmt(totalPop), sub: "" },
    {
      label: "Torres / 10 mil hab.",
      value: fmtF(globalPer),
      sub: "Nacional",
    },
  ]
    .map(
      (c) => `<div class="card">
            <div class="label">${c.label}</div>
            <div class="value">${c.value}</div>
            ${c.sub ? `<div class="sub">${c.sub}</div>` : ""}
          </div>`,
    )
    .join("");

  const ordered = [...allRows].sort((a, b) => b.per10k - a.per10k);
  new Chart(document.getElementById("chart-per-capita"), {
    type: "bar",
    data: {
      labels: ordered.map((r) => r.uf),
      datasets: [
        {
          label: "Torres / 10 mil hab.",
          data: ordered.map((r) => r.per10k),
          backgroundColor: "rgba(0,204,153,.7)",
          borderRadius: 3,
        },
      ],
    },
    options: {
      indexAxis: "y",
      responsive: true,
      plugins: { legend: { display: false } },
      scales: CHART_SCALES,
    },
  });

  const byTotal = [...allRows].sort((a, b) => b.total - a.total);
  new Chart(document.getElementById("chart-total"), {
    type: "bar",
    data: {
      labels: byTotal.map((r) => r.uf),
      datasets: [
        {
          label: "Total de torres",
          data: byTotal.map((r) => r.total),
          backgroundColor: "rgba(59,130,246,.6)",
          borderRadius: 3,
        },
      ],
    },
    options: {
      indexAxis: "y",
      responsive: true,
      plugins: { legend: { display: false } },
      scales: CHART_SCALES,
    },
  });

  document.getElementById("ranking").innerHTML = [
    rankBox(
      `${ICON_TROPHY} Mais torres / 10 mil hab.`,
      ordered.slice(0, 5),
      (r) => fmtF(r.per10k),
    ),
    rankBox(
      `${ICON_TREND_DOWN} Menos torres / 10 mil hab.`,
      ordered.slice(-5).reverse(),
      (r) => fmtF(r.per10k),
    ),
    rankBox(`${ICON_SIGNAL} Mais torres (total)`, byTotal.slice(0, 5), (r) =>
      fmt(r.total),
    ),
    rankBox(
      `${ICON_SPARK} Mais municípios`,
      [...allRows]
        .sort((a, b) => b.municipalities - a.municipalities)
        .slice(0, 5),
      (r) => fmt(r.municipalities),
    ),
  ].join("");

  const maxPer10k = Math.max(...allRows.map((r) => r.per10k), 1);
  renderNationalTable(sortedRows(allRows), maxPer10k);
  wireTableSort(() => {
    renderNationalTable(
      sortedRows(allRows),
      Math.max(...allRows.map((r) => r.per10k), 1),
    );
  });
}

function renderNationalTable(data, maxPer10k) {
  document.getElementById("table-body").innerHTML = data
    .map(
      (r) => `
          <tr style="cursor:pointer" data-uf="${r.uf}">
            <td class="city-name">${r.city} <span style="color:var(--muted)">(${r.uf})</span></td>
            <td class="num">${fmt(r.pop)}</td>
            <td class="num hl">${fmt(r.total)}</td>
            <td class="num">
              <span class="bar" style="width:${Math.round((r.per10k / maxPer10k) * 60)}px;background:var(--accent);opacity:.75"></span>
              ${fmtF(r.per10k)}
            </td>
            <td class="num">${fmt(r.municipalities)}</td>
          </tr>`,
    )
    .join("");

  document.querySelectorAll("#table-body tr[data-uf]").forEach((tr) => {
    tr.addEventListener("click", () => {
      selection.states.clear();
      selection.cities.length = 0;
      selection.states.add(tr.dataset.uf);
      renderChips();
      syncUrl();
      loadScope();
    });
  });
}

// ── Detail view (single-state, multi-state, cities) ─────────────────────────
function renderDetailView(tableHeading, entityLabel) {
  const ops = [...new Set(allRows.flatMap((r) => Object.keys(r.ops)))].sort();
  const opGroup = document.getElementById("op-filter-group");
  opGroup.innerHTML =
    '<button class="filter-btn active" data-op="" aria-pressed="true">Todos</button>';
  ops.forEach((op) => {
    const btn = document.createElement("button");
    const isActive = op === activeOp;
    btn.className = "filter-btn" + (isActive ? " active" : "");
    btn.dataset.op = op;
    btn.textContent = op;
    btn.setAttribute("aria-pressed", String(isActive));
    opGroup.appendChild(btn);
  });
  if (activeOp)
    opGroup.querySelector('[data-op=""]')?.classList.remove("active");
  if (activeOp)
    opGroup
      .querySelector('[data-op=""]')
      ?.setAttribute("aria-pressed", "false");

  document.querySelectorAll("#tech-filter-group .filter-btn").forEach((b) => {
    const isActive = b.dataset.tech === activeTech;
    b.classList.toggle("active", isActive);
    b.setAttribute("aria-pressed", String(isActive));
  });

  const showRankings = viewMode === "single-state";
  const chartHeight =
    viewMode === "comparison" ? Math.max(120, allRows.length * 35) : 320;

  document.querySelector("main").innerHTML = `
          <div class="cards" id="summary-cards"></div>
          <section>
            <h2 id="section-heading">Torres por habitante</h2>
            <div class="charts">
              <div class="chart-box">
                <h3 id="chart-per-capita-title">Torres por 10 mil hab.</h3>
                <canvas id="chart-per-capita" height="${chartHeight}"></canvas>
              </div>
              <div class="chart-box">
                <h3>Distribuição de tecnologia</h3>
                <canvas id="chart-tech" height="${chartHeight}"></canvas>
              </div>
            </div>
          </section>
          ${showRankings ? '<section><h2>Destaques</h2><div class="ranking" id="ranking"></div></section>' : ""}
          <section>
            <h2>${tableHeading}</h2>
            <div class="table-wrap">
              <table id="main-table">
                <thead>
                  <tr>
                    <th data-col="city" data-type="str">${entityLabel} <span class="sort-icon">↕</span></th>
                    <th data-col="pop" data-type="num" class="num">População <span class="sort-icon">↕</span></th>
                    <th data-col="total" data-type="num" class="num"><span id="th-towers">Torres</span> <span class="sort-icon">↕</span></th>
                    <th data-col="per10k" data-type="num" class="num sorted">/ 10 mil hab. <span class="sort-icon">↓</span></th>
                    <th data-col="newPct" data-type="num" class="num">Novas (%) <span class="sort-icon">↕</span></th>
                    <th>Operadoras</th>
                    <th>Tecnologias</th>
                  </tr>
                </thead>
                <tbody id="table-body"></tbody>
              </table>
            </div>
          </section>
          ${showRankings ? "<footer><p>* Pop. &lt; 5 mil — per capita pode ser pouco representativo</p></footer>" : ""}
        `;

  initCharts();
  applyFilter(activeTech, activeOp);

  document
    .getElementById("tech-filter-group")
    .addEventListener("click", (e) => {
      const btn = e.target.closest(".filter-btn[data-tech]");
      if (!btn) return;
      document
        .querySelectorAll("#tech-filter-group .filter-btn")
        .forEach((b) => {
          b.classList.remove("active");
          b.setAttribute("aria-pressed", "false");
        });
      btn.classList.add("active");
      btn.setAttribute("aria-pressed", "true");
      activeTech = btn.dataset.tech;
      saveFilters();
      applyFilter(activeTech, activeOp);
    });

  document.getElementById("op-filter-group").addEventListener("click", (e) => {
    const btn = e.target.closest(".filter-btn[data-op]");
    if (!btn) return;
    document
      .querySelectorAll("#op-filter-group .filter-btn")
      .forEach((b) => {
        b.classList.remove("active");
        b.setAttribute("aria-pressed", "false");
      });
    btn.classList.add("active");
    btn.setAttribute("aria-pressed", "true");
    activeOp = btn.dataset.op;
    saveFilters();
    applyFilter(activeTech, activeOp);
  });

  wireTableSort(() => {
    const rows = deriveRows(activeTech, activeOp);
    renderDetailTable(
      sortedRows(rows),
      Math.max(...rows.map((r) => r.per10k), 1),
      activeTech === "Todos"
        ? "var(--accent)"
        : (TECH_COLOR[activeTech] ?? "var(--accent)"),
    );
  });
}

// ── Derive + filter ─────────────────────────────────────────────────────────
function deriveRows(tech, op) {
  return allRows.map((r) => {
    let total = 0,
      newCount = 0;
    for (const s of r._sites) {
      const techOk = tech === "Todos" || s.techs.has(tech);
      const opOk = !op || s.ops.has(op);
      if (techOk && opOk) {
        total++;
        if (s.isNew) newCount++;
      }
    }
    const per10k = r.pop ? +((total / r.pop) * 10000).toFixed(1) : 0;
    const newPct = total ? +((newCount / total) * 100).toFixed(1) : 0;
    const has5g = r._sites.some((s) => s.techs.has("5G"));
    return { ...r, total, new: newCount, per10k, newPct, has5g };
  });
}

function applyFilter(tech, op) {
  const label = tech === "Todos" ? "Todas as gerações" : tech;
  const techColor = TECH_COLOR[tech] ?? "var(--muted)";
  const isComp = viewMode === "comparison";

  const el = document.getElementById("chart-per-capita-title");
  if (el) el.textContent = `Torres ${label} por 10 mil hab.`;
  const thEl = document.getElementById("th-towers");
  if (thEl) thEl.textContent = `Torres ${tech === "Todos" ? "" : tech}`.trim();

  const rows = deriveRows(tech, op);
  const totalPop = allRows.reduce((s, r) => s + r.pop, 0);
  const totalTowers = rows.reduce((s, r) => s + r.total, 0);
  const totalNew = rows.reduce((s, r) => s + r.new, 0);
  const globalPer = totalPop
    ? +((totalTowers / totalPop) * 10000).toFixed(2)
    : 0;
  const cities5g = rows.filter((r) => r.has5g).length;
  const operators = [...new Set(allRows.flatMap((r) => Object.keys(r.ops)))];

  const entityLabel = viewMode === "single-state" ? "Municípios" : "Itens";
  const towerLabel = tech === "Todos" ? "Torres (todas)" : `Torres ${tech}`;
  document.getElementById("summary-cards").innerHTML = [
    {
      label: entityLabel,
      value: rows.length,
      sub: `${cities5g} com 5G`,
    },
    {
      label: towerLabel,
      value: fmt(totalTowers),
      sub: `${fmt(totalNew)} novas (≤1 ano)`,
    },
    { label: "População total", value: fmt(totalPop), sub: "" },
    { label: "Torres / 10 mil hab.", value: fmtF(globalPer), sub: label },
    {
      label: "Operadoras",
      value: operators.length,
      sub: operators.join(", "),
    },
  ]
    .map(
      (c) => `<div class="card">
            <div class="label">${c.label}</div>
            <div class="value">${c.value}</div>
            <div class="sub">${c.sub}</div>
          </div>`,
    )
    .join("");

  const maxPer10k = Math.max(...rows.map((r) => r.per10k), 1);
  const barColor =
    tech === "Todos" ? "var(--accent)" : (TECH_COLOR[tech] ?? "var(--accent)");
  renderDetailTable(sortedRows(rows), maxPer10k, barColor);

  // Charts
  const TOP_N = isComp ? 999 : 20;
  const ordered = [...rows]
    .filter((r) => isComp || r.pop >= POP_THRESHOLD)
    .sort((a, b) => b.per10k - a.per10k);
  const top = ordered.slice(0, TOP_N);

  if (chartPerCapita) {
    chartPerCapita.data.labels = top.map((r) =>
      !isComp && r.pop < POP_THRESHOLD ? r.city + " *" : r.city,
    );
    chartPerCapita.data.datasets[0].label = `Torres ${label} / 10 mil hab.`;
    chartPerCapita.data.datasets[0].data = top.map((r) => r.per10k);
    chartPerCapita.data.datasets[0].backgroundColor =
      tech === "Todos"
        ? top.map((r) =>
          !isComp && r.pop < POP_THRESHOLD
            ? "rgba(255,255,255,.18)"
            : r.has5g
              ? "rgba(0,204,153,.75)"
              : "rgba(59,130,246,.6)",
        )
        : top.map((r) =>
          !isComp && r.pop < POP_THRESHOLD
            ? "rgba(255,255,255,.18)"
            : techColor + "bf",
        );
    chartPerCapita.update();
  }

  if (chartTech) {
    const byTotal = [...rows]
      .filter((r) => isComp || r.pop >= POP_THRESHOLD)
      .sort((a, b) => {
        const ta = Object.values(a.techs).reduce((s, v) => s + v, 0);
        const tb = Object.values(b.techs).reduce((s, v) => s + v, 0);
        return tb - ta;
      })
      .slice(0, TOP_N);
    chartTech.data.labels = byTotal.map((r) => r.city);
    ALL_TECHS.forEach((t, i) => {
      chartTech.data.datasets[i].data = byTotal.map((r) => r.techs[t] || 0);
    });
    chartTech.update();
  }

  // Rankings (single-state only)
  const rankingEl = document.getElementById("ranking");
  if (rankingEl) {
    const byPer10k = [...rows]
      .filter((r) => r.total > 0 && r.pop >= POP_THRESHOLD)
      .sort((a, b) => b.per10k - a.per10k);
    const byNew = [...rows]
      .filter((r) => r.new > 0 && r.pop >= POP_THRESHOLD)
      .sort((a, b) => b.newPct - a.newPct)
      .slice(0, 5);
    const by5g = [...allRows]
      .filter((r) => r.pop >= POP_THRESHOLD)
      .map((r) => ({
        ...r,
        v5g: r._sites.filter((s) => s.techs.has("5G")).length,
      }))
      .sort((a, b) => b.v5g - a.v5g)
      .slice(0, 5);

    rankingEl.innerHTML = [
      rankBox(
        `${ICON_TROPHY} Mais torres / 10 mil hab.`,
        byPer10k.slice(0, 5),
        (r) => fmtF(r.per10k),
        true,
      ),
      rankBox(
        `${ICON_TREND_DOWN} Menos torres / 10 mil hab.`,
        byPer10k.slice(-5).reverse(),
        (r) => fmtF(r.per10k),
        true,
      ),
      rankBox(
        `${ICON_SIGNAL} Mais torres 5G`,
        by5g,
        (r) => `${r.v5g} torres`,
        true,
      ),
      rankBox(
        `${ICON_SPARK} Mais novas (% do total)`,
        byNew,
        (r) => fmtF(r.newPct) + "%",
        true,
      ),
    ].join("");
  }
}

// ── Table rendering ─────────────────────────────────────────────────────────
function renderDetailTable(data, maxPer10k, barColor) {
  document.getElementById("table-body").innerHTML = data
    .map(
      (r) => `
          <tr>
            <td class="city-name">${r.city}${r.has5g ? '<span class="badge-5g">5G</span>' : ""}${viewMode === "single-state" && r.pop < POP_THRESHOLD ? ' <span style="color:var(--muted);font-size:.7rem" title="Pop. < ' + fmt(POP_THRESHOLD) + '">*</span>' : ""}</td>
            <td class="num">${fmt(r.pop)}</td>
            <td class="num hl">${r.total}</td>
            <td class="num">
              <span class="bar" style="width:${Math.round((r.per10k / maxPer10k) * 60)}px;background:${barColor};opacity:.75"></span>
              ${fmtF(r.per10k)}
            </td>
            <td class="num">${r.newPct > 0 ? fmtF(r.newPct) + "%" : "—"}</td>
            <td>${stackBar(
        r.ops,
        OP_COLOR,
        Object.values(r.ops).reduce((s, v) => s + v, 0),
      )}</td>
            <td>${stackBar(
        r.techs,
        TECH_COLOR,
        Object.values(r.techs).reduce((s, v) => s + v, 0),
      )}</td>
          </tr>`,
    )
    .join("");
}

// ── Charts ──────────────────────────────────────────────────────────────────
function initCharts() {
  chartPerCapita = new Chart(document.getElementById("chart-per-capita"), {
    type: "bar",
    data: {
      labels: [],
      datasets: [{ label: "", data: [], backgroundColor: [], borderRadius: 3 }],
    },
    options: {
      indexAxis: "y",
      responsive: true,
      plugins: { legend: { display: false } },
      scales: CHART_SCALES,
    },
  });

  const isComp = viewMode === "comparison";
  const initRows = deriveRows("Todos", "");
  const ordered = [...initRows]
    .filter((r) => isComp || r.pop >= POP_THRESHOLD)
    .sort((a, b) => {
      const ta = Object.values(a.techs).reduce((s, v) => s + v, 0);
      const tb = Object.values(b.techs).reduce((s, v) => s + v, 0);
      return tb - ta;
    })
    .slice(0, isComp ? 999 : 20);

  chartTech = new Chart(document.getElementById("chart-tech"), {
    type: "bar",
    data: {
      labels: ordered.map((r) => r.city),
      datasets: ALL_TECHS.map((t) => ({
        label: t,
        data: ordered.map((r) => r.techs[t] || 0),
        backgroundColor: TECH_COLOR[t],
        borderRadius: 2,
      })),
    },
    options: {
      indexAxis: "y",
      responsive: true,
      plugins: {
        legend: {
          position: "top",
          labels: { color: "#8b949e", boxWidth: 12 },
        },
      },
      scales: {
        x: { stacked: true, ...CHART_SCALES.x },
        y: { stacked: true, ...CHART_SCALES.y },
      },
    },
  });
}

// ── Shared helpers ──────────────────────────────────────────────────────────
function rankBox(title, items, valFn, showSmallMarker = false) {
  return `<div class="rank-box"><h3>${title}</h3>${items
    .map(
      (r) =>
        `<div class="rank-item"><span>${r.city}${showSmallMarker && r.pop < POP_THRESHOLD ? ' <span style="color:var(--muted);font-size:.7rem">*</span>' : ""}${!showSmallMarker && r.uf ? ` (${r.uf})` : ""}</span><span class="rank-val">${valFn(r)}</span></div>`,
    )
    .join("")}</div>`;
}

function sortedRows(rows) {
  return [...rows].sort((a, b) => {
    const av = a[sortCol],
      bv = b[sortCol];
    return typeof av === "string"
      ? sortDir * av.localeCompare(bv, "pt-BR")
      : sortDir * (av - bv);
  });
}

function wireTableSort(renderFn) {
  document.querySelectorAll("thead th[data-col]").forEach((th) => {
    th.addEventListener("click", () => {
      const col = th.dataset.col;
      if (sortCol === col) {
        sortDir *= -1;
      } else {
        sortCol = col;
        sortDir = col === "city" ? 1 : -1;
      }
      document.querySelectorAll("thead th").forEach((t) => {
        t.classList.remove("sorted");
        const ic = t.querySelector(".sort-icon");
        if (ic) ic.textContent = "↕";
      });
      th.classList.add("sorted");
      th.querySelector(".sort-icon").textContent = sortDir === -1 ? "↓" : "↑";
      renderFn();
    });
  });
}

// ── Init ────────────────────────────────────────────────────────────────────
loadFromUrl();
buildSearchIndex();
initScopeSelector();
loadScope();
