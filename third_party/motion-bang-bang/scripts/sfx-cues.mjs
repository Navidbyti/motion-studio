/* =========================================================
   SFX CUE MINER — turn an animation timeline into a sound cue sheet.

   The bundle in assets/sfx holds one recording per *kind of motion*, not per
   event: the 824 tweens behind a five-minute explainer must not become 824
   generations. This script reads a rendered composition's GSAP timeline in
   headless Chrome, decides which family each motion belongs to, prunes the
   list down to a density the ear can follow, and writes assets/sfx-cues.json
   for scripts/sfx-mix.mjs to place.

   Prerequisite: the page exposes window.OPENER = { ready, tl } or
   window.__timelines["main"] (HyperFrames) — every starter in this skill does.
   Nothing is played; the timeline is only walked.

   Usage (from the project folder; no server, no npm install, system Chrome):
     node <skill>/scripts/sfx-cues.mjs
     node <skill>/scripts/sfx-cues.mjs --dry            # report only, write nothing
     node <skill>/scripts/sfx-cues.mjs --why           # what stayed silent, and why
     URL="file:///C:/proyek/index.html?clean=1" BUNDLE="C:/skill/assets/sfx" node sfx-cues.mjs
     --out assets/sfx-cues.json  --fps 30  --land-at 0.5  --mask-ms 60  --max-per-s 1.6
     --chrome <path-to-chrome>  --port 9344
     --word-clicks   # text reveals are answered by the camera layer, one click per word

   --word-clicks is a different contract from the rest of the sheet. The normal
   rule is "one sound per event, sparse enough to follow". A word-by-word
   caption is not one event: it is a roll of small events, and a viewer who sees
   twelve words arrive expects twelve clicks. Those cues are texture, so they
   skip the masking and global-budget pruners and are limited only by their
   family's max_hits_per_s.

   That run on a real 285 s explainer: 824 tweens -> 422 candidates -> 219 cues,
   0.77 cue/second. The printed tally is the point of the tool: cue counts per
   family and the reason each dropped cue was dropped. Read it before touching
   the rule table.
   ========================================================= */
