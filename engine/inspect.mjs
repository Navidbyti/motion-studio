/* Composition inspector: walks a HyperFrames composition's GSAP timeline in
 * headless Chrome (raw CDP, no npm dependencies) and records, for every sample:
 * visible text blocks with their boxes, font sizes and effective opacity,
 * plus the timeline labels and Studio hit registry. Output is JSON for the
 * Python QA (copy, number provenance, safe area, text size, beat accuracy).
 *
 * The HyperFrames runtime is not loaded. The inspector mounts sub-compositions
 * the way the runtime does (clone the <template>, run its scripts, nest each
 * scene timeline into the root at the slot's data-start) and reproduces clip
 * visibility from data-start / data-duration (numeric or "<clip id> +/- s").
 *
 *   node engine/inspect.mjs --project projects/x --chrome <path> --out qa/inspect.json [--step-frames 3]
 */
import { spawn } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { pathToFileURL } from "node:url";

const argv = process.argv.slice(2);
const opt = (name, dflt) => { const i = argv.indexOf("--" + name); return i >= 0 ? argv[i + 1] : dflt; };
const PROJECT = resolve(opt("project", "."));
const CHROME = opt("chrome", process.env.HYPERFRAMES_BROWSER_PATH || process.env.CHROME);
const OUT = opt("out", join(PROJECT, "renders", "qa", "inspect.json"));
const STEP = Number(opt("step-frames", "3"));
if (!CHROME) { console.error("inspect: pass --chrome <path> (or set HYPERFRAMES_BROWSER_PATH)"); process.exit(2); }

const html = readFileSync(join(PROJECT, "index.html"), "utf8");
const W = Number((html.match(/data-width="(\d+)"/) || [])[1] || 1080);
const H = Number((html.match(/data-height="(\d+)"/) || [])[1] || 1920);
const PAGE = pathToFileURL(join(PROJECT, "index.html")).href;
const PORT = 9400 + Math.floor((process.pid % 500));
const PROFILE = mkdtempSync(join(tmpdir(), "mstudio-inspect-"));

const chrome = spawn(CHROME, [
  "--headless=new", `--remote-debugging-port=${PORT}`, `--user-data-dir=${PROFILE}`, "--no-first-run",
  "--no-default-browser-check", "--disable-extensions", "--allow-file-access-from-files", "--hide-scrollbars",
  "--mute-audio", "--force-device-scale-factor=1", `--window-size=${W},${H}`, "--disable-background-timer-throttling",
  "about:blank",
], { stdio: "ignore" });
const cleanup = () => { try { chrome.kill(); } catch {} try { rmSync(PROFILE, { recursive: true, force: true }); } catch {} };
process.on("exit", cleanup);

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let target;
for (let i = 0; i < 100 && !target; i++) {
  try { const list = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json(); target = list.find((t) => t.type === "page"); } catch {}
  if (!target) await sleep(100);
}
if (!target) { console.error("inspect: Chrome did not start"); process.exit(1); }
const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((r, j) => { ws.onopen = r; ws.onerror = j; });
let seq = 0; const pending = new Map(); const consoleErrors = [];
ws.onmessage = (m) => {
  const msg = JSON.parse(m.data);
  if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); }
  if (msg.method === "Runtime.exceptionThrown") consoleErrors.push(msg.params.exceptionDetails.exception?.description || msg.params.exceptionDetails.text);
  if (msg.method === "Runtime.consoleAPICalled" && msg.params.type === "error") consoleErrors.push(msg.params.args.map((a) => a.value ?? a.description).join(" "));
};
const send = (method, params = {}) => new Promise((r) => { const id = ++seq; pending.set(id, r); ws.send(JSON.stringify({ id, method, params })); });
const ev = async (expression) => {
  const r = await send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
  if (r.result?.exceptionDetails) throw new Error(r.result.exceptionDetails.exception?.description || "evaluate failed");
  return r.result?.result?.value;
};

await send("Runtime.enable");
await send("Page.enable");
await send("Emulation.setDeviceMetricsOverride", { width: W, height: H, deviceScaleFactor: 1, mobile: false });
// HyperFrames creates window.__timelines before inline scripts run; do the same.
await send("Page.addScriptToEvaluateOnNewDocument", { source: "window.__timelines = window.__timelines || {};" });
await send("Page.navigate", { url: PAGE });
let ready = false;
for (let i = 0; i < 150 && !ready; i++) { await sleep(100); try { ready = await ev("!!(window.__timelines && window.__timelines.main) && document.readyState === 'complete'"); } catch {} }
if (!ready) { console.error("inspect: window.__timelines.main never registered"); console.error(consoleErrors.join("\n")); process.exit(1); }
const mounted = await ev(`(() => {
  const out = [];
  for (const slot of document.querySelectorAll('[data-composition-src]')) {
    const xhr = new XMLHttpRequest();
    xhr.open('GET', slot.getAttribute('data-composition-src'), false);
    xhr.send();
    const doc = new DOMParser().parseFromString(xhr.responseText, 'text/html');
    const tpl = doc.querySelector('template');
    const frag = tpl ? tpl.content : doc.body;
    for (const node of [...frag.childNodes]) {
      if (node.nodeName === 'SCRIPT') {
        const s = document.createElement('script'); s.textContent = node.textContent; slot.appendChild(s);
      } else slot.appendChild(document.importNode(node, true));
    }
    const id = slot.getAttribute('data-composition-id');
    const child = window.__timelines[id];
    if (child) window.__timelines.main.add(child.paused(false), Number(slot.getAttribute('data-start') || 0));
    out.push({ id, timeline: !!child });
  }
  return out;
})()`);
await ev("document.fonts.ready.then(() => true)");

