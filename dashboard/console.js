/* Fuzz console: a live diagram of the circuit (board -> relay -> wire -> appliance) plus one timeline. */
const $ = id => document.getElementById(id);
const NS = "http://www.w3.org/2000/svg";
const S = (tag, attrs = {}, text) => { const e = document.createElementNS(NS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); if (text !== undefined) e.textContent = text; return e; };
const live = new Live({ withRun: true });
const cssVar = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();

const X0 = 410, X1 = 1020, DMAX = 20;                       // ruler: 0 m at the board side, 20 m at the appliance
const xOf = d => X0 + Math.max(0, Math.min(DMAX, d)) / DMAX * (X1 - X0);

/* ---- sensor rows on the board */
const ROWS = [
  { k: "rf",   label: "Arc noise",   get: r => r.rf,      fmt: v => v.toFixed(2),        frac: r => r.rf / 0.8 },
  { k: "leak", label: "Leakage",     get: r => r.leak_ma, fmt: v => v.toFixed(1) + " mA", frac: r => r.leak_ma / 30 },
  { k: "didt", label: "Current spikes", get: r => r.didt, fmt: v => v.toFixed(2),        frac: r => r.didt / 1.0 },
  { k: "temp", label: "Temperature", get: r => r.temp_c,  fmt: v => v.toFixed(1) + " °C", frac: r => (r.temp_c - 40) / 40 },
  { k: "volt", label: "Mains voltage", get: r => r.volt,  fmt: v => v.toFixed(0) + " V",  frac: r => r.volt > 0 && (r.volt < 207 || r.volt > 253) ? 0.9 : 0 },
];
const rowEls = {};
ROWS.forEach((c, i) => {
  const y = 112 + i * 38, g = S("g", { class: "row" });
  const lamp = S("circle", { class: "lamp", cx: 46, cy: y - 6, r: 7 });
  const l = S("text", { class: "lbl", x: 64, y }, c.label);
  const v = S("text", { class: "val", x: 282, y, "text-anchor": "end" }, "-");
  g.append(lamp, l, v); $("rows").append(g);
  rowEls[c.k] = { g, lamp, v };
});

/* ---- ruler ticks */
for (let d = 0; d <= DMAX; d += 5) {
  $("ticks").append(S("line", { class: "tick", x1: xOf(d), x2: xOf(d), y1: 226, y2: 238 }));
  $("ticks").append(S("text", { class: "small", x: xOf(d), y: 262, "text-anchor": "middle" }, d === 0 ? "board" : d === DMAX ? "20 m" : d + " m"));
}
/* ---- sparks at the fault: short lines radiating from it, each flickering on its own beat */
for (let i = 0; i < 7; i++) {
  const a = (i / 7) * Math.PI * 2 + 0.3, r0 = 13, r1 = 22 + (i % 3) * 5;
  const s = S("line", { class: "spark", x1: Math.cos(a) * r0, y1: Math.sin(a) * r0, x2: Math.cos(a) * r1, y2: Math.sin(a) * r1 });
  s.style.animationDelay = (i * 0.13) + "s"; s.style.animationDuration = (0.7 + (i % 4) * 0.17) + "s";
  $("sparks").append(s);
}
const sparksG = $("sparks");

/* ---- appliance icons by family, drawn in a 140x120 box centred at 0,0 */
const ICONS = {
  heating: () => [S("path", { class: "ic", d: "M-38 14 L-26 -14 L-14 14 L-2 -14 L10 14 L22 -14 L34 14 L38 8" })],
  motor: () => [S("circle", { class: "ic", cx: 0, cy: 0, r: 28 }), S("path", { class: "ic", d: "M-12 10 V-10 L0 4 L12 -10 V10" })],
  electronics: () => [S("rect", { class: "ic", x: -22, y: -22, width: 44, height: 44, rx: 5 }), ...[-12, 0, 12].flatMap(p => [S("line", { class: "ic", x1: -30, x2: -22, y1: p, y2: p }), S("line", { class: "ic", x1: 22, x2: 30, y1: p, y2: p })])],
  microwave: () => [S("rect", { class: "ic", x: -38, y: -24, width: 76, height: 48, rx: 6 }), S("rect", { class: "ic", x: -30, y: -16, width: 40, height: 32, rx: 3 }), S("circle", { class: "ic", cx: 24, cy: -6, r: 3 }), S("circle", { class: "ic", cx: 24, cy: 8, r: 3 })],
  none: () => [S("rect", { class: "ic", x: -34, y: -26, width: 68, height: 52, rx: 8, "stroke-dasharray": "5 7" }), S("text", { x: 0, y: 11, "text-anchor": "middle", fill: cssVar("--dim"), "font-size": 30 }, "?")],
};
let iconKey = null;
function setIcon(k) { if (k === iconKey) return; iconKey = k; $("appIcon").replaceChildren(...ICONS[k]()); }
setIcon("none");