import { spawn } from 'node:child_process';
import { readFileSync, writeFileSync, rmSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const argv = process.argv.slice(2);
const opt = (name, dflt) => {
  const i = argv.indexOf('--' + name);
  if (i >= 0 && argv[i + 1] && !argv[i + 1].startsWith('--')) return argv[i + 1];
  const env = process.env[name.toUpperCase().replace(/-/g, '_')];
  return env !== undefined ? env : dflt;
};
const isDry = argv.includes('--dry');

const round = (v) => Math.round(v * 1000) / 1000;
const clamp = (v) => Math.max(0.2, Math.min(1, v));

const CHROME = opt('chrome', process.env.CHROME || 'C:/Program Files/Google/Chrome/Application/chrome.exe');
const PROJ = process.cwd().replace(/\\/g, '/');
const PAGE = opt('url', pathToFileURL(PROJ).href + '/index.html?clean=1');
const SKILL_ROOT = dirname(dirname(fileURLToPath(import.meta.url)));
const BUNDLE = opt('bundle', join(SKILL_ROOT, 'assets', 'sfx'));
const OUT = opt('out', 'assets/sfx-cues.json');
const FPS = Number(opt('fps', 30));
const LAND_AT = Number(opt('land-at', 0.5));   // where inside an entrance the hit lands
const MAX_PER_S = Number(opt('max-per-s', 1.6));
const MASK_MS = Number(opt('mask-ms', 60));    // two sounds inside 60 ms read as one event
const PORT = Number(opt('port', 9344));
const PROFILE = opt('profile', join(PROJ, '.sfx-profile'));
const WORD_CLICKS = argv.includes('--word-clicks');

/* Families ranked by how much they need to be heard. When two cues collide the
   stronger one wins, which is what stops a page-turn from eating an impact. */
const PRIORITY = ['impact', 'transition', 'stamp', 'whoosh', 'accent', 'paper', 'pen', 'ui', 'camera', 'ambience'];
const rank = (f) => { const i = PRIORITY.indexOf(f); return i < 0 ? 99 : i; };

const manifest = JSON.parse(readFileSync(join(BUNDLE, 'manifest.json'), 'utf8'));
const mix = Object.fromEntries(Object.entries(manifest.mix || {}).filter(([, v]) => v && typeof v === 'object'));
const assets = (manifest.assets || []).filter(a => a && a.file);
if (!assets.length) { console.error('Bundle kosong — jalankan sfx --spec dulu.'); process.exit(1); }

/* verb -> take, straight from each asset's `trigger` list in library.json, so the
   spec file stays the one place where a sound is bound to a motion. */
const byVerb = {};
for (const a of assets) for (const v of (a.trigger || [])) if (!(v in byVerb)) byVerb[v] = a;
const byFamily = {};
for (const a of assets) (byFamily[a.family] = byFamily[a.family] || []).push(a);
const pick = (family, key) => (byFamily[family] || []).find(a => a.file.includes(key)) || (byFamily[family] || [])[0];

/* Every take that answers a verb, in manifest order. A roll of twelve clicks over
   one caption must not be one recording twelve times: rotation is what keeps a
   dense layer from reading as a machine gun. */
const byVerbPool = {};
for (const a of assets) for (const v of (a.trigger || [])) (byVerbPool[v] = byVerbPool[v] || []).push(a);
let roll = 0;
const pickVerb = (verb) => {
  const pool = byVerbPool[verb] || [];
  return pool.length ? pool[roll++ % pool.length] : byVerb[verb];
};

/* ---- browser side: describe every motion the timeline contains ------------ */
const PROBE = `(() => {
  const RESERVED = new Set(['duration','delay','ease','onUpdate','onComplete','onStart','onEnd',
    'onRepeat','onReverseComplete','callbackScope','repeat','repeatDelay','yoyo','paused','data',
    'id','stagger','keyframes','parent','overwrite','immediateRender','targets','onInterrupt',
    'svgOrigin','transformOrigin','force3D','autoRound','modifyEnd','modifyStart','startAt']);
  const propsOf = (v) => Object.keys(v || {}).filter(k => !RESERVED.has(k) && typeof v[k] !== 'function');
  const n = (v) => (typeof v === 'number' && isFinite(v)) ? v : null;
  const describe = (el) => {
    const tag = (el.tagName || '').toLowerCase();
    const cls = (typeof el.className === 'string' ? el.className : (el.getAttribute && el.getAttribute('class')) || '');
    return {
      sel: el.id ? '#' + el.id : (cls ? cls.trim().split(/\\s+/)[0] : tag),
      tag,
      img: tag === 'img' || tag === 'video' || tag === 'image',
      svg: !!(el.ownerSVGElement || tag === 'path' || tag === 'polyline' || tag === 'line' || tag === 'circle'),
      text: !!el.textContent && !el.querySelector('*') && el.textContent.trim().length > 0,
      w: el.offsetWidth || 0, h: el.offsetHeight || 0,
    };
  };
  const out = { tweens: [] };
  const root = (window.OPENER && window.OPENER.tl) || (window.__timelines && (window.__timelines.main || Object.values(window.__timelines)[0]));
  if (!root) throw new Error('No GSAP timeline found on window.OPENER or window.__timelines');
  const walk = (tl, base, depth) => {
    let child = tl._first;
    while (child) {
      const at = base + (child.startTime ? child.startTime() : 0);
      if (child._first) { walk(child, at, depth + 1); child = child._next; continue; }
      let targets = [];
      try { targets = child.targets ? child.targets() : []; } catch (e) { targets = []; }
      // GSAP keeps the opening state of a .from()/.fromTo() in one of two places.
      const to = child.vars || {};
      const from = (child._startAt && child._startAt.vars) || (typeof to.startAt === 'object' && to.startAt) || {};
      const p = propsOf(to);
      // A staggered reveal is N events wearing one tween's clothes. Read the step
      // and the count so the roll can be written out; GSAP reports the whole spread
      // in duration(), so the per-element ramp has to come from vars.
      const stg = (() => {
        const s = to.stagger;
        if (typeof s === 'number' && isFinite(s)) return Math.abs(s);
        if (s && typeof s === 'object') {
          const each = n(s.each);
          if (each !== null) return Math.abs(each);
          const amount = n(s.amount);
          if (amount !== null && targets.length > 1) return Math.abs(amount) / (targets.length - 1);
        }
        return 0;
      })();
      out.tweens.push({
        at, dur: child.duration ? child.duration() : 0, depth,
        stg, nTargets: targets.length,
        baseDur: n(to.duration) !== null ? n(to.duration) : (child.duration ? child.duration() : 0),
        data: typeof child.data === 'string' ? child.data : (typeof to.data === 'string' ? to.data : ''),
        ease: typeof to.ease === 'string' ? to.ease : '',
        repeat: to.repeat === -1 || (child.repeat && child.repeat() === -1) ? -1 : (to.repeat || 0),
        props: p,
        to: p.reduce((o, k) => { const v = n(to[k]); if (v !== null) o[k] = v; return o; }, {}),
        from: propsOf(from).reduce((o, k) => { const v = n(from[k]); if (v !== null) o[k] = v; return o; }, {}),
        dom: targets.length > 0 && typeof Element !== 'undefined' && targets[0] instanceof Element,
        els: (targets.length > 0 && typeof Element !== 'undefined' && targets[0] instanceof Element)
             ? targets.slice(0, 4).map(describe) : [],
      });
      child = child._next;
    }
  };
  walk(root, 0, 0);
  out.duration = root.duration();
  out.frameEnd = Math.max(0, ...out.tweens.map(t => t.at + t.dur));
  return JSON.stringify(out);
})()`;

/* The rig is one object tweened between absolute positions, so how far the
   camera travelled is only knowable against where it stood before. Walk the rig
   tweens in time order and remember that position. */
const rigState = { x: null, y: null, z: 1 };
function rig(tw) {
  const ox = rigState.x, oy = rigState.y, oz = rigState.z;
  const nx = tw.to.x !== undefined ? tw.to.x : ox;
  const ny = tw.to.y !== undefined ? tw.to.y : oy;
  const nz = tw.to.z !== undefined ? tw.to.z : oz;
  rigState.x = nx; rigState.y = ny; rigState.z = nz;
  if (ox === null || oy === null) return null;                 // the opening set: nothing moved yet
  const pan = Math.hypot(nx - ox, ny - oy);
  const push = oz ? Math.abs(nz / oz - 1) : 0;
  if (pan < 24 && push < 0.02) return null;                    // a hold, or a breath too soft to sound
  if (pan > 700 || push > 0.25)
    return { verb: 'look', asset: pick('whoosh', 'camera'), strength: clamp(0.45 + pan / 4000 + push) };
  return { verb: 'look', asset: pick('whoosh', 'object'), strength: clamp(0.3 + pan / 2600 + push * 2) };
}

/* ---- classification: what moved -> which family -> which take ------------- */
function classify(tw) {
  if (tw.data && byVerb[tw.data]) {
    const asset = byVerb[tw.data];
    const land = asset.family === 'impact' || asset.family === 'stamp';
    return { verb: tw.data, asset, strength: clamp(0.5 + tw.dur / 4), land };
  }
  const P = new Set(tw.props), to = tw.to, from = tw.from;
  const delta = (k) => (from[k] === undefined || to[k] === undefined) ? null : Math.abs(to[k] - from[k]);
  const has = (k) => P.has(k);

  if (!tw.dom) {
    // A tween on a plain object is the camera rig (x/y/z) or a value counter.
    if (has('x') || has('y') || has('z')) return rig(tw);
    // A bare `v` proxy is this skill's motion-blur ramp, not a counter, so counters have to
    // announce themselves by name: tween {count: 0} and it gets a tick, tween {v: 0} and it
    // stays silent. Guessing from a number that means "px of blur" put 45 ticks over a video
    // that had no counters in it at all.
    if (tw.props.some(k => ['count', 'counter', 'total', 'amount', 'number', 'nilai', 'angka'].includes(k)))
      return { verb: 'counter', asset: pick('accent', 'tick'), strength: 0.5 };
    return null;
  }

  const el = tw.els[0] || {};
  const area = (el.w || 0) * (el.h || 0);
  // `.to()` tweens carry no start values, so only the end state is known there.
  const fadesIn = has('opacity') && (to.opacity ?? 0) > 0.5;
  const fadesOut = has('opacity') && (to.opacity ?? 0) <= 0.05;
  const scale = delta('scale') !== null ? delta('scale') : Math.max(delta('scaleX') || 0, delta('scaleY') || 0);
  // A `.to({x:-900})` records no start value, so its end value is the best available estimate
  // of the distance travelled. Right for a fly-on from where the layout put the element,
  // wrong for nudging something that already sits at -900 -- which is what data:'<verb>' and
  // the printed per-family sample are for.
  const travel = Math.hypot(delta('x') ?? (to.x ?? 0), delta('y') ?? (to.y ?? 0));
  const spin = Math.max(delta('rotation') || 0, delta('skewX') || 0, delta('skewY') || 0);
  const drawn = tw.props.some(k => /strokeDash|drawSVG|pathLength/i.test(k));
  const wiped = tw.props.some(k => /clipPath|inset|width|scaleX/i.test(k));

  if (drawn) return { verb: 'draw', asset: tw.dur > 0.55 ? pick('pen', 'marker') : pick('pen', 'thin'),
                      strength: clamp(0.4 + tw.dur / 2) };
  if (fadesIn && scale >= 0.55) {                          // arrives oversized, lands hard
    const heavy = scale >= 1.2 || area > 160000;
    return { verb: 'slam', asset: heavy ? pick('impact', 'heavy') : pick('impact', 'medium'),
             strength: clamp(0.45 + scale / 3), land: true };
  }
  if (spin >= 4 && !fadesOut) return { verb: 'swap', asset: pick('ui', 'toggle'), strength: clamp(0.3 + spin / 40) };
  if (travel >= 120 && !(fadesOut && travel < 400)) {
    const far = travel > 600;
    return { verb: 'fly', asset: far ? pick('whoosh', 'camera') : pick('whoosh', 'object'),
             strength: clamp(0.3 + travel / 2200) };
  }
  // A wipe has no opacity in it at all: a highlight bar scaling from 0, a clip-path opening,
  // a rule growing to width. Checked before the fade rules because such an element never
  // fades -- putting it after "not fading means silent" muted every underline in the video.
  if (wiped && !has('opacity')) {
    if (el.img) return { verb: 'photo', asset: pick('paper', 'cardboard'), strength: 0.55 };
    return { verb: 'label', asset: pick('whoosh', 'thin'), strength: 0.45 };
  }
  if (!fadesIn) return null;
  if (scale >= 0.12) return { verb: 'pop', asset: pick('ui', 'pop'), strength: clamp(0.3 + scale) };
  if (el.text || el.img) return { verb: 'say', asset: el.img ? pick('paper', 'archive') : pick('paper', 'flip'), strength: 0.4 };
  return { verb: 'pop', asset: pick('ui', 'click'), strength: 0.3 };
}

/* ---- headless Chrome, one evaluate, then classify locally ----------------- */
const chrome = spawn(CHROME, [
  '--headless=new', '--disable-gpu', '--hide-scrollbars', '--window-size=1920,1080',
  '--remote-debugging-port=' + PORT, '--remote-debugging-address=127.0.0.1',
  '--user-data-dir=' + PROFILE, '--no-first-run', '--no-default-browser-check', '--mute-audio', PAGE,
], { stdio: 'ignore' });
const cleanup = () => { try { chrome.kill(); } catch {} try { rmSync(PROFILE, { recursive: true, force: true }); } catch {} };
process.on('exit', cleanup);

const jget = async (p) => (await fetch('http://127.0.0.1:' + PORT + p)).json().catch(() => null);
let target = null;
for (let i = 0; i < 160 && !target; i++) {
  await new Promise(r => setTimeout(r, 250));
  const list = await jget('/json/list');
  target = list && list.find(t => t.type === 'page' && /index\.html/.test(t.url));
}
if (!target) { console.error('Chrome tidak memberi target page — cek PAGE dan CHROME.'); process.exit(1); }

const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
const pending = new Map(); let seq = 0;
ws.onmessage = (e) => {
  const m = JSON.parse(e.data);
  if (m.id && pending.has(m.id)) { const p = pending.get(m.id); pending.delete(m.id); m.error ? p.rej(new Error(JSON.stringify(m.error))) : p.res(m.result); }
};
const send = (method, params = {}) => new Promise((res, rej) => { const id = ++seq; pending.set(id, { res, rej }); ws.send(JSON.stringify({ id, method, params })); });
const ev = async (expression) => {
  const r = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true });
  if (r.exceptionDetails) throw new Error((r.exceptionDetails.exception && r.exceptionDetails.exception.description) || r.exceptionDetails.text);
  return r.result.value;
};
await send('Page.enable'); await send('Runtime.enable');
try { await send('Page.setWebLifecycleState', { state: 'active' }); } catch {}
let ready = false;
for (let i = 0; i < 240 && !ready; i++) {
  ready = await ev('!!((window.OPENER && window.OPENER.ready) || (window.__timelines && Object.keys(window.__timelines).length > 0))');
  if (!ready) await new Promise(r => setTimeout(r, 250));
}
if (!ready) { console.error('Timeline (window.OPENER.ready atau window.__timelines) tidak muncul — halaman ini tidak bisa ditambang.'); process.exit(1); }
const probed = JSON.parse(await ev(PROBE));
ws.close(); cleanup();

