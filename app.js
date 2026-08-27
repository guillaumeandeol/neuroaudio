/* Vega — CRM (Coordinate Response Measure) speech-in-noise test
   Prototype web app. Based on:
   Isnard, Chastres & Andéol (2024), "French version of the coordinate
   response measure corpus and its validation on a speech-on-speech task",
   JASA Express Letters 4, 075203.
*/

const COLORS = ["Bleu", "Jaune", "Rouge", "Vert"];
const NUMBERS = [1,2,3,4,5,6,7,8];

// RMS reference levels (16-bit PCM scale) measured once at build time on the
// source corpus / generated noise. The CRM corpus is already RMS-normalized
// (Isnard et al. 2024), so a single fixed reference per source is accurate
// enough to set SNR by gain — no need to decode each file at runtime.
const TARGET_RMS_REF = 2185.6;
const NOISE_RMS_REF = 2999.6;
const MAIN_SNR = -9;

// Clinical classification thresholds, calibrated for a 32-trial main test.
const NUM_TRIALS_FOR_CLASSIFICATION = 32;
const NORMAL_MIN_CORRECT = 19;   // >= this many correct (out of 32) => normal
const ABNORMAL_MAX_CORRECT = 6;  // <= this many correct (out of 32) => abnormal (i.e. "< 7")
const SNR50_ABNORMAL_THRESHOLD = -8.1; // confirmed abnormal if estimated SNR-50 >= this

const NOISE_FILES = {
  corpus: "noise/corpus_ssn.mp3",
  standard: "noise/standard_ssn.mp3",
};

const state = {
  manifest: null,
  byCallsign: {},          // callsign -> array of manifest entries
  config: null,
  trials: [],               // planned/executed trial records (current phase)
  trialIndex: 0,
  practiceRemaining: 0,
  audioCtx: null,
  audioUnlocked: false,
  noiseEl: null,
  noiseNode: null,
  noiseGain: null,
  masterGain: null,
  currentTrial: null,
  trialStartTime: null,
  replayUsed: false,
  phases: [],              // [{key,label,snr}], appended to if confirmation needed
  phaseIdx: 0,
  results: [],             // results for the current phase only
  allResults: [],          // results across every phase, for CSV/table export
  phaseHistory: [],        // completed phase summaries {key,label,snr,correct,total,pct}
  finalConclusion: null,
  snr50: null,
};

// ---------------------------------------------------------------- helpers

function $(sel) { return document.querySelector(sel); }
function $all(sel) { return Array.from(document.querySelectorAll(sel)); }

function showScreen(id) {
  $all(".screen").forEach(s => s.classList.remove("active"));
  $(`#${id}`).classList.add("active");
}

function dbToGain(db) { return Math.pow(10, db / 20); }

// Résolution d'une ressource audio. Dans la version dossier, c'est un chemin
// relatif ; dans le build autonome (crm_standalone.html), window.EMBEDDED_AUDIO
// contient les mêmes fichiers en data: URI et l'app fonctionne à l'identique.
function audioUrl(rel) {
  const emb = window.EMBEDDED_AUDIO;
  return (emb && emb[rel]) ? emb[rel] : `audio/${rel}`;
}