/* ---- helpers shared with the backend wording */
const CH_TEXT = { rf: "Arc activity", leak: "Leakage current", didt: "Fast current spikes", temp: "Overheating", volt: "Mains voltage out of range" };
function dominant(r) {
  if (r.volt > 0 && (r.volt < 207 || r.volt > 253)) return "volt";
  const s = { rf: r.rf / 0.8, leak: r.leak_ma / 30, didt: r.didt / 1.0, temp: (r.temp_c - 40) / 40 };
  const k = Object.keys(s).reduce((a, b) => s[a] >= s[b] ? a : b);
  return s[k] >= 0.35 ? k : null;
}
function reasonAt(hist, i) {                              // after a trip the readings are zero, so use the last live reading
  for (let j = i; j >= 0; j--) if (hist[j].relay !== "OPEN" && hist[j].volt > 0) return dominant(hist[j]);
  return null;
}
function risk(r) {
  const f = Math.max(r.rf / 0.8, r.leak_ma / 30, r.didt, (r.temp_c - 40) / 40, r.volt > 0 && (r.volt < 207 || r.volt > 253) ? 0.85 : 0);
  return Math.max(0, f);
}

/* ---- timeline */
let lastHist = [];
function drawTimeline(hist, idx) {
  const cv = $("tl"), dpr = devicePixelRatio || 1, W = cv.clientWidth, H = cv.clientHeight;
  if (!W) return;
  if (cv.width !== W * dpr || cv.height !== H * dpr) { cv.width = W * dpr; cv.height = H * dpr; }
  const g = cv.getContext("2d"); g.setTransform(dpr, 0, 0, dpr, 0, 0); g.clearRect(0, 0, W, H);
  const top = 8, bot = H - 14, MAXV = 1.25, y = v => bot - Math.min(MAXV, v) / MAXV * (bot - top);
  const n = hist.length, x = i => 2 + (n <= 1 ? 0 : i / (n - 1)) * (W - 4);
  g.font = "12px " + cssVar("--mono"); g.textBaseline = "bottom";
  [[1, "trip", "--trip"], [0.8, "warning", "--warn"]].forEach(([v, t, c]) => {
    g.setLineDash([5, 5]); g.strokeStyle = cssVar(c); g.globalAlpha = .55; g.lineWidth = 1;
    g.beginPath(); g.moveTo(0, y(v) + .5); g.lineTo(W, y(v) + .5); g.stroke();
    g.setLineDash([]); g.globalAlpha = 1; g.fillStyle = cssVar(c); g.textAlign = "left"; g.fillText(t, 4, y(v) - 3);
  });
  if (n) {
    g.beginPath(); hist.forEach((r, i) => { const px = x(i), py = y(risk(r)); i ? g.lineTo(px, py) : g.moveTo(px, py); });
    g.lineTo(x(n - 1), bot); g.lineTo(x(0), bot); g.closePath();
    g.fillStyle = "rgba(221,225,232,.08)"; g.fill();
    g.strokeStyle = cssVar("--text"); g.lineWidth = 2; g.lineJoin = "round"; g.beginPath();
    hist.forEach((r, i) => { const px = x(i), py = y(risk(r)); i ? g.lineTo(px, py) : g.moveTo(px, py); });
    g.stroke();
    hist.forEach((r, i) => {
      if (r.state === "NORMAL") return;
      g.fillStyle = cssVar(r.state === "TRIP" ? "--trip" : "--warn");
      g.fillRect(x(i) - 1, bot + 4, Math.max(2, (W - 4) / n + 1), 4);
    });
  }
  if (idx !== null && n) {
    g.strokeStyle = cssVar("--sel"); g.lineWidth = 2; g.beginPath(); g.moveTo(Math.round(x(idx)), 0); g.lineTo(Math.round(x(idx)), H); g.stroke();
  }
}
function scrubTo(e) {
  if (!lastHist.length) return;
  const r = $("tl").getBoundingClientRect();
  live.setScrub(Math.round(Math.max(0, Math.min(1, (e.clientX - r.left) / r.width)) * (lastHist.length - 1)));
}
$("tl").addEventListener("pointerdown", e => { $("tl").setPointerCapture(e.pointerId); scrubTo(e); });
$("tl").addEventListener("pointermove", e => { if (e.buttons) scrubTo(e); });
$("goLive").onclick = () => live.setScrub(null);
addEventListener("keydown", e => {
  if (e.target.closest("input, select")) return;
  if (e.key === "Escape") { if (!$("drawer").hidden) toggleDrawer(false); else live.setScrub(null); }
  if ((e.key === "ArrowLeft" || e.key === "ArrowRight") && lastHist.length) {
    const cur = live.scrub === null ? lastHist.length - 1 : live.scrub;
    live.setScrub(Math.max(0, Math.min(lastHist.length - 1, cur + (e.key === "ArrowLeft" ? -1 : 1))));
  }
});

