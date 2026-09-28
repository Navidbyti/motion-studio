/* =========================================================
   SFX MIXER — place a cue sheet on the picture and mux it out.

   Reads assets/sfx-cues.json (see sfx-cues.mjs), drops every take at its
   frame-exact position, rides the gain levels the bundle itself documents, ducks
   what has to duck under the voice, then writes a new MP4 with the video stream
   COPIED. Copying is the point: sound is a post-render decision, so adding or
   retuning SFX never re-renders 8.500 frames, and the picture that was approved
   is the picture that ships.

   Two stages on purpose. Stage 1 renders one stem per family (a plain WAV, so a
   human can listen to "all the whooshes" and judge them alone). Stage 2 mixes
   the stems against the voice and muxes. When the result is wrong, the fix is
   usually one number in assets/sfx/library.json -- but know which stage it lives
   in: --duck, --ceiling and duck_under_speech are stage 2 only, while gain_db is
   baked into the stems, so changing it re-runs stage 1. Either way no video
   frame is ever rendered.

   Usage (from the project folder; ffmpeg on PATH, nothing installed):
     node <skill>/scripts/sfx-mix.mjs --video final.mp4 --vo assets/vo.wav --out final-sfx.mp4
     node <skill>/scripts/sfx-mix.mjs --video final.mp4 --vo assets/vo.wav --dry
     node <skill>/scripts/sfx-mix.mjs --video final.mp4 --vo assets/vo.wav --stems sfx-stems
     --cues assets/sfx-cues.json  --bundle <skill>/assets/sfx
     --duck 0.28  --ceiling -1.0  --pitch-spread 2.5
   ========================================================= */
