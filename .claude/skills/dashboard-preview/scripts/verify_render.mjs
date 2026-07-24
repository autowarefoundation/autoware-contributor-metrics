// Executes the dashboard's main.js against real data in a stubbed DOM, so that
// a render-time exception is caught here instead of on the deployed page.
//
// The page loads its JSON at runtime and draws everything client-side, so a bad
// assumption about the data's shape only fails in the browser. That is how a
// blank dashboard once shipped: one chart threw, and the throw aborted every
// section after it. Running the same file here reproduces that in a second.
//
// Usage:
//   node verify_render.mjs <public-dir> [data-dir] [--json] [--dump <selector>]
//
// data-dir defaults to public-dir. Exits non-zero if anything threw, so this
// can gate a commit or a deploy.

import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const args = process.argv.slice(2);
const flags = new Set(args.filter((a) => a.startsWith('--')));
const positional = args.filter((a) => !a.startsWith('--'));
const dumpIndex = args.indexOf('--dump');
const dumpSelector = dumpIndex !== -1 ? args[dumpIndex + 1] : null;

const publicDir = positional[0];
const dataDir = positional[1] && positional[1] !== dumpSelector ? positional[1] : publicDir;

if (!publicDir) {
  console.error('usage: node verify_render.mjs <public-dir> [data-dir] [--json] [--dump <selector>]');
  process.exit(2);
}

const elements = new Map();
const charts = [];
const errors = [];
const consoleErrors = [];
const domReadyListeners = [];

function makeElement(name) {
  return {
    __name: name,
    innerHTML: '',
    textContent: '',
    value: '',
    checked: false,
    dataset: {},
    style: {},
    classList: { add() {}, remove() {}, toggle() {}, contains: () => false },
    children: [],
    setAttribute() {}, getAttribute: () => null, removeAttribute() {},
    addEventListener() {}, removeEventListener() {}, click() {},
    appendChild() {}, removeChild() {}, remove() {}, insertAdjacentHTML() {},
    closest: () => null,
    querySelector: (s) => element(`${name} ${s}`),
    querySelectorAll: (s) => [element(`${name} ${s}`)],
    getBoundingClientRect: () => ({ top: 0, left: 0, width: 1200, height: 400 }),
    scrollIntoView() {}, focus() {},
  };
}

function element(selector) {
  if (!elements.has(selector)) elements.set(selector, makeElement(selector));
  return elements.get(selector);
}

const document = {
  documentElement: makeElement(':root'),
  body: makeElement('body'),
  readyState: 'complete',
  querySelector: element,
  // One stand-in per selector: enough for the loops the page runs over nav
  // links and sections, without pretending to know the real element count.
  querySelectorAll: (s) => [element(s)],
  getElementById: (id) => element(`#${id}`),
  createElement: (tag) => makeElement(`<${tag}>`),
  addEventListener(type, fn) {
    if (type === 'DOMContentLoaded') domReadyListeners.push(fn);
  },
  removeEventListener() {},
};

class ApexCharts {
  constructor(el, options) { this.el = el; this.options = options; charts.push(options); }
  render() { return Promise.resolve(); }
  updateOptions() {} updateSeries() {} destroy() {}
}

const storage = new Map();
const localStorage = {
  getItem: (k) => (storage.has(k) ? storage.get(k) : null),
  setItem: (k, v) => storage.set(k, String(v)),
  removeItem: (k) => storage.delete(k),
};

async function fetchStub(url) {
  const file = path.join(dataDir, path.basename(String(url)));
  if (!fs.existsSync(file)) {
    const err = new Error(`404 ${url}`);
    err.status = 404;
    throw err;
  }
  const text = fs.readFileSync(file, 'utf8');
  return { ok: true, status: 200, json: async () => JSON.parse(text), text: async () => text };
}

const sandboxConsole = {
  ...console,
  error: (...a) => { consoleErrors.push(a.map(String).join(' ')); },
};

const windowStub = {
  innerWidth: 1400,
  innerHeight: 900,
  location: { href: 'http://localhost/', search: '', hash: '' },
  addEventListener() {}, removeEventListener() {},
  matchMedia: () => ({ matches: false, addEventListener() {}, addListener() {}, removeEventListener() {} }),
  requestAnimationFrame: (fn) => fn(),
  localStorage,
  scrollTo() {},
};

// Only host objects are injected. Standard built-ins already exist inside the
// context, and passing this realm's copies in would break instanceof checks.
const sandbox = {
  document,
  window: windowStub,
  ApexCharts,
  fetch: fetchStub,
  localStorage,
  matchMedia: windowStub.matchMedia,
  requestAnimationFrame: windowStub.requestAnimationFrame,
  IntersectionObserver: class { observe() {} unobserve() {} disconnect() {} },
  ResizeObserver: class { observe() {} unobserve() {} disconnect() {} },
  console: sandboxConsole,
  setTimeout, clearTimeout, setInterval, clearInterval, queueMicrotask,
};
sandbox.globalThis = sandbox;
sandbox.self = sandbox;
vm.createContext(sandbox);

process.on('unhandledRejection', (e) => {
  errors.push(`unhandledRejection: ${(e && e.stack) || e}`);
});

const mainPath = path.join(publicDir, 'main.js');
if (!fs.existsSync(mainPath)) {
  console.error(`not found: ${mainPath}`);
  process.exit(2);
}

try {
  vm.runInContext(fs.readFileSync(mainPath, 'utf8'), sandbox, { filename: 'main.js' });
  for (const fn of domReadyListeners) fn();
} catch (e) {
  errors.push(`threw during evaluation: ${(e && e.stack) || e}`);
}

// The page's top-level work is async, so give its promises time to settle.
await new Promise((r) => setTimeout(r, 2000));

const report = {
  ok: errors.length === 0,
  errors,
  consoleErrors,
  chartCount: charts.length,
  chartTitles: charts.map((c) => c && c.title && c.title.text).filter(Boolean),
  seriesPerChart: charts.map((c) => ({
    title: (c && c.title && c.title.text) || '(untitled)',
    series: (c && c.series ? c.series : []).map((s) => s && s.name).filter(Boolean),
  })),
  renderedSelectors: [...elements.entries()]
    .filter(([, el]) => el.innerHTML)
    .map(([selector, el]) => ({ selector, length: el.innerHTML.length })),
};

if (dumpSelector) {
  report.dump = { selector: dumpSelector, innerHTML: elements.get(dumpSelector)?.innerHTML ?? null };
}

if (flags.has('--json')) {
  console.log(JSON.stringify(report, null, 2));
} else {
  console.log(report.ok ? 'PASS — main.js ran with no uncaught errors' : 'FAIL — main.js threw');
  for (const e of errors) console.log(`  error: ${e}`);
  for (const e of consoleErrors) console.log(`  console.error: ${e}`);
  console.log(`  charts rendered: ${report.chartCount}`);
  for (const c of report.seriesPerChart) {
    console.log(`    ${c.title}: ${c.series.length} series`);
  }
  console.log(`  sections with content: ${report.renderedSelectors.length}`);
  for (const s of report.renderedSelectors) console.log(`    ${s.selector} (${s.length} chars)`);
  if (report.dump) {
    console.log(`\n  --- ${report.dump.selector} ---`);
    console.log(report.dump.innerHTML === null ? '  (element never rendered)' : report.dump.innerHTML);
  }
}

process.exit(report.ok ? 0 : 1);