/* ---- details drawer */
function toggleDrawer(open) { $("drawer").hidden = !open; $("more").setAttribute("aria-expanded", open); }
$("more").onclick = () => toggleDrawer($("drawer").hidden);
$("closeMore").onclick = () => toggleDrawer(false);
function pretty(o) {
  const s = JSON.stringify(o, null, 2).replace(/&/g, "&amp;").replace(/</g, "&lt;");
  return s.replace(/("(?:\\.|[^"\\])*")(\s*:)?|\b(true|false|null)\b|-?\d+\.?\d*(?:[eE][+-]?\d+)?/g, (m, str, colon, bool) =>
    str ? (colon ? `<span class="k">${str}</span>${colon}` : `<span class="s">${str}</span>`) : bool ? `<span class="b">${m}</span>` : `<span class="n">${m}</span>`);
}
function ruleList(hist, r) {
  const i = hist.indexOf(r), win = hist.slice(Math.max(0, i - 4), i + 1);
  const sc = x => ({ rf: x.rf / 0.8, leak: x.leak_ma / 30, didt: x.didt, temp: (x.temp_c - 40) / 40 });
  const now = sc(r), avg = {};
  Object.keys(now).forEach(k => avg[k] = win.reduce((s, x) => s + sc(x)[k], 0) / win.length);
  /* di/dt never acts alone: motors and dimmers make fast steps all the time, so it counts only while another channel is raised */
  if (!["rf", "leak", "temp"].some(k => avg[k] >= 0.35)) { now.didt = 0; avg.didt = 0; }
  const keys = o => Object.keys(o);
  return [
    { cls: "trip", on: keys(now).some(k => now[k] >= 1) || r.relay === "OPEN", t: "A channel reaches its trip limit (or the relay is latched open)" },
    { cls: "", on: keys(avg).filter(k => avg[k] >= 0.35).length >= 2, t: "Two channels average 35% of their limit or more over 5 readings" },
    { cls: "", on: keys(now).some(k => now[k] >= 0.8), t: "One channel is at 80% of its limit or more" },
    { cls: "", on: r.volt > 0 && (r.volt < 207 || r.volt > 253), t: "Mains voltage is outside 207 to 253 V" },
  ];
}

/* ---- controls */
let optsLoaded = false;
async function loadOptions() {
  try {
    const o = await getJSON("/api/sim/options");
    $("scn").replaceChildren(...o.scenarios.map(s => new Option(({ normal: "Normal use", arc: "Arc fault", leakage: "Leakage", overheat: "Overheating", surge: "Voltage surge", motor: "Motor load (normal)" })[s] || s, s)));
    $("app").replaceChildren(...o.appliances.map(a => new Option(a, a)));
    $("scn").value = "arc"; syncArc(); optsLoaded = true;
  } catch (e) { /* retried on the next update */ }
}
const syncArc = () => { $("distBox").hidden = $("scn").value !== "arc"; };
$("scn").onchange = syncArc;
$("cmd").addEventListener("submit", async e => {
  e.preventDefault(); live.scrub = null;
  await post("/api/sim/start", { scenario: $("scn").value, appliance: $("app").value, distance: +$("dist").value, interval: 0.4 });
  live.tick();
});
$("stop").onclick = async () => { await post("/api/sim/stop"); live.tick(); };
$("reset").onclick = async () => { await post("/api/sim/reset"); live.scrub = null; live.tick(); };
$("unit").onchange = e => live.setUnit(e.target.value);