const setup = `(() => {
  const root = document.querySelector('[data-composition-id="main"]');
  const fps = (window.TIMING && window.TIMING.fps) || 30;
  const total = Number(root.getAttribute('data-duration')) || window.__timelines.main.duration();
  const timed = [...document.querySelectorAll('[data-start]')];
  const byId = Object.fromEntries(timed.filter(e => e.id).map(e => [e.id, e]));
  const win = new Map();
  const resolveStart = (el, depth = 0) => {
    const raw = (el.getAttribute('data-start') || '0').trim();
    if (/^-?[\\d.]+$/.test(raw)) return Number(raw);
    const m = raw.match(/^([\\w-]+)\\s*([+-])?\\s*([\\d.]+)?$/);
    if (!m || !byId[m[1]] || depth > 20) return 0;
    const ref = byId[m[1]]; const refStart = resolveStart(ref, depth + 1);
    const refDur = Number(ref.getAttribute('data-duration') || 0);
    const off = m[3] ? Number(m[3]) * (m[2] === '-' ? -1 : 1) : 0;
    return refStart + refDur + off;
  };
  for (const el of timed) {
    const slot = el.parentElement ? el.parentElement.closest('[data-composition-src]') : null;
    const base = slot ? Number(slot.getAttribute('data-start') || 0) : 0;
    const s = base + resolveStart(el); const d = Number(el.getAttribute('data-duration') || 1e9); win.set(el, [s, s + d]);
  }
  window.__inspect = { root, fps, total, win };
  return { fps, total, W: root.clientWidth || ${W}, H: root.clientHeight || ${H} };
})()`;
const meta = await ev(setup);

const sampleExpr = (t) => `(() => {
  const { root, win } = window.__inspect; const t = ${t};
  window.__timelines.main.seek(t, false);
  const vis = (el) => {
    let op = 1;
    for (let n = el; n && n !== document.documentElement; n = n.parentElement) {
      const w = win.get(n); if (w && !(t >= w[0] - 1e-6 && t < w[1] - 1e-6)) return 0;
      if (n.hasAttribute && n.hasAttribute('data-hidden')) return 0;
      const cs = getComputedStyle(n);
      if (cs.display === 'none' || cs.visibility === 'hidden') return 0;
      op *= Number(cs.opacity);
      if (op < 0.02) return 0;
    }
    return op;
  };
  const isBlock = (el) => { const d = getComputedStyle(el).display; return el.hasAttribute('data-copy') || !d.startsWith('inline') || el === root; };
  const blocks = new Map();
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    const txt = node.textContent.replace(/\\s+/g, ' ').trim();
    if (!txt) continue;
    const el = node.parentElement; if (!el || el.closest('script,style,svg title,[data-qa-ignore]')) continue;
    const op = vis(el); if (op <= 0) continue;
    const range = document.createRange(); range.selectNodeContents(node);
    const r = range.getBoundingClientRect(); if (r.width < 1 || r.height < 1) continue;
    let block = el; while (block !== root && !isBlock(block)) block = block.parentElement;
    const cs = getComputedStyle(el);
    const valueEl = el.closest('[data-value]');
    const entry = blocks.get(block) || { text: block.textContent.replace(/\\s+/g, ' ').trim(), x0: 1e9, y0: 1e9, x1: -1e9, y1: -1e9, minFont: 1e9, opacity: 0,
      provenance: (block.closest('[data-provenance]') || {}).dataset?.provenance || null, value: valueEl ? valueEl.dataset.value : null, dir: getComputedStyle(block).direction };
    entry.x0 = Math.min(entry.x0, r.left); entry.y0 = Math.min(entry.y0, r.top); entry.x1 = Math.max(entry.x1, r.right); entry.y1 = Math.max(entry.y1, r.bottom);
    entry.minFont = Math.min(entry.minFont, parseFloat(cs.fontSize) * (r.height / (el.offsetHeight || r.height) || 1));
    entry.opacity = Math.max(entry.opacity, op);
    blocks.set(block, entry);
  }
  return [...blocks.values()].map(b => ({ text: b.text, box: [Math.round(b.x0), Math.round(b.y0), Math.round(b.x1), Math.round(b.y1)],
    font: Math.round(b.minFont * 10) / 10, opacity: Math.round(b.opacity * 100) / 100, provenance: b.provenance, value: b.value, dir: b.dir }));
})()`;

const samples = [];
const frames = Math.round(meta.total * meta.fps);
for (let f = 0; f < frames; f += STEP) {
  const t = f / meta.fps;
  samples.push({ frame: f, t: Math.round(t * 10000) / 10000, text: await ev(sampleExpr(t)) });
}
const timeline = await ev(`(() => {
  const tl = window.__timelines.main;
  return { duration: tl.duration(), labels: tl.labels || {}, hits: window.__studioHits || [], values: [...new Set(window.__studioValues || [])],
           scenes_mounted: Object.keys(window.__timelines).filter(k => k !== 'main'), events_used: [...new Set(window.__studioEvents || [])],
           tweens: tl.getChildren(true, true, false).length };
})()`);
writeFileSync(OUT, JSON.stringify({ project: PROJECT, canvas: { w: W, h: H }, fps: meta.fps, duration: meta.total, step_frames: STEP,
  mounted, samples, timeline, console_errors: consoleErrors }, null, 1));
console.log(`inspect: ${samples.length} samples, ${timeline.hits.length} hits, ${consoleErrors.length} console errors -> ${OUT}`);
ws.close();
cleanup();
process.exit(0);