/* ---- assemble, then prune to a density the ear can follow ----------------- */
const cues = [];
const dropped = { looping: 0, unclassified: 0, beyond: 0, density: 0, masked: 0, budget: 0 };
const unclassified = new Map();          // what the rule table does not recognise yet
const END = Math.min(probed.duration, probed.frameEnd || probed.duration);
for (const tw of probed.tweens.slice().sort((a, b) => a.at - b.at)) {
  if (tw.repeat === -1) { dropped.looping++; continue; }
  const rule = classify(tw);
  const fadesInNow = tw.props.includes('opacity') && (tw.to.opacity ?? 0) > 0.5;
  const isText = tw.dom && !!tw.els[0] && tw.els[0].text;
  /* A word-by-word caption is twelve small events wearing one tween. The eye
     counts them, so the ear has to be offered twelve clicks. Only text rolls
     qualify, and only up to 40 targets: a 200-element stagger is a particle
     field, and one sound per particle is noise, not rhythm. */
  if (WORD_CLICKS && isText && fadesInNow && tw.stg > 0 && tw.nTargets >= 2 && tw.nTargets <= 40) {
    const base = tw.at + tw.baseDur * LAND_AT;
    for (let i = 0; i < tw.nTargets; i++) {
      const at = base + i * tw.stg;
      if (at > END - 0.02 || at < 0) { dropped.beyond++; continue; }
      const asset = pickVerb('word');
      if (!asset) { dropped.unclassified++; continue; }
      cues.push({
        t: round(at), frame: Math.round(at * FPS), family: asset.family, file: asset.file,
        strength: 0.45, motion: round(tw.stg), verb: 'word',
        on: tw.els[0].sel + ' word ' + (i + 1) + '/' + tw.nTargets,
        _rank: rank(asset.family), _texture: true,
      });
    }
    continue;
  }
  // Text that arrives as one block still gets the camera click, just once.
  if (WORD_CLICKS && isText && fadesInNow && rule && ['say', 'label', 'pop'].includes(rule.verb)) {
    const asset = pickVerb('word');
    if (asset) { rule.verb = 'word'; rule.asset = asset; rule.strength = 0.5; }
  }
  if (!rule || !rule.asset) {
    dropped.unclassified++;
    const sig = (tw.dom ? (tw.els[0] && tw.els[0].sel) || 'el' : 'rig') + ' ' + tw.props.slice(0, 4).join(',');
    unclassified.set(sig, (unclassified.get(sig) || 0) + 1);
    continue;
  }
  const at = tw.at + (rule.land && tw.dur > 0.15 ? tw.dur * LAND_AT : 0);
  if (at > END - 0.02 || at < 0) { dropped.beyond++; continue; }
  cues.push({
    t: round(at), frame: Math.round(at * FPS), family: rule.asset.family, file: rule.asset.file,
    strength: round(rule.strength), motion: round(tw.dur), verb: rule.verb,
    on: (tw.dom ? (tw.els[0] && tw.els[0].sel) || 'el' : 'rig') + ' ' + tw.props.slice(0, 4).join(','),
    _rank: rank(rule.asset.family),
  });
}
/* Same-family spacing comes from the bundle's own mix table, so loudness and
   density are tuned in one file. Then masking, then the global budget. */