/* ---- render */
live.onUpdate(m => {
  if (!optsLoaded) loadOptions();
  const sel = $("unit");
  if (sel.options.length !== m.units.length) sel.replaceChildren(...m.units.map(u => new Option(u.unit_id, u.unit_id)));
  const hist = m.hist, r = m.view; lastHist = hist;
  drawTimeline(hist, m.replay ? m.idx : null);
  $("goLive").hidden = !m.replay; $("replayHint").hidden = m.replay;

  if (m.offline) { document.body.dataset.state = "idle"; $("pill").textContent = "offline"; $("title").textContent = "Can't reach the backend"; $("sub").textContent = "Start it with: python backend\\app.py"; return; }
  if (!r) { document.body.dataset.state = "idle"; $("pill").textContent = "no data"; $("title").textContent = "Waiting for the circuit"; $("sub").textContent = "Press Run to start a demo, or connect the ESP32."; $("timeLabel").textContent = "Timeline"; return; }

  const state = r.state, ai = r.ai || {}, i = hist.indexOf(r), reason = reasonAt(hist, i < 0 ? hist.length - 1 : i);
  document.body.dataset.state = state;
  const open = r.relay === "OPEN";

  /* headline */
  $("pill").textContent = state === "NORMAL" ? "Normal" : state === "WARNING" ? "Warning" : "Power cut";
  const d = ai.distance;
  if (state === "NORMAL") { $("title").textContent = "All normal"; $("sub").textContent = "Every channel is inside its limits and the relay is closed."; }
  else {
    let t = (state === "TRIP" ? "Power cut: " : "") + (CH_TEXT[reason] || "A fault is developing");
    if (d && (reason === "rf" || reason === "didt")) t += d.hi - d.lo > 12 ? `, ${d.zone}` : `, about ${d.m.toFixed(0)} m from the board`;
    $("title").textContent = t;
    $("sub").textContent = ai.appliances && (reason === "rf" || reason === "didt")
      ? `The load looks like ${FAMILY_TEXT[ai.family.name] || "an appliance"}: ${ai.appliances.slice(0, 2).map(a => `${a.name} ${Math.round(a.p * 100)}%`).join(", ")}.`
      : (open ? "The relay is open, so the circuit is off." : "Fuzz is watching this channel closely.");
  }
  $("timeLabel").textContent = m.replay ? `Replay ${clock(r.time)}` : (r.sim_truth ? `Live, ${r.sim_truth.t.toFixed(0)} s into the run` : "Live");

  /* board rows */
  ROWS.forEach(c => {
    const e = rowEls[c.k], v = c.get(r), f = c.frac(r);
    e.v.textContent = open ? "off" : c.fmt(v);
    e.lamp.setAttribute("class", "lamp" + (open ? "" : f >= 1 ? " trip" : f >= .8 ? " warn" : " ok"));
    e.g.setAttribute("class", "row" + (state !== "NORMAL" && reason === c.k ? " flag" : ""));
    if (state !== "NORMAL" && reason === c.k) e.lamp.setAttribute("class", "lamp " + (state === "TRIP" ? "trip" : "warn"));
  });

  /* relay and wire */
  $("lever").setAttribute("class", "lever" + (open ? " open" : ""));
  $("relayTxt").textContent = open ? "relay open" : "relay closed";
  const speed = state === "WARNING" ? 0.7 : 1.3;
  $("circuit").style.setProperty("--dur", speed + "s");

  /* appliance */
  const loadKnown = ai.appliances && (reason === "rf" || reason === "didt");
  const fam = loadKnown ? ai.family.name : null;
  setIcon(fam || "none");
  $("appliance").firstElementChild.setAttribute("class", "appbox" + (open ? "" : " on"));
  $("appIcon").setAttribute("class", open ? "" : "on");
  const nm = loadKnown ? ai.appliances[0].name : "Appliance";
  $("appName").textContent = nm.length > 18 ? nm.slice(0, 17) + "…" : nm;
  $("appSub").textContent = loadKnown ? `${Math.round(ai.appliances[0].p * 100)}% likely` : "not identified";

  /* fault marker and distance range */
  const fault = $("fault"), band = $("band"), showDist = d && (state !== "NORMAL");
  fault.setAttribute("visibility", showDist ? "visible" : "hidden"); band.setAttribute("visibility", showDist ? "visible" : "hidden");
  $("rangeTxt").textContent = "";
  if (showDist) {
    const fx = xOf(d.m);
    ["drop", "pulse", "dot"].forEach(id => { const el_ = $(id); ["x1", "x2", "cx"].forEach(a => { if (el_.hasAttribute(a)) el_.setAttribute(a, fx); }); });
    sparksG.setAttribute("transform", `translate(${fx},165)`);
    $("faultTxt").setAttribute("x", fx); $("faultTxt").textContent = `≈ ${d.m.toFixed(0)} m`;
    band.setAttribute("x", xOf(d.lo)); band.setAttribute("width", Math.max(6, xOf(d.hi) - xOf(d.lo)));
    $("rangeTxt").setAttribute("x", Math.max(520, Math.min(930, fx)));
    $("rangeTxt").textContent = `likely between ${d.lo.toFixed(0)} and ${d.hi.toFixed(0)} m (90% range)`;
  }

  /* details */
  const rl = $("rules"); rl.textContent = "";
  ruleList(hist, r).forEach(x => { const li = el("li", (x.cls + (x.on ? " on" : "")).trim()); li.append(el("span", "dot"), el("span", "", x.t)); rl.append(li); });
  $("truth").innerHTML = r.sim_truth ? Object.entries(r.sim_truth).map(([k, v]) => `${k.padEnd(11)}<b>${v}</b>`).join("\n") : "none: this packet came from hardware";
  const { sim_truth, ...rest } = r; $("raw").innerHTML = pretty(rest);
});
addEventListener("resize", () => live.emit());
live.start();
