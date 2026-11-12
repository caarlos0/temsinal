const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { join } = require("node:path");
const { test } = require("node:test");
const vm = require("node:vm");

const source = readFileSync(join(__dirname, "main.js"), "utf8");

async function renderCity(name, uf) {
  const writes = [];
  const requests = [];
  const elements = new Map();
  function element(id) {
    return {
      style: {},
      dataset: {},
      classList: { add() {}, remove() {}, toggle() {} },
      set innerHTML(value) { writes.push({ id, value }); },
      get innerHTML() { return ""; },
      addEventListener() {},
      setAttribute() {},
      insertBefore() {},
      appendChild() {},
      querySelectorAll() { return []; },
      querySelector() { return element("child"); },
    };
  }
  const getElement = (id) => {
    if (!elements.has(id)) elements.set(id, element(id));
    return elements.get(id);
  };
  const context = {
    URL,
    URLSearchParams,
    console,
    location: { search: "?cities=" + encodeURIComponent(`${name}|${uf}`) },
    localStorage: { getItem() { return null; } },
    document: {
      getElementById: getElement,
      querySelector: getElement,
      querySelectorAll() { return []; },
      createElement() { return element("chip"); },
      addEventListener() {},
    },
    fetch: async (url) => {
      requests.push(url);
      return {
        ok: true,
        json: async () => url.endsWith("municipalities.json")
          ? { synthetic: { nome: name, uf, populacao: 100, lat: -25.4 } }
          : [{ municipio: name, tecnologia: "5G", operadora: "Audit", lat: -25.4, lon: -49.2 }],
      };
    },
    Chart: function (_, options) {
      this.data = options.data;
      this.update = () => {};
    },
  };
  vm.createContext(context);
  vm.runInContext(source, context);
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(vm.runInContext("allRows[0].city", context), name);
  return { writes, requests };
}

test("URL city markup is text in chips, labels and table cells", async () => {
  const name = '<b title="audit">City</b>';
  const escaped = "&lt;b title=&quot;audit&quot;&gt;City&lt;/b&gt;";
  const { writes } = await renderCity(name, "PR");
  const chip = writes.find((write) => write.id === "chip");
  const table = writes.findLast((write) => write.id === "table-body");
  assert.ok(chip, "city chip was not rendered");
  assert.ok(table, "city table was not rendered");
  assert.ok(!chip.value.includes(name), "URL city markup entered chip HTML");
  assert.ok(chip.value.includes(escaped));
  assert.ok(chip.value.includes(`aria-label="Remover ${escaped}"`));
  assert.ok(!table.value.includes(name), "URL city markup entered table HTML");
  assert.ok(table.value.includes(escaped));
});

test("URL state markup is text in city chips", async () => {
  const { writes } = await renderCity("City", '<b title="audit">PR</b>');
  const chip = writes.find((write) => write.id === "chip");
  assert.ok(chip, "city chip was not rendered");
  assert.ok(!chip.value.includes('<b title="audit">'), "URL state markup entered chip HTML");
  assert.ok(chip.value.includes("&lt;b title=&quot;audit&quot;&gt;PR&lt;/b&gt;"));
});

test("legitimate URL city names keep their data identity", async () => {
  const { writes, requests } = await renderCity('D\'Agua & "Centro"', "PR");
  const table = writes.findLast((write) => write.id === "table-body");
  assert.ok(table.value.includes("D&#39;Agua &amp; &quot;Centro&quot;"));
  assert.deepEqual(requests, ["../data/municipalities.json", "../data/antennas/PR.json"]);
});