cues.sort((a, b) => a.t - b.t || a._rank - b._rank);
const kept = [], lastByFamily = {};
let lastEvent = null;
const gap = 1 / MAX_PER_S;
for (const c of cues) {
  const minGap = (mix[c.family] || {}).max_hits_per_s ? 1 / (mix[c.family].max_hits_per_s) : 0.35;
  if (c.t - (lastByFamily[c.family] ?? -9) < minGap) { dropped.density++; continue; }
  // Texture keeps its own beat, and gives its own beat back: a click the ear has been
  // following must neither vanish beside a whoosh nor spend the gap that whoosh needed.
  if (!c._texture && kept.some(k => Math.abs(k.t - c.t) * 1000 < MASK_MS && k._rank <= c._rank)) { dropped.masked++; continue; }
  if (!c._texture && lastEvent !== null && c.t - lastEvent < gap) { dropped.budget++; continue; }
  kept.push(c); lastByFamily[c.family] = c.t;
  if (!c._texture) lastEvent = c.t;
}
const texture = kept.filter(c => c._texture).length;
for (const c of kept) { delete c._rank; delete c._texture; }

const perFamily = {}, perFile = {};
for (const c of kept) {
  perFamily[c.family] = (perFamily[c.family] || 0) + 1;
  perFile[c.file] = (perFile[c.file] || 0) + 1;
}
const secs = Math.max(1, probed.duration);
const sheet = {
  generated: new Date().toISOString().slice(0, 10),
  page: PAGE, bundle: BUNDLE.replace(/\\/g, '/'), fps: FPS,
  duration: round(probed.duration), cuesEnd: kept.length ? kept[kept.length - 1].t : 0,
  landAt: LAND_AT, maskMs: MASK_MS, maxPerSecond: MAX_PER_S, wordClicks: WORD_CLICKS,
  stats: {
    tweens: probed.tweens.length, candidates: cues.length, kept: kept.length,
    perSecond: round(kept.length / secs),
    events: kept.length - texture, eventsPerSecond: round((kept.length - texture) / secs),
    texture, dropped, byFamily: perFamily, byFile: Object.fromEntries(
      Object.entries(perFile).sort((a, b) => b[1] - a[1])),
  },
  cues: kept,
};