import { readFileSync, writeFileSync, existsSync, mkdirSync, mkdtempSync, rmSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const argv = process.argv.slice(2);
const opt = (name, dflt) => {
  const i = argv.indexOf('--' + name);
  if (i >= 0 && argv[i + 1] && !argv[i + 1].startsWith('--')) return argv[i + 1];
  const env = process.env[name.toUpperCase().replace(/-/g, '_')];
  return env !== undefined ? env : dflt;
};
const DRY = argv.includes('--dry');
const SKILL_ROOT = dirname(dirname(fileURLToPath(import.meta.url)));

const CUES = resolve(opt('cues', 'assets/sfx-cues.json'));
const BUNDLE = opt('bundle', join(SKILL_ROOT, 'assets', 'sfx'));
const VIDEO = opt('video', '') ? resolve(opt('video')) : '';
const VO = opt('vo', '') ? resolve(opt('vo')) : '';
const OUT = opt('out', '') ? resolve(opt('out')) : '';
const KEEP = opt('stems', '') ? resolve(opt('stems')) : null;
const DUCK = Number(opt('duck', 0.28));         // what the SFX bus keeps while the voice talks
const CEILING = Number(opt('ceiling', -1.0));   // dBFS true-peak ceiling of the finished mix
const SPREAD = Number(opt('pitch-spread', 2.5)); // per-mille rate detune; breaks machine-gun repeats
const CHUNK = 40;                               // asplit caps at 64 outputs; stay under it

const run = (...args) => spawnSync('ffmpeg', ['-hide_banner', ...args], { encoding: 'utf8' });
const dbToLinear = (db) => Math.pow(10, db / 20);
const tally = (o) => Object.entries(o).map(([k, v]) => `${k}=${v}`).join(' ');

if (!VIDEO || !existsSync(VIDEO)) { console.error('Butuh --video <file>. Lihat header scripts/sfx-mix.mjs.'); process.exit(1); }
if (!existsSync(CUES)) { console.error(`Tidak ada ${CUES} — jalankan scripts/sfx-cues.mjs dulu.`); process.exit(1); }

const sheet = JSON.parse(readFileSync(CUES, 'utf8'));
const manifest = JSON.parse(readFileSync(join(BUNDLE, 'manifest.json'), 'utf8'));
const mix = Object.fromEntries(Object.entries(manifest.mix || {}).filter(([, v]) => v && typeof v === 'object'));
const cues = (sheet.cues || []).slice().sort((a, b) => a.t - b.t);
if (!cues.length) { console.error('Sheet cue kosong — tidak ada yang di-mix.'); process.exit(1); }

const durLine = (run('-i', VIDEO).stderr || '').match(/Duration:\s(\d+):(\d+):(\d+\.\d+)/);
const parsed = durLine ? Number(durLine[1]) * 3600 + Number(durLine[2]) * 60 + Number(durLine[3]) : 0;
const DUR = Math.max(parsed, sheet.duration || 0);
if (!DUR) { console.error('Durasi video tidak terbaca.'); process.exit(1); }
const FPS = Number(sheet.fps || 30);
const out = OUT || VIDEO.replace(/\.mp4$/i, '') + '-sfx.mp4';
const work = KEEP ? (mkdirSync(KEEP, { recursive: true }), KEEP) : mkdtempSync(join(tmpdir(), 'mbb_sfxmix_'));

/* ---- stage 1: one stem per family ---------------------------------------- */
const families = {};
for (const c of cues) (families[c.family] = families[c.family] || []).push(c);

const stemInfo = [];
for (const [fam, list] of Object.entries(families)) {
  const stem = join(work, `${fam}.wav`);
  const args = [], filters = [], parts = [];
  /* A filter pad can only be read once, so a take used more than CHUNK times gets
     passed to ffmpeg again as a second input of the same file: decoding a 400 kB
     WAV a few extra times is cheaper than any asplit gymnastics, and asplit caps
     at 64 outputs anyway. */
  for (let ci = 0, inputIdx = 0; ci < list.length; ci += CHUNK) {
    const chunk = list.slice(ci, ci + CHUNK);
    const byFile = {};
    for (const c of chunk) (byFile[c.file] = byFile[c.file] || []).push(c);
    const branch = (src, c, tag) => {
      /* Trust the frame the miner chose. Re-deriving it from c.t rounds twice: the sheet
         stores t to 3 decimals, and a t ending in .x5 multiplied by 30 lands exactly on
         .5, which Math.round tipped one frame past the picture it was cut against. */
      const frame = Number.isFinite(c.frame) ? c.frame : Math.round(c.t * FPS);
      const ms = Math.round(frame / FPS * 1000);                             // snap onto the frame grid
      const gain = ((mix[fam] && typeof mix[fam].gain_db === 'number' ? mix[fam].gain_db : -12)) + (c.strength - 0.5) * 6;
      const seed = ((frame * 2654435761) % 1000) / 1000;                     // stable per cue, not per run order
      const rate = 1 + (seed - 0.5) * 2 * SPREAD / 1000;
      filters.push(`[${src}]asetrate=48000*${rate.toFixed(5)},aresample=48000,` +
        `volume=${dbToLinear(gain).toFixed(4)},adelay=${ms}|${ms}[${tag}]`);
      return tag;
    };
    const branches = [];
    for (const [file, group] of Object.entries(byFile)) {
      filters.push(`[${inputIdx}:a]aformat=sample_rates=48000:channel_layouts=stereo,` +
        (group.length > 1 ? `asplit=${group.length}` + group.map((_, k) => `[r${inputIdx}_${k}]`).join('')
                          : `[r${inputIdx}_0]`));
      args.push('-i', join(BUNDLE, file));
      group.forEach((c, k) => branches.push(branch(`r${inputIdx}_${k}`, c, `b${inputIdx}_${k}`)));
      inputIdx++;
    }
    const part = `p${parts.length}`;
    filters.push(`[${branches.join('][')}]amix=inputs=${branches.length}:normalize=0:duration=longest:dropout_transition=0[${part}]`);
    parts.push(part);
  }
  filters.push(parts.length > 1
    ? `[${parts.join('][')}]amix=inputs=${parts.length}:normalize=0:duration=longest:dropout_transition=0,apad[${fam}]`
    : `[${parts[0]}]apad[${fam}]`);
  const cmd = ['ffmpeg', '-loglevel', 'error', '-y', ...args,
    '-filter_complex', filters.join(';'), '-map', `[${fam}]`, '-t', DUR.toFixed(3),
    '-ar', '48000', '-ac', '2', '-c:a', 'pcm_s16le', stem];
  stemInfo.push({ fam, cues: list.length, duck: !!(mix[fam] && mix[fam].duck_under_speech), stem, cmd });
  if (DRY) continue;
  const r = spawnSync(cmd[0], cmd.slice(1), { encoding: 'utf8' });
  if (r.status !== 0) { console.error(`stem ${fam} gagal:\n` + (r.stderr || '').slice(-2500)); process.exit(1); }
}

/* ---- stage 2: voice + stems, ducked, limited, muxed onto the copied video -- */
/* Input order is decided once, here: [voice] [video] [stem families...]. With no --vo the
   narration is taken from the delivered cut itself, which is the usual case when SFX are
   added after the client approved the picture: the same voice, the same loudness, new bed. */
const videoIdx = VO ? 1 : 0;
const inputs = [...(VO ? ['-i', VO] : []), '-i', VIDEO, ...stemInfo.flatMap(s => ['-i', s.stem])];
const voiceIdx = VO ? 0 : videoIdx;
const f = [`[${voiceIdx}:a]aformat=sample_rates=48000:channel_layouts=stereo,asplit=2[voA][voSide]`];
const stemIdx = stemInfo.map((s, i) => ({ ...s, idx: videoIdx + 1 + i }));
const ducked = stemIdx.filter(s => s.duck), straight = stemIdx.filter(s => !s.duck);
if (ducked.length) {
  f.push(`[${ducked.map(s => `${s.idx}:a`).join('][')}]amix=inputs=${ducked.length}:normalize=0:duration=longest:dropout_transition=0[duckIn]`);
  f.push(`[duckIn][voSide]sidechaincompress=threshold=0.02:ratio=${Math.round(1 / Math.max(0.02, DUCK))}:attack=25:release=340:makeup=1[duckOut]`);
}
const busIn = [...straight.map(s => `${s.idx}:a`), ...(ducked.length ? ['duckOut'] : [])].map(x => `[${x}]`);
if (!busIn.length) { console.error('Tidak ada stem untuk di-mix.'); process.exit(1); }
f.push(`${busIn.join('')}amix=inputs=${busIn.length}:normalize=0:duration=longest:dropout_transition=0[sfx]`);
f.push(`[voA][sfx]amix=inputs=2:normalize=0:duration=longest:dropout_transition=0,` +
  `apad,alimiter=limit=${dbToLinear(CEILING).toFixed(4)}:attack=3:release=60,` +
  `aformat=sample_rates=48000:channel_layouts=stereo[aout]`);

const final = ['ffmpeg', '-loglevel', 'error', '-y', ...inputs,
  '-filter_complex', f.join(';'), '-map', `${videoIdx}:v`, '-c:v', 'copy',
  '-map', '[aout]', '-c:a', 'aac', '-b:a', '256k', '-t', DUR.toFixed(3), '-movflags', '+faststart', out];
if (DRY) {
  for (const s of stemInfo) console.log(`\n# stem ${s.fam} — ${s.cues} cue${s.duck ? ' (duck)' : ''}\n` + s.cmd.join(' '));
  console.log('\n# mix + mux, video stream disalin\n' + final.join(' '));
  console.log(`\n(dry: ${cues.length} cue, ${stemInfo.length} bus, voice ${VO ? 'dari --vo' : 'dari track video'} — tidak ada berkas ditulis)\n`);
  if (!KEEP) rmSync(work, { recursive: true, force: true });
  process.exit(0);
}
const r2 = spawnSync(final[0], final.slice(1), { encoding: 'utf8' });
if (!KEEP) rmSync(work, { recursive: true, force: true });
if (r2.status !== 0) { console.error('mix gagal:\n' + (r2.stderr || '').slice(-3000)); process.exit(1); }

/* ---- measure: "terdengar oke" bukan pemeriksaan --------------------------- */
/* ffmpeg mencetak blok Summary lebih dari satu kali (satu per inisialisasi
   filter, yang pertama selalu kosong), jadi ambil kejadian TERAKHIR.
   peak=true wajib untuk baris "Peak:"; tanpa itu true peak tidak pernah ada. */
const m = run('-i', out, '-map', '0:a', '-af', 'ebur128=framelog=quiet:peak=true', '-f', 'null', '-');
const g = (re) => { let v; for (const x of (m.stderr || '').matchAll(new RegExp(re.source, 'g'))) v = x[1]; return v; };
const loud = { lufs: g(/I:\s+(-?\d+\.\d)\s+LUFS/), lra: g(/LRA:\s+(-?\d+\.\d)\s+LU/), tp: g(/Peak:\s+(-?\d+\.\d)\s+dBFS/) };

console.log('\n' + '='.repeat(62));
console.log(`  SFX MIX    ${cues.length} cue -> ${out}`);
console.log('='.repeat(62));
console.log(`  stems      ${tally(Object.fromEntries(stemInfo.map(s => [s.fam, s.cues])))}`);
console.log(`  ducking    ${ducked.length ? ducked.map(s => s.fam).join(', ') + ` turun saat ${VO ? 'VO' : 'narasi di trek video'} bicara` : 'tidak ada family yang di-duck'}`);
console.log(`  loudness   ${loud.lufs ?? '?'} LUFS   LRA ${loud.lra ?? '?'} LU   true peak ${loud.tp ?? '?'} dBFS (target ${CEILING})`);
console.log(`  picture    stream video disalin: DUR ${DUR.toFixed(2)}s tetap, tidak ada render ulang`);
const notes = [];
/* Limiter menahan PCM di --ceiling SEBELUM encode; AAC menambah overshoot
   antar-sample ~0.5 dB di atasnya. Jadi angka di atas ceiling itu normal —
   yang berbahaya hanya kalau mendekati 0 dBFS (klip digital). */
if (Number(loud.tp) > -0.1) notes.push(`true peak ${loud.tp} dBFS menempel 0 — mix terpotong di speaker; turunkan gain_db di library.json atau perketat --ceiling.`);
if (Number(loud.lufs) > -13.5) notes.push('mix lebih keras dari narasi sendiri: SFX menutupi suara, turunkan gain_db di library.json.');
if (Number(loud.lufs) < -18.5) notes.push('mix sangat pelan: naikkan gain_db family utama, atau perkecil --duck.');
if (!loud.lufs) notes.push('pengukuran loudness gagal — cek manual: ffmpeg -i "' + out + '" -map 0:a -af ebur128=peak=true -f null -');
notes.forEach(n => console.log('  ! ' + n));
if (KEEP) console.log(`  stems      audition per family di ${KEEP}/`);
/* out sudah berakhir dengan "-sfx.mp4", jadi buang ekstensi saja — "-sfx-mix.json",
   bukan "-sfx-sfx-mix.json". */
writeFileSync(out.replace(/\.mp4$/i, '') + '-mix.json', JSON.stringify({
  out, video: VIDEO, vo: VO, cues: cues.length, duration: DUR, fps: FPS, ceiling_dbfs: CEILING,
  duck_factor: DUCK, pitch_spread_permille: SPREAD, voice: VO || VIDEO + ' (track audio)',
  stems: stemInfo.map(({ stem, cmd, ...s }) => s),
  measured: { lufs: loud.lufs ?? null, lra: loud.lra ?? null, true_peak_dbfs: loud.tp ?? null },
  generated: new Date().toISOString(),
}, null, 2));
console.log('');