function shuffle(arr) {
  const a = arr.slice();
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

function choice(arr) { return arr[Math.floor(Math.random() * arr.length)]; }

// ---------------------------------------------------------------- loading
//
// Audio is played through plain <audio> elements (routed via
// createMediaElementSource into the Web Audio graph for gain control),
// rather than fetch()+decodeAudioData. This lets the app run directly from
// a double-clicked index.html (file://) with no local server required,
// since loading a local media resource via a tag isn't subject to the
// fetch/XHR same-origin restriction that blocks file:// JSON/array-buffer
// fetches.

function loadManifest() {
  state.manifest = window.CRM_MANIFEST || [];
  state.byCallsign = {};
  for (const e of state.manifest) {
    (state.byCallsign[e.callsign] ||= []).push(e);
  }
}

async function ensureAudioCtx() {
  if (!state.audioCtx) {
    state.audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    state.masterGain = state.audioCtx.createGain();
    state.masterGain.gain.value = 0.7;
    state.masterGain.connect(state.audioCtx.destination);
  }
  if (state.audioCtx.state === "suspended") await state.audioCtx.resume();
}

async function startNoiseLoop(noiseType) {
  if (state.noiseNode) return; // already running
  const file = NOISE_FILES[noiseType] || NOISE_FILES.corpus;
  const el = new Audio(audioUrl(file));
  el.loop = true;
  el.crossOrigin = "anonymous";
  const src = state.audioCtx.createMediaElementSource(el);
  const g = state.audioCtx.createGain();
  g.gain.value = 1.0; // reference level, corresponds to NOISE_RMS_REF
  src.connect(g).connect(state.masterGain);
  await el.play();
  state.noiseEl = el;
  state.noiseNode = src;
  state.noiseGain = g;
}

function stopNoiseLoop() {
  if (state.noiseNode) {
    try { state.noiseEl.pause(); } catch (e) {}
    state.noiseNode.disconnect();
    state.noiseGain.disconnect();
    state.noiseEl = null;
    state.noiseNode = null;
    state.noiseGain = null;
  }
}

// ---------------------------------------------------------------- trial generation

function buildTrialList(numTrials) {
  return new Array(numTrials).fill(null);
}

function pickStimulus(callsign) {
  const pool = state.byCallsign[callsign];
  return choice(pool);
}

// ---------------------------------------------------------------- playback of a trial

function trialGain(snr) {
  return (NOISE_RMS_REF * state.noiseGain.gain.value / TARGET_RMS_REF) * dbToGain(snr);
}

function playFile(relFile, gainValue) {
  const el = new Audio(audioUrl(relFile));
  el.crossOrigin = "anonymous";
  const src = state.audioCtx.createMediaElementSource(el);
  const g = state.audioCtx.createGain();
  g.gain.value = gainValue;
  src.connect(g).connect(state.masterGain);
  el.addEventListener("ended", () => { src.disconnect(); g.disconnect(); });
  el.play().catch(err => console.error("lecture audio impossible:", err));
  return { el, src, gainNode: g };
}

async function playTrial(snr) {
  const entry = pickStimulus(state.config.callsign);
  const playback = playFile(entry.file, trialGain(snr));
  state.currentTrial = { entry, snr, ...playback };
  return entry;
}

function replayCurrent() {
  if (!state.currentTrial || state.replayUsed) return;
  const { entry, snr } = state.currentTrial;
  playFile(entry.file, trialGain(snr));
  state.replayUsed = true;
  $("#btnReplay").style.display = "none";
}

// ---------------------------------------------------------------- grid UI

function buildGrid() {
  const grid = $("#grid");
  grid.innerHTML = "";
  for (const color of COLORS) {
    for (const num of NUMBERS) {
      const btn = document.createElement("button");
      btn.className = `grid-btn ${color}`;
      btn.textContent = num;
      btn.dataset.color = color;
      btn.dataset.number = num;
      btn.addEventListener("click", onResponse);
      grid.appendChild(btn);
    }
  }
}

function setGridEnabled(enabled) {
  $all(".grid-btn").forEach(b => { b.disabled = !enabled; b.classList.remove("correct", "incorrect"); });
}

function updateLiveScore() {
  const el = $("#liveScore");
  if (!el) return;
  const correct = state.results.filter(r => r.correctBoth).length;
  const answered = state.results.length;
  const total = state.trials.length;
  el.innerHTML = state.pendingIsPractice
    ? ""
    : `Bonnes réponses : <strong>${correct}</strong> / ${answered} (sur ${total} essais)`;
}

// ---------------------------------------------------------------- trial flow

async function nextTrial() {
  state.replayUsed = false;
  $("#btnReplay").style.display = "none";
  setGridEnabled(false);

  const isPractice = state.practiceRemaining > 0;
  const phase = state.phases[state.phaseIdx];
  $("#phaseLabel").textContent = isPractice ? "Entraînement" : `${phase.label} (SNR ${phase.snr} dB)`;

  const snr = phase.snr;
  if (!isPractice && state.trialIndex >= state.trials.length) { onPhaseComplete(); return; }

  $("#snrLabel").textContent = `SNR : ${snr.toFixed(1)} dB`;
  $("#callsignReminder").textContent = state.config.callsign;

  $("#trialCounter").textContent = isPractice
    ? `Entraînement ${state.practiceTotal - state.practiceRemaining + 1}/${state.practiceTotal}`
    : `Essai ${state.trialIndex + 1} / ${state.trials.length}`;

  state.pendingSnr = snr;
  state.pendingIsPractice = isPractice;
  updateLiveScore();

  if (state.audioUnlocked) {
    // Audio already unlocked by an earlier click this session — present the
    // next sentence automatically, no button press needed.
    await playCurrentTrial();
    $("#btnPlay").style.display = "none";
  } else {
    $("#btnPlay").style.display = "inline-block";
    $("#btnPlay").disabled = false;
    $("#btnPlay").textContent = "▶ Écouter la phrase";
  }
}

async function playCurrentTrial() {
  await ensureAudioCtx();
  await startNoiseLoop(state.config.noiseType);
  const entry = await playTrial(state.pendingSnr);
  state.trialStartTime = performance.now();
  setGridEnabled(true);
  if (!state.pendingIsPractice) $("#btnReplay").style.display = "inline-block";
  return entry;
}

async function onPlayClicked() {
  $("#btnPlay").disabled = true;
  state.audioUnlocked = true;
  await playCurrentTrial();
  $("#btnPlay").style.display = "none";
}

function onResponse(e) {
  if (!state.currentTrial) return;
  const btn = e.currentTarget;
  const respColor = btn.dataset.color;
  const respNumber = parseInt(btn.dataset.number, 10);
  const rt = performance.now() - state.trialStartTime;

  const entry = state.currentTrial.entry;
  const correctColor = respColor === entry.color;
  const correctNumber = respNumber === entry.number;
  const correctBoth = correctColor && correctNumber;

  btn.classList.add(correctBoth ? "correct" : "incorrect");
  setGridEnabled(false);

  if (!state.pendingIsPractice) {
    const phase = state.phases[state.phaseIdx];
    const record = {
      phase: phase.label,
      trial: state.trialIndex + 1,
      snr: state.pendingSnr,
      talker: entry.talker,
      sex: entry.sex,
      callsign: entry.callsign,
      targetColor: entry.color,
      targetNumber: entry.number,
      respColor, respNumber,
      correctColor, correctNumber, correctBoth,
      rt_ms: Math.round(rt),
    };
    state.results.push(record);
    state.allResults.push(record);
    state.trialIndex++;
  } else {
    state.practiceRemaining--;
  }
  updateLiveScore();

  setTimeout(() => {
    const finished = state.pendingIsPractice ? false : state.trialIndex >= state.trials.length;
    if (finished) onPhaseComplete();
    else nextTrial();
  }, 1000);
}

// ---------------------------------------------------------------- phase / classification logic

function summarizePhase() {
  const phase = state.phases[state.phaseIdx];
  const correct = state.results.filter(r => r.correctBoth).length;
  const total = state.results.length;
  const pct = total ? 100 * correct / total : 0;
  return { key: phase.key, label: phase.label, snr: phase.snr, correct, total, pct };
}

function classifyMain(correct, numTrials) {
  if (numTrials !== NUM_TRIALS_FOR_CLASSIFICATION) return null; // thresholds only valid for 32 essais
  if (correct >= NORMAL_MIN_CORRECT) return "normal";
  if (correct <= ABNORMAL_MAX_CORRECT) return "anormal";
  return "ambigu";
}

function linearRegression(points) {
  const n = points.length;
  const sumX = points.reduce((s, p) => s + p.x, 0);
  const sumY = points.reduce((s, p) => s + p.y, 0);
  const sumXY = points.reduce((s, p) => s + p.x * p.y, 0);
  const sumXX = points.reduce((s, p) => s + p.x * p.x, 0);
  const denom = n * sumXX - sumX * sumX;
  if (denom === 0) return null;
  const slope = (n * sumXY - sumX * sumY) / denom;
  const intercept = (sumY - slope * sumX) / n;
  return { slope, intercept };
}

function computeConfirmation() {
  const points = state.phaseHistory
    .filter(p => ["main", "c12", "c6"].includes(p.key))
    .map(p => ({ x: p.snr, y: p.pct }));
  const reg = linearRegression(points);
  if (!reg || reg.slope === 0) {
    state.snr50 = null;
    state.finalConclusion = "indetermine";
    return;
  }
  const snr50 = (50 - reg.intercept) / reg.slope;
  state.snr50 = snr50;
  state.finalConclusion = snr50 >= SNR50_ABNORMAL_THRESHOLD ? "anormal_confirme" : "normal_confirme";
}

function beginPhase(phaseIdx, practiceTrials) {
  state.phaseIdx = phaseIdx;
  state.results = [];
  state.trialIndex = 0;
  state.practiceRemaining = practiceTrials || 0;
  state.practiceTotal = practiceTrials || 0;
  state.trials = buildTrialList(state.config.numTrials);
  showScreen("screen-test");
  nextTrial();
}

function onPhaseComplete() {
  const summary = summarizePhase();
  state.phaseHistory.push(summary);
  const phase = state.phases[state.phaseIdx];

  if (phase.key === "main") {
    const classification = classifyMain(summary.correct, state.config.numTrials);
    state.finalConclusion = classification;
    if (classification === "ambigu") {
      state.phases.push({ key: "c12", label: "Confirmation", snr: -12 });
      state.phases.push({ key: "c6", label: "Confirmation", snr: -6 });
      beginPhase(state.phaseIdx + 1, 0);
      return;
    }
    finishTest();
    return;
  }

  // confirmation phase (c12 or c6)
  if (state.phaseIdx + 1 < state.phases.length) {
    beginPhase(state.phaseIdx + 1, 0);
    return;
  }
  computeConfirmation();
  finishTest();
}

// ---------------------------------------------------------------- results

function finishTest() {
  stopNoiseLoop();
  showScreen("screen-results");
  renderResults();
}

const CONCLUSION_TEXT = {
  normal: { label: "Normal", detail: `Score suffisant au SNR de ${MAIN_SNR} dB (≥ ${NORMAL_MIN_CORRECT} bonnes réponses sur ${NUM_TRIALS_FOR_CLASSIFICATION}) — aucun test complémentaire nécessaire.` },
  anormal: { label: "Anormal", detail: `Score insuffisant au SNR de ${MAIN_SNR} dB (≤ ${ABNORMAL_MAX_CORRECT} bonnes réponses sur ${NUM_TRIALS_FOR_CLASSIFICATION}) — aucun test complémentaire nécessaire.` },
  anormal_confirme: { label: "Anormal (confirmé)", detail: "" },
  normal_confirme: { label: "Normal (confirmé)", detail: "" },
  indetermine: { label: "Indéterminé", detail: "La relation score/SNR obtenue sur les trois essais ne permet pas d'estimer un seuil à 50 % — envisager de recommencer le test." },
};

function renderResults() {
  const summaryEl = $("#resultsSummary");
  const conclusionEl = $("#resultsConclusion");

  const classification = state.finalConclusion;
  const numTrials = state.config.numTrials;

  if (!classification) {
    conclusionEl.innerHTML = `<p class="hint">La conclusion clinique automatique nécessite exactement ${NUM_TRIALS_FOR_CLASSIFICATION} essais au test principal (ce test en comptait ${numTrials}). Seuls les scores bruts sont affichés ci-dessous.</p>`;
  } else {
    const c = CONCLUSION_TEXT[classification];
    let detail = c.detail;
    if (classification === "anormal_confirme" || classification === "normal_confirme") {
      detail = `SNR à 50 % de réussite estimé à ${state.snr50.toFixed(1)} dB à partir des trois essais (-12, -9 et -6 dB) — seuil de décision : ${SNR50_ABNORMAL_THRESHOLD} dB.`;
    }
    conclusionEl.innerHTML = `
      <p style="font-size:1.4rem;font-weight:700;margin:0 0 6px">${c.label}</p>
      <p class="hint" style="margin:0">${detail}</p>
    `;
  }

  const rows = state.phaseHistory.map(p => ({ snr: p.snr, pct: p.pct, n: p.total, label: p.label }));
  summaryEl.innerHTML = `
    <h2>Score par phase de test</h2>
    <table style="width:100%">
      <tr><th style="text-align:left">Phase</th><th style="text-align:left">SNR (dB)</th><th style="text-align:left">% correct</th><th style="text-align:left">n</th></tr>
      ${rows.map(r => `<tr><td>${r.label}</td><td>${r.snr.toFixed(1)}</td><td>${r.pct.toFixed(0)}%</td><td>${r.n}</td></tr>`).join("")}
    </table>
  `;
  drawChart(rows);

  renderTable(state.allResults);
}

function drawChart(rows) {
  const canvas = $("#resultsChart");
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  if (!rows.length) return;
  const pad = 40;
  const w = canvas.width - pad * 2;
  const h = canvas.height - pad * 2;
  const minSnr = Math.min(...rows.map(r => r.snr));
  const maxSnr = Math.max(...rows.map(r => r.snr));
  const xFor = snr => pad + (maxSnr === minSnr ? w / 2 : (snr - minSnr) / (maxSnr - minSnr) * w);
  const yFor = pct => pad + h - (pct / 100) * h;

  ctx.strokeStyle = "#2a3550";
  ctx.beginPath();
  ctx.moveTo(pad, pad); ctx.lineTo(pad, pad + h); ctx.lineTo(pad + w, pad + h);
  ctx.stroke();
  ctx.fillStyle = "#9aa7c2";
  ctx.font = "12px sans-serif";
  ctx.fillText("100%", 4, yFor(100) + 4);
  ctx.fillText("50%", 8, yFor(50) + 4);
  ctx.fillText("0%", 12, yFor(0) + 4);
  ctx.fillText(`${minSnr.toFixed(0)} dB`, pad - 10, pad + h + 18);
  ctx.fillText(`${maxSnr.toFixed(0)} dB`, pad + w - 20, pad + h + 18);

  ctx.strokeStyle = "#4f8cff";
  ctx.lineWidth = 2;
  ctx.beginPath();
  rows.forEach((r, i) => {
    const x = xFor(r.snr), y = yFor(r.pct);
    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  });
  ctx.stroke();
  ctx.fillStyle = "#4f8cff";
  rows.forEach(r => {
    ctx.beginPath();
    ctx.arc(xFor(r.snr), yFor(r.pct), 4, 0, Math.PI * 2);
    ctx.fill();
  });
}

function renderTable(results) {
  const table = $("#resultsTable");
  if (!results.length) { table.innerHTML = ""; return; }
  const cols = ["phase","trial","snr","talker","sex","callsign","targetColor","targetNumber","respColor","respNumber","correctBoth","rt_ms"];
  table.innerHTML = `
    <tr>${cols.map(c => `<th>${c}</th>`).join("")}</tr>
    ${results.map(r => `<tr>${cols.map(c => `<td>${r[c]}</td>`).join("")}</tr>`).join("")}
  `;
}

function exportCsv() {
  const results = state.allResults;
  if (!results.length) return;
  const cols = Object.keys(results[0]);
  const lines = [cols.join(",")];
  for (const r of results) lines.push(cols.map(c => r[c]).join(","));
  const blob = new Blob([lines.join("\n")], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  const pid = state.config.participantId || "anonyme";
  const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-");
  a.href = url;
  a.download = `crm_${pid}_${stamp}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

// ---------------------------------------------------------------- setup screen wiring

function readConfig() {
  return {
    participantId: $("#participantId").value.trim(),
    callsign: $("#targetCallsign").value,
    noiseType: $all('input[name="noiseType"]').find(r => r.checked).value,
    numTrials: parseInt($("#numTrials").value, 10),
    practiceTrials: parseInt($("#practiceTrials").value, 10),
  };
}

async function startSession() {
  const cfg = readConfig();
  if (!cfg.numTrials || cfg.numTrials < 1) {
    alert("Indiquez un nombre d'essais valide.");
    return;
  }
  state.config = cfg;
  state.audioUnlocked = false;
  state.allResults = [];
  state.phaseHistory = [];
  state.finalConclusion = null;
  state.snr50 = null;
  state.phases = [{ key: "main", label: "Test principal", snr: MAIN_SNR }];

  buildGrid();
  beginPhase(0, cfg.practiceTrials);
}

function previewNoise(noiseType) {
  const el = new Audio(audioUrl(NOISE_FILES[noiseType]));
  el.play().catch(err => console.error("lecture impossible:", err));
  setTimeout(() => el.pause(), 3000);
}

function wireSetupScreen() {
  $("#btnPreviewCorpus").addEventListener("click", () => previewNoise("corpus"));
  $("#btnPreviewStandard").addEventListener("click", () => previewNoise("standard"));

  $("#btnStart").addEventListener("click", startSession);
  $("#btnPlay").addEventListener("click", onPlayClicked);
  $("#btnReplay").addEventListener("click", replayCurrent);
  $("#btnStop").addEventListener("click", () => { finishTest(); });
  $("#btnExport").addEventListener("click", exportCsv);
  $("#btnRestart").addEventListener("click", () => {
    stopNoiseLoop();
    showScreen("screen-setup");
  });
}

// ---------------------------------------------------------------- boot

(function init() {
  wireSetupScreen();
  loadManifest();
  if (!state.manifest.length) {
    alert("Le corpus audio (audio/manifest.js) n'a pas pu être chargé. Vérifiez que le dossier webapp/ est complet.");
  }
})();

/* ================================================================================
   VÉRIFICATION DU SNR
   Écoute séparée du bruit et de la voix, aux niveaux exacts du test, puis mesure
   du rapport signal/bruit réellement produit par la chaîne audio.

   Deux mesures indépendantes sont proposées :
   1. Mesure "à la lecture" : un tap (ScriptProcessor) est branché juste après le
      gain de chaque source, donc sur le signal réellement envoyé à la sortie.
      Fonctionne aussi en file://.
   2. Analyse "hors-ligne" : les fichiers sont décodés (fetch + decodeAudioData) et
      leur RMS exact est comparé aux constantes TARGET_RMS_REF / NOISE_RMS_REF sur
      lesquelles repose tout le calcul de SNR. Nécessite un serveur HTTP local.
   ================================================================================ */

const VERIF_ACTIVE_THRESHOLD_DB = -30; // trames à moins de 30 dB du max = "parole active"
const VERIF_TOLERANCE_DB = 0.5;        // écart accepté entre SNR mesuré et SNR cible
const METER_BLOCK = 1024;              // ~23 ms à 44,1 kHz

const verif = {
  entry: null,
  entryDuration: null,
  playing: null,
  last: { noise: null, voice: null },
  decoded: {},
};

function dbFS(x) { return x > 0 ? 20 * Math.log10(x) : -Infinity; }
function fmtDbFS(x) { return Number.isFinite(x) ? `${x.toFixed(1)} dBFS` : "—"; }
function signed(x, d = 1) { return `${x >= 0 ? "+" : ""}${x.toFixed(d)}`; }

// Gain appliqué à la voix pour obtenir le SNR demandé, avec le bruit à son gain
// de référence (1.0) — strictement la même formule que trialGain() pendant le test.
function verifVoiceGain(snr) { return (NOISE_RMS_REF / TARGET_RMS_REF) * dbToGain(snr); }

function currentNoiseType() {
  const r = $all('input[name="noiseType"]').find(x => x.checked);
  return r ? r.value : "corpus";
}

// ---------------------------------------------------------------- mesure temps réel

function makeMeter(ctx) {
  if (!ctx.createScriptProcessor) return null;
  const node = ctx.createScriptProcessor(METER_BLOCK, 1, 1);
  const sink = ctx.createGain();
  sink.gain.value = 0; // le tap ne doit rien ajouter au son entendu
  const blocks = [];
  let sum = 0, count = 0, peak = 0;
  node.onaudioprocess = (e) => {
    const d = e.inputBuffer.getChannelData(0);
    let s = 0;
    for (let i = 0; i < d.length; i++) {
      const v = d[i];
      s += v * v;
      const a = v < 0 ? -v : v;
      if (a > peak) peak = a;
    }
    sum += s; count += d.length;
    blocks.push(Math.sqrt(s / d.length));
  };
  node.connect(sink);
  sink.connect(ctx.destination);
  return {
    node,
    result() {
      const rms = count ? Math.sqrt(sum / count) : 0;
      let active = rms;
      if (blocks.length) {
        let max = 0;
        for (const b of blocks) if (b > max) max = b;
        const thr = max * Math.pow(10, VERIF_ACTIVE_THRESHOLD_DB / 20);
        let s2 = 0, k = 0;
        for (const b of blocks) if (b >= thr) { s2 += b * b; k++; }
        if (k) active = Math.sqrt(s2 / k);
      }
      return { rms, active, peak, seconds: count / ctx.sampleRate };
    },
    dispose() {
      node.onaudioprocess = null;
      try { node.disconnect(); sink.disconnect(); } catch (e) {}
    },
  };
}

function verifChain(url, gainValue, loop) {
  const ctx = state.audioCtx;
  const el = new Audio(url);
  el.crossOrigin = "anonymous";
  el.loop = !!loop;
  const src = ctx.createMediaElementSource(el);
  const g = ctx.createGain();
  g.gain.value = gainValue;
  src.connect(g);
  g.connect(state.masterGain);          // audible
  const meter = makeMeter(ctx);
  if (meter) g.connect(meter.node);     // mesuré, après gain
  return {
    el, src, g, meter,
    stop() {
      try { el.pause(); } catch (e) {}
      try { src.disconnect(); g.disconnect(); } catch (e) {}
      if (meter) meter.dispose();
    },
  };
}

// ---------------------------------------------------------------- stimulus

function verifPickStimulus() {
  const callsign = $("#targetCallsign") ? $("#targetCallsign").value : null;
  const pool = (callsign && state.byCallsign[callsign]) || state.manifest;
  if (!pool || !pool.length) return;
  verif.entry = choice(pool);
  verif.entryDuration = null;
  const e = verif.entry;
  $("#verifStimulus").innerHTML =
    `Phrase de test : <strong>${e.callsign} ${e.color} ${e.number}</strong> <span class="mono">${e.file}</span>`;
  const probe = new Audio(audioUrl(e.file));
  probe.addEventListener("loadedmetadata", () => {
    verif.entryDuration = probe.duration;
    $("#verifStimulus").innerHTML =
      `Phrase de test : <strong>${e.callsign} ${e.color} ${e.number}</strong> <span class="mono">${e.file}</span> — ${probe.duration.toFixed(2)} s`;
  });
}

// ---------------------------------------------------------------- lecture

function verifStopPlayback() {
  if (!verif.playing) return;
  clearTimeout(verif.playing.timer);
  for (const c of Object.values(verif.playing.chains)) c.stop();
  verif.playing = null;
  verifSetPlayingUI(false);
}

function verifSetPlayingUI(on) {
  const stop = $("#btnVerifStop");
  if (stop) stop.style.visibility = on ? "visible" : "hidden";
}

async function verifPlay(mode) {
  await ensureAudioCtx();
  stopNoiseLoop();          // pas de collision avec la boucle de bruit du test
  verifStopPlayback();
  if (!verif.entry) verifPickStimulus();
  if (!verif.entry) { alert("Corpus audio indisponible."); return; }

  const snr = parseFloat($("#verifSnr").value);
  if (!Number.isFinite(snr)) { alert("Indiquez un SNR valide."); return; }
  const noiseType = currentNoiseType();

  const chains = {};
  if (mode === "noise" || mode === "mix") {
    chains.noise = verifChain(audioUrl(NOISE_FILES[noiseType]), 1.0, true);
  }
  if (mode === "voice" || mode === "mix") {
    chains.voice = verifChain(audioUrl(verif.entry.file), verifVoiceGain(snr), false);
  }
  verif.playing = { chains, mode, snr, noiseType, entry: verif.entry };
  verifSetPlayingUI(true);

  if (chains.voice) chains.voice.el.addEventListener("ended", () => verifFinish());

  await Promise.all(Object.values(chains).map(c =>
    c.el.play().catch(err => console.error("lecture impossible:", err))));

  if (mode === "noise") {
    // le bruit seul est joué exactement le temps d'une phrase, pour que la
    // fenêtre de mesure soit la même que celle de la voix
    const dur = verif.entryDuration || 2.0;
    verif.playing.timer = setTimeout(() => verifFinish(), dur * 1000 + 80);
  }
}

function verifFinish() {
  const p = verif.playing;
  if (!p) return;
  const res = {};
  if (p.chains.noise && p.chains.noise.meter) res.noise = p.chains.noise.meter.result();
  if (p.chains.voice && p.chains.voice.meter) res.voice = p.chains.voice.meter.result();
  verifStopPlayback();

  if (res.noise) verif.last.noise = Object.assign(res.noise, { snr: p.snr, noiseType: p.noiseType, mode: p.mode });
  if (res.voice) verif.last.voice = Object.assign(res.voice, { snr: p.snr, entry: p.entry, mode: p.mode });
  renderVerifMeasure();
}

// ---------------------------------------------------------------- affichage mesure

function renderVerifMeasure() {
  const el = $("#verifMeasure");
  const n = verif.last.noise, v = verif.last.voice;
  if (!n && !v) { el.innerHTML = ""; return; }

  const rows = [];
  if (n) rows.push([`Bruit (${n.noiseType}) — RMS sur ${n.seconds.toFixed(2)} s`, fmtDbFS(dbFS(n.rms))]);
  if (v) {
    rows.push([`Voix — RMS sur la phrase entière (${v.seconds.toFixed(2)} s)`, fmtDbFS(dbFS(v.rms))]);
    rows.push([`Voix — RMS pendant la parole active`, fmtDbFS(dbFS(v.active))]);
  }

  let verdict = "";
  if (n && v) {
    const measured = dbFS(v.rms) - dbFS(n.rms);
    const activeSnr = dbFS(v.active) - dbFS(n.rms);
    const target = v.snr;
    const delta = measured - target;
    const ok = Math.abs(delta) <= VERIF_TOLERANCE_DB;
    rows.push([
      "<strong>SNR mesuré (phrase entière)</strong>",
      `<strong class="${ok ? "ok" : "bad"}">${measured.toFixed(1)} dB</strong>`,
    ]);
    rows.push(["SNR pendant la parole active", `${activeSnr.toFixed(1)} dB`]);
    verdict = ok
      ? `<p class="verif-verdict ok">✓ Conforme : SNR cible ${target.toFixed(1)} dB, mesuré ${measured.toFixed(1)} dB (écart ${signed(delta)} dB).</p>`
      : `<p class="verif-verdict bad">✗ Écart de ${signed(delta)} dB par rapport au SNR cible de ${target.toFixed(1)} dB.</p>`;
    if (n.snr !== v.snr || n.noiseType !== currentNoiseType()) {
      verdict += `<p class="hint">Les deux mesures ne proviennent pas de la même écoute : vérifiez que le bruit mesuré correspond bien au bruit sélectionné.</p>`;
    }
  } else {
    verdict = `<p class="hint">Mesurez aussi ${n ? "la voix" : "le bruit"} pour obtenir le SNR.</p>`;
  }

  const peak = Math.max(n ? n.peak : 0, v ? v.peak : 0);
  let clip = "";
  if (peak >= 0.999) clip = `<p class="verif-verdict bad">⚠ Écrêtage détecté (crête ${fmtDbFS(dbFS(peak))}) : le SNR réellement entendu n'est plus celui affiché.</p>`;
  else if (peak > 0) clip = `<p class="hint">Crête la plus élevée : ${fmtDbFS(dbFS(peak))} (avant volume général).</p>`;

  el.innerHTML = `
    <h3>Mesure à la lecture</h3>
    <table class="verif-table">
      ${rows.map(r => `<tr><td>${r[0]}</td><td class="num">${r[1]}</td></tr>`).join("")}
    </table>
    ${verdict}${clip}`;
}

// ---------------------------------------------------------------- analyse hors-ligne

function dataUriToArrayBuffer(url) {
  const bin = atob(url.slice(url.indexOf(",") + 1));
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return bytes.buffer;
}

async function verifDecode(url) {
  if (verif.decoded[url]) return verif.decoded[url];
  let buf;
  if (url.startsWith("data:")) {
    // build autonome : les fichiers sont déjà là, pas de fetch (bloqué en file://)
    buf = dataUriToArrayBuffer(url);
  } else {
    const resp = await fetch(url);
    if (!resp.ok) throw new Error(`HTTP ${resp.status} sur ${url}`);
    buf = await resp.arrayBuffer();
  }
  const audio = await state.audioCtx.decodeAudioData(buf);
  verif.decoded[url] = audio;
  return audio;
}

function bufferStats(buf) {
  const n = buf.length;
  const ch = buf.numberOfChannels;
  const mono = new Float32Array(n);
  for (let c = 0; c < ch; c++) {
    const d = buf.getChannelData(c);
    for (let i = 0; i < n; i++) mono[i] += d[i] / ch;
  }
  let sum = 0, peak = 0;
  for (let i = 0; i < n; i++) {
    const v = mono[i];
    sum += v * v;
    const a = v < 0 ? -v : v;
    if (a > peak) peak = a;
  }
  const rms = Math.sqrt(sum / n);
  // RMS restreint aux trames "parole active"
  const win = Math.round(buf.sampleRate * 0.02);
  let active = rms;
  if (win > 0 && n > win) {
    const frames = [];
    for (let i = 0; i + win <= n; i += win) {
      let s = 0;
      for (let j = i; j < i + win; j++) s += mono[j] * mono[j];
      frames.push(Math.sqrt(s / win));
    }
    let max = 0;
    for (const f of frames) if (f > max) max = f;
    const thr = max * Math.pow(10, VERIF_ACTIVE_THRESHOLD_DB / 20);
    let s2 = 0, k = 0;
    for (const f of frames) if (f >= thr) { s2 += f * f; k++; }
    if (k) active = Math.sqrt(s2 / k);
  }
  return { rms, active, peak, seconds: n / buf.sampleRate };
}

async function verifOfflineAnalysis() {
  const out = $("#verifOffline");
  out.innerHTML = `<p class="hint">Décodage en cours…</p>`;
  try {
    await ensureAudioCtx();
    const snr = parseFloat($("#verifSnr").value) || MAIN_SNR;
    const noiseType = currentNoiseType();
    const nBuf = await verifDecode(audioUrl(NOISE_FILES[noiseType]));
    const vBuf = await verifDecode(audioUrl(verif.entry.file));
    const nS = bufferStats(nBuf), vS = bufferStats(vBuf);

    // les constantes de l'app sont exprimées sur l'échelle PCM 16 bits
    const nRms16 = nS.rms * 32768, vRms16 = vS.rms * 32768;
    const errNoise = dbFS(NOISE_RMS_REF / nRms16);   // erreur induite par la constante bruit
    const errVoice = dbFS(vRms16 / TARGET_RMS_REF);  // erreur induite par la constante voix
    const realSnr = snr + errNoise + errVoice;
    const delta = realSnr - snr;
    const ok = Math.abs(delta) <= VERIF_TOLERANCE_DB;

    const nbSample = parseInt($("#verifNbPhrases").value, 10) || 0;
    let dispersion = "";
    if (nbSample > 0) {
      out.innerHTML = `<p class="hint">Analyse de ${nbSample} phrases du corpus…</p>`;
      const pool = state.byCallsign[$("#targetCallsign").value] || state.manifest;
      const sample = shuffle(pool).slice(0, Math.min(nbSample, pool.length));
      const vals = [];
      for (const e of sample) {
        const b = await verifDecode(audioUrl(e.file));
        vals.push(bufferStats(b).rms * 32768);
      }
      const mean = vals.reduce((s, x) => s + x, 0) / vals.length;
      const min = Math.min(...vals), max = Math.max(...vals);
      dispersion = `
        <h3>Dispersion du corpus (${vals.length} phrases, indicatif ${$("#targetCallsign").value})</h3>
        <table class="verif-table">
          <tr><td>RMS moyen</td><td class="num">${mean.toFixed(1)} (soit ${signed(dbFS(mean / TARGET_RMS_REF), 2)} dB / constante)</td></tr>
          <tr><td>RMS minimum</td><td class="num">${min.toFixed(1)} (${signed(dbFS(min / TARGET_RMS_REF), 2)} dB)</td></tr>
          <tr><td>RMS maximum</td><td class="num">${max.toFixed(1)} (${signed(dbFS(max / TARGET_RMS_REF), 2)} dB)</td></tr>
        </table>
        <p class="hint">Le SNR effectif varie d'une phrase à l'autre de la même quantité : c'est l'erreur résiduelle liée à l'utilisation d'une constante RMS unique pour tout le corpus.</p>`;
    }

    out.innerHTML = `
      <h3>Analyse hors-ligne (décodage exact des fichiers)</h3>
      <table class="verif-table">
        <tr><td>RMS mesuré du bruit (${noiseType})</td><td class="num">${nRms16.toFixed(1)} — constante NOISE_RMS_REF = ${NOISE_RMS_REF}</td></tr>
        <tr><td>RMS mesuré de la phrase</td><td class="num">${vRms16.toFixed(1)} — constante TARGET_RMS_REF = ${TARGET_RMS_REF}</td></tr>
        <tr><td>Erreur apportée par la constante bruit</td><td class="num">${signed(errNoise, 2)} dB</td></tr>
        <tr><td>Erreur apportée par la constante voix</td><td class="num">${signed(errVoice, 2)} dB</td></tr>
        <tr><td><strong>SNR réellement produit</strong></td><td class="num"><strong class="${ok ? "ok" : "bad"}">${realSnr.toFixed(2)} dB</strong> pour un SNR demandé de ${snr.toFixed(1)} dB</td></tr>
        <tr><td>Crête voix après gain</td><td class="num">${fmtDbFS(dbFS(vS.peak * verifVoiceGain(snr)))}</td></tr>
      </table>
      ${dispersion}`;
  } catch (err) {
    out.innerHTML = `<p class="verif-verdict bad">Analyse hors-ligne impossible : ${err.message}</p>
      <p class="hint">Cette analyse lit les fichiers avec <code>fetch()</code>, ce que les navigateurs bloquent en <code>file://</code>.
      Servez le dossier en local puis rouvrez l'app :<br><code class="mono">python3 -m http.server 8000</code> → <code class="mono">http://localhost:8000</code>.
      La « mesure à la lecture » ci-dessus fonctionne, elle, dans tous les cas.</p>`;
  }
}

// ---------------------------------------------------------------- câblage

(function initVerif() {
  const snrInput = $("#verifSnr");
  if (!snrInput) return;
  snrInput.value = MAIN_SNR;
  $("#btnVerifNoise").addEventListener("click", () => verifPlay("noise"));
  $("#btnVerifVoice").addEventListener("click", () => verifPlay("voice"));
  $("#btnVerifMix").addEventListener("click", () => verifPlay("mix"));
  $("#btnVerifStop").addEventListener("click", () => verifStopPlayback());
  $("#btnVerifNewStim").addEventListener("click", () => { verifPickStimulus(); verif.last.voice = null; renderVerifMeasure(); });
  $("#btnVerifAnalyse").addEventListener("click", () => verifOfflineAnalysis());
  $("#targetCallsign").addEventListener("change", () => verifPickStimulus());
  $("#btnStart").addEventListener("click", () => verifStopPlayback());
  verifSetPlayingUI(false);
  verifPickStimulus();
})();