const tally = (o) => Object.entries(o).map(([k, v]) => `${k}=${v}`).join(' ');
console.log('\n' + '='.repeat(62));
console.log(`  SFX CUES   ${probed.tweens.length} motion tween -> ${cues.length} kandidat -> ${kept.length} cue`);
console.log(`  density    ${sheet.stats.perSecond} cue/detik selama ${round(probed.duration)}s` +
  (texture ? `   (${sheet.stats.eventsPerSecond} events + ${round(texture / secs)} texture)` : ''));
console.log('='.repeat(62));
console.log('  per family  ' + tally(perFamily));
console.log('  per take    ' + tally(Object.fromEntries(Object.entries(perFile).map(([k, v]) => [k.split('/').pop(), v]))));
console.log('  dropped     ' + tally(dropped));
for (const fam of Object.keys(perFamily)) {
  const sample = kept.filter(c => c.family === fam).slice(0, 3)
    .map(c => `${c.t}s ${c.file.split('/').pop()} s=${c.strength} (${c.verb} @ ${c.on})`);
  console.log(`  ${fam.padEnd(11)} ${sample.join('\n' + ' '.repeat(14))}`);
}
if (argv.includes('--why')) {
  const top = [...unclassified.entries()].sort((a, b) => b[1] - a[1]).slice(0, 12);
  console.log('\n  what stayed silent (prop signatures, most frequent first):');
  for (const [sig, n] of top) console.log(`    ${String(n).padStart(4)}  ${sig}`);
  console.log('  add a rule to classify(), or tag the tween with data:"<verb>" from library.json.\n');
}
if (isDry) { console.log('\n  --dry: tidak ada berkas yang ditulis.\n'); process.exit(0); }
writeFileSync(resolve(OUT), JSON.stringify(sheet, null, 2));
console.log(`\n[OK] ${OUT} — siap untuk scripts/sfx-mix.mjs\n`);
