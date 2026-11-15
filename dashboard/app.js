const MODE = location.pathname.startsWith("/client") ? "client" : "operator";
const root = document.documentElement;
const $ = id => document.getElementById(id);
const live = new Live({ withRun: MODE === "operator", unit: new URLSearchParams(location.search).get("unit") });

const IC = {
  check: '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
  alert: '<path d="M12 4l9 16H3z"/><path d="M12 10v4M12 17.2v.1"/>',
  off: '<path d="M12 3v8"/><path d="M6.3 6.6a8 8 0 1 0 11.4 0"/>',
  rf: '<path d="M5 18a9 9 0 0 1 0-12M8.5 15a5 5 0 0 1 0-6"/><circle cx="12.5" cy="12" r="1.3"/><path d="M16 9a5 5 0 0 1 0 6M19.5 6a9 9 0 0 1 0 12"/>',
  leak: '<path d="M12 3.5c3.5 4.2 6 7 6 10a6 6 0 0 1-12 0c0-3 2.5-5.8 6-10z"/>',
  didt: '<path d="M13 3L5 13.5h6L10 21l8-10.5h-6z"/>',
  temp: '<path d="M10 14.5V5a2 2 0 0 1 4 0v9.5a4 4 0 1 1-4 0z"/>',
  volt: '<path d="M9 3v5M15 3v5M6 8h12v3a6 6 0 0 1-12 0z"/><path d="M12 17v4"/>',
  home: '<path d="M4 11l8-7 8 7v9H4z"/><path d="M10 20v-6h4v6"/>',
  history: '<circle cx="12" cy="12" r="8.5"/><path d="M12 7v5l3 2"/>',
  bell: '<path d="M6 16V11a6 6 0 0 1 12 0v5l1.5 2h-15z"/><path d="M10 20a2 2 0 0 0 4 0"/>',
  sliders: '<path d="M5 8h9M18 8h1M5 16h1M10 16h9"/><circle cx="16" cy="8" r="2"/><circle cx="8" cy="16" r="2"/>',
};
const svg = (n, s = 24, sw = 1.8) => `<svg viewBox="0 0 24 24" width="${s}" height="${s}" fill="none" stroke="currentColor" stroke-width="${sw}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${IC[n]}</svg>`;

const COPY = {
  NORMAL: { word: "All good", sub: "Your circuit is calm. Fuzz is watching.", icon: "check" },
  WARNING: { word: "Take a look", sub: "Something on this circuit needs attention.", icon: "alert" },
  TRIP: { word: "Power is off", sub: "Fuzz switched this circuit off to keep you safe.", icon: "off" },
};
const STEPS = {
  WARNING: ["If it is safe to do so, switch off and unplug appliances on this circuit, heaters first.", "Do not ignore this warning. Fuzz has seen more than one sign of a fault.", "Ask a licensed electrician to inspect the wiring and sockets."],
  TRIP: ["Power to this circuit was cut automatically.", "Keep it off until a licensed electrician has checked the wiring.", "Do not keep resetting it."],
};
const TILES = [
  { k: "rf", name: "Arc noise", icon: "rf", unit: "", pct: r => r.rf / 0.8 * 100, val: r => r.rf.toFixed(2), lim: "Fuzz cuts power at 0.80." },
  { k: "leak", name: "Leakage", icon: "leak", unit: "mA", pct: r => r.leak_ma / 30 * 100, val: r => r.leak_ma.toFixed(1), lim: "Fuzz cuts power at 30 mA." },
  { k: "didt", name: "Current spikes", icon: "didt", unit: "", pct: r => r.didt * 100, val: r => r.didt.toFixed(2), lim: "Fuzz cuts power at 1.00." },
  { k: "temp", name: "Temperature", icon: "temp", unit: "°C", pct: r => Math.max(0, (r.temp_c - 40) / 40 * 100), val: r => r.temp_c.toFixed(1), lim: "Warns above 40 °C, cuts power at 80 °C." },
  { k: "volt", name: "Mains voltage", icon: "volt", unit: "V", wide: true, val: r => r.volt.toFixed(0), lim: "Safe range is 207 to 253 V." },
];

/* ======================= the orb ======================= */
class Orb {
  constructor(box, interactive) {
    this.box = box;
    box.innerHTML = `<div class="tilt"><div class="orb"><div class="orb-clip">
      <div class="set calm"><i></i><i></i><i></i></div><div class="set warn"><i></i><i></i><i></i></div><div class="set off"><i></i><i></i><i></i></div>
      <div class="gloss"></div></div></div><div class="ring"></div><div class="ring r2"></div><div class="ping"></div><div class="orb-icon"></div></div>`;
    this.icon = box.querySelector(".orb-icon"); this.ping = box.querySelector(".ping"); this.cur = null;
    if (!interactive) return;
    const aim = e => {
      const r = box.getBoundingClientRect();
      box.style.setProperty("--tx", clamp((e.clientX - r.left - r.width / 2) / (r.width / 2), -1, 1).toFixed(3));
      box.style.setProperty("--ty", clamp((e.clientY - r.top - r.height / 2) / (r.height / 2), -1, 1).toFixed(3));
    };
    box.addEventListener("pointerdown", e => { box.classList.add("drag"); aim(e); });
    box.addEventListener("pointermove", e => { if (e.buttons || e.pointerType === "mouse") aim(e); });
    const rest = () => { box.classList.remove("drag"); box.style.setProperty("--tx", 0); box.style.setProperty("--ty", 0); };
    box.addEventListener("pointerup", rest); box.addEventListener("pointerleave", rest); box.addEventListener("pointercancel", rest);
  }
  set(state) {
    if (this.cur === state) return; this.cur = state;
    this.icon.innerHTML = svg(COPY[state].icon, 64, 1.6);
  }
  pulse() { this.ping.classList.remove("go"); void this.ping.offsetWidth; this.ping.classList.add("go"); }
}
const clamp = (x, a, b) => Math.max(a, Math.min(b, x));
const orb = new Orb($("orb"), true), mini = new Orb($("miniorb"), false);

/* ======================= static parts ======================= */
const hr = new Date().getHours();
$("greet").textContent = hr < 5 ? "Good night" : hr < 12 ? "Good morning" : hr < 18 ? "Good afternoon" : "Good evening";

[["home", "Home", "p-home"], ["sliders", "Sensors", "p-sensors"], ["history", "History", "p-history"]].forEach(([ic, label, id], i) => {
  const b = el("button"); b.setAttribute("role", "tab"); b.innerHTML = svg(ic, 22) + label; b.dataset.i = i;
  b.onclick = () => $("pager").scrollTo({ left: i * $("pager").clientWidth, behavior: "smooth" });
  $("tabs").append(b);
});
$("pager").addEventListener("scroll", () => {
  const i = Math.round($("pager").scrollLeft / $("pager").clientWidth);
  [...$("tabs").children].forEach((b, j) => b.setAttribute("aria-selected", String(i === j)));
}, { passive: true });
$("tabs").firstChild.setAttribute("aria-selected", "true");

const tiles = {};
TILES.forEach(t => {
  const b = el("button", "tile" + (t.wide ? " wide" : "")); b.setAttribute("aria-expanded", "false");
  b.innerHTML = `<div class="head"><div class="dial"><svg viewBox="0 0 46 46"><circle class="bg" cx="23" cy="23" r="19"/><circle class="fg" cx="23" cy="23" r="19" stroke-dasharray="0 120"/></svg><div class="ic">${svg(t.icon, 20)}</div></div>
    <div><div class="nm">${t.name}</div><div class="st">-</div></div></div>
    <div class="val">-<small>${t.unit}</small></div>
    <div class="more"><div><svg class="spark" viewBox="0 0 120 44" preserveAspectRatio="none"><polyline fill="none" stroke="#7b6be0" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" vector-effect="non-scaling-stroke"/></svg><p>${t.lim}</p></div></div>`;
  b.onclick = () => b.setAttribute("aria-expanded", String(b.getAttribute("aria-expanded") !== "true"));
  $("tiles").append(b);
  tiles[t.k] = { b, st: b.querySelector(".st"), val: b.querySelector(".val"), fg: b.querySelector(".fg"), spark: b.querySelector(".spark polyline") };
});

/* ---------- sheets ---------- */
function openSheet(html, after) {
  $("sheet").innerHTML = `<div class="grabber"></div>${html}`;
  $("sheet").classList.add("on"); $("scrim").classList.add("on");
  const d = $("sheet").querySelector(".done"); if (d) d.onclick = closeSheet;
  if (after) after($("sheet"));
}
function closeSheet() { $("sheet").classList.remove("on"); $("scrim").classList.remove("on"); }
$("scrim").onclick = closeSheet;
addEventListener("keydown", e => { if (e.key === "Escape") closeSheet(); });
$("todo").onclick = () => {
  const s = live.last && live.last.view ? live.last.view.state : "WARNING";
  openSheet(`<h2>${s === "TRIP" ? "What to do now" : "What to do"}</h2><ol>${(STEPS[s] || STEPS.WARNING).map(x => `<li>${x}</li>`).join("")}</ol><button class="done">Got it</button>`);
};

/* ---------- top actions ---------- */
if (MODE === "client") {
  const bell = el("button", "chip btn"); bell.innerHTML = svg("bell", 18) + "Alerts"; bell.setAttribute("aria-label", "Turn on alerts on this device");
  bell.onclick = async () => { try { await Notification.requestPermission(); } catch (e) {} bell.lastChild.textContent = (window.Notification && Notification.permission === "granted") ? "Alerts on" : "Alerts blocked"; };
  $("actions").append(bell);
} else {
  const demo = el("button", "chip btn"); demo.innerHTML = svg("sliders", 18) + "Run a demo"; demo.onclick = openDemo; $("actions").append(demo);
  $("actions").prepend(el("span", "chip", "Operator"));
}

/* ---------- demo drawer (operator) ---------- */
const SCN = [["normal", "Normal use"], ["arc", "Arc fault"], ["leakage", "Leakage"], ["overheat", "Overheating"], ["surge", "Surge"]];
const SPEEDS = [["Quick", 0.4], ["Normal", 0.8], ["Slow", 1.5]];
let scenario = "arc", interval = 0.4, appliance = "Heater", dist = 10, appliances = [];
function openDemo() {
  const seg = (items, cur, name) => items.map(([k, l]) => `<button data-${name}="${k}" aria-pressed="${k === cur}">${l}</button>`).join("");
  openSheet(`<h2>Run a demo</h2>
    <label>Scenario</label><div class="opts" id="o-scn">${seg(SCN, scenario, "k")}</div>
    <label for="d-app">Appliance on the circuit</label><select id="d-app">${appliances.map(a => `<option ${a === appliance ? "selected" : ""}>${a}</option>`).join("")}</select>
    <div id="d-distbox" ${scenario === "arc" ? "" : "hidden"}><label for="d-dist">Fault distance from the board: <span id="d-dv">${dist} m</span></label><input type="range" id="d-dist" min="1" max="20" step="1" value="${dist}"></div>
    <label>Speed</label><div class="opts" id="o-sp">${SPEEDS.map(([l, v]) => `<button data-v="${v}" aria-pressed="${v === interval}">${l}</button>`).join("")}</div>
    <div class="runrow"><button class="go" id="d-start">Start</button><button id="d-stop">Stop</button><button id="d-reset">Reset</button></div>
    <div class="prog"><i id="d-prog"></i></div><p class="muted small" id="d-txt" style="margin-top:8px"></p>
    <button class="done">Close</button>`, s => {
    s.querySelectorAll("#o-scn button").forEach(b => b.onclick = () => { scenario = b.dataset.k; s.querySelectorAll("#o-scn button").forEach(x => x.setAttribute("aria-pressed", String(x === b))); s.querySelector("#d-distbox").hidden = scenario !== "arc"; });
    s.querySelectorAll("#o-sp button").forEach(b => b.onclick = () => { interval = +b.dataset.v; s.querySelectorAll("#o-sp button").forEach(x => x.setAttribute("aria-pressed", String(x === b))); });
    s.querySelector("#d-app").onchange = e => appliance = e.target.value;
    s.querySelector("#d-dist").oninput = e => { dist = +e.target.value; s.querySelector("#d-dv").textContent = dist + " m"; };
    s.querySelector("#d-start").onclick = () => { post("/api/sim/start", { scenario, appliance, distance: dist, interval }); closeSheet(); };
    s.querySelector("#d-stop").onclick = () => post("/api/sim/stop");
    s.querySelector("#d-reset").onclick = () => post("/api/sim/reset");
  });
}
if (MODE === "operator") getJSON("/api/sim/options").then(o => { appliances = o.appliances; if (appliances.includes("Heater")) appliance = "Heater"; }).catch(() => {});

/* ======================= render ======================= */
let note = null;                                  // temporary line shown after tapping the orb
$("orb").addEventListener("click", () => {
  const v = live.last && live.last.view; orb.pulse(); if (navigator.vibrate) navigator.vibrate(12);
  if (!v) return;
  const n = TILES.filter(t => t.pct ? t.pct(v) < 35 : (v.volt >= 207 && v.volt <= 253)).length;
  note = { text: v.state === "NORMAL" ? `Checked just now. ${n} of ${TILES.length} sensors read normal.` : `Checked just now. ${TILES.length - n} of ${TILES.length} sensors need a look.`, until: Date.now() + 3500 };
  render(live.last);
  setTimeout(() => live.last && render(live.last), 3600);
});
$("backLive").onclick = () => live.setScrub(null);

function render(m) {
  live.last = m;
  $("offline").style.display = m.offline ? "block" : "none";
  const v = m.view, state = v ? v.state : "NORMAL";
  root.dataset.state = state; orb.set(state); mini.set(state);
  const c = COPY[state];
  $("word").textContent = v ? c.word : "Waiting";
  $("sub").textContent = note && Date.now() < note.until ? note.text : (v ? c.sub : "Nothing has reported yet.");
  $("todo").hidden = !STEPS[state];
  $("homeName").textContent = v ? (MODE === "operator" ? v.unit_id : "Your home") : "Your home";
  $("banner").classList.toggle("on", m.replay);
  if (m.replay && v) $("bannerText").textContent = `Replaying ${clock(v.time)}`;
  document.title = (m.latest && m.latest.state !== "NORMAL" ? COPY[m.latest.state].word + " - " : "") + "Fuzz";
  renderKnowing(v, state, m);
  renderTiles(v, m);
  renderHistory(m);
  renderUnits(m);
  if (MODE === "operator" && $("d-prog") && m.run) {
    $("d-prog").style.width = (m.run.running || m.run.t > 0 ? Math.min(100, m.run.t / m.run.duration * 100) : 0) + "%";
    const nm = (SCN.find(x => x[0] === m.run.scenario) || [0, ""])[1];
    $("d-txt").textContent = m.run.running ? `Running: ${nm}, ${Math.round(m.run.t)} of ${m.run.duration} seconds` : (m.run.scenario ? `Finished: ${nm}.` : "Pick a scenario and press Start.");
  }
  notify(m);
}

function renderKnowing(v, state, m) {
  const box = $("knowing"); box.replaceChildren();
  if (!v || state === "NORMAL") return;
  const ai = v.ai || {};
  const f = el("div", "card found"); f.append(el("h3", "", "What Fuzz found"), el("p", "", cleanMessage(v.message))); box.append(f);
  if (ai.distance) {
    const d = ai.distance, pos = x => clamp((x - 1) / 19 * 100, 0, 100) + "%", wide = d.hi - d.lo > 12;
    const w = el("div", "card");
    w.innerHTML = `<h3>Where</h3><div class="where-big">${wide ? d.zone.charAt(0).toUpperCase() + d.zone.slice(1) : `About ${d.m.toFixed(0)} m from the board`}</div>
      <div class="where-track" style="margin-top:14px"><div class="where-range" style="left:${pos(d.lo)};width:${(d.hi - d.lo) / 19 * 100}%"></div><div class="where-dot" style="left:${pos(d.m)}"></div></div>
      <div class="where-axis"><span>Board</span><span>Far end</span></div>
      <p class="muted small" style="margin-top:8px">Best guess ${d.m.toFixed(0)} m, likely between ${d.lo.toFixed(0)} and ${d.hi.toFixed(0)} m.${MODE === "operator" && v.sim_truth && v.sim_truth.scenario === "arc" ? ` Simulated truth: ${v.sim_truth.distance_m} m.` : ""}</p>`;
    box.append(w);
  }
  if (ai.appliances) {
    const a = el("div", "card"); a.append(el("h3", "", "Probably plugged in"));
    ai.appliances.forEach(x => { const r = el("div", "load"); r.append(el("b", "", x.name), el("span", "muted", Math.round(x.p * 100) + "%")); const b = el("div", "bar"), i = el("i"); i.style.width = x.p * 100 + "%"; b.append(i); r.append(b); a.append(r); });
    a.append(Object.assign(el("p", "muted small", `Looks like ${FAMILY_TEXT[ai.family.name] || ai.family.name}. Assumes one appliance; the family is right about 89% of the time on unseen houses.`), { style: "margin-top:10px" }));
    box.append(a);
  }
}

function renderTiles(v, m) {
  if (!v) return;
  const off = v.relay === "OPEN", hist = m.hist.slice(-60);
  TILES.forEach(t => {
    const T = tiles[t.k]; let p, cls, word;
    if (t.k === "volt") { const bad = v.volt !== 0 && (v.volt < 207 || v.volt > 253); p = off ? 0 : bad ? 100 : 18; cls = off ? "off" : bad ? "hi" : ""; word = off ? "Circuit off" : bad ? "Out of range" : "Normal"; }
    else { p = t.pct(v); cls = off ? "off" : p >= 80 ? "hi" : p >= 35 ? "mid" : ""; word = off ? "Circuit off" : p >= 80 ? "High" : p >= 35 ? "Raised" : "Normal"; }
    T.b.className = "tile" + (t.wide ? " wide " : " ") + cls;
    T.st.textContent = word; T.val.firstChild.textContent = t.val(v);
    T.fg.setAttribute("stroke-dasharray", `${clamp(p, 4, 100) / 100 * 119.4} 120`);
    const vals = hist.map(r => t.k === "volt" ? (r.volt === 0 ? 0 : clamp(50 + (r.volt - 230) * 2, 0, 100)) : clamp(t.pct(r), 0, 100));
    T.spark.setAttribute("points", vals.map((y, i) => `${(i / Math.max(1, vals.length - 1) * 118 + 1).toFixed(1)},${(41 - y / 100 * 38).toFixed(1)}`).join(" "));
  });
}

/* ---------- history: smooth area chart, drag to replay ---------- */
const strip = $("strip"); let dragging = false;
function histPath(h) {
  const n = h.length; if (n < 2) return ["", ""];
  const X = i => i / (n - 1) * 300, Y = r => 104 - clamp(riskOf(r), 0, 120) / 120 * 96;
  let d = `M${X(0)} ${Y(h[0]).toFixed(1)}`;
  for (let i = 1; i < n; i++) { const x0 = X(i - 1), x1 = X(i), y0 = Y(h[i - 1]), y1 = Y(h[i]), mx = (x0 + x1) / 2; d += ` C${mx.toFixed(1)} ${y0.toFixed(1)} ${mx.toFixed(1)} ${y1.toFixed(1)} ${x1.toFixed(1)} ${y1.toFixed(1)}`; }
  return [d, d + " L300 110 L0 110 Z"];
}
function renderHistory(m) {
  const [line, area] = histPath(m.hist); $("line").setAttribute("d", line); $("area").setAttribute("d", area);
  $("limit").setAttribute("y1", 104 - 100 / 120 * 96); $("limit").setAttribute("y2", 104 - 100 / 120 * 96);
  const on = m.idx !== null && m.hist.length > 1; strip.classList.toggle("on", on);
  if (on) $("head").style.left = (m.idx / (m.hist.length - 1) * 100) + "%";
  const v = m.view; $("trLabel").textContent = m.replay ? "Replaying" : "Live"; $("trTime").textContent = v ? clock(v.time) : "-";
  $("hint").textContent = m.replay ? "Let go to return to live." : "Drag across the timeline to see how your home looked a moment ago.";
  const ev = $("events"); ev.replaceChildren();
  const items = m.hist.filter((r, i) => i === 0 || r.state !== m.hist[i - 1].state).reverse();
  if (!items.length) ev.append(el("li", "muted", "Nothing yet."));
  items.forEach(r => { const li = el("li"), t = el("div"); li.append(el("span", "dot " + r.state)); t.append(el("time", "", clock(r.time)), el("b", "", COPY[r.state].word + ". "), document.createTextNode(cleanMessage(r.message) || COPY[r.state].sub)); li.append(t); ev.append(li); });
}
const idxAt = e => { const r = strip.getBoundingClientRect(), n = live.last ? live.last.hist.length : 0; return n ? Math.round(clamp((e.clientX - r.left) / r.width, 0, 1) * (n - 1)) : null; };
strip.addEventListener("pointerdown", e => { strip.setPointerCapture(e.pointerId); dragging = true; const i = idxAt(e); if (i !== null) live.setScrub(i); });
strip.addEventListener("pointermove", e => { if (dragging) { const i = idxAt(e); if (i !== null) live.setScrub(i); } });
const release = () => { if (dragging) { dragging = false; live.setScrub(null); } };
strip.addEventListener("pointerup", release); strip.addEventListener("pointercancel", release);

function renderUnits(m) {
  if (MODE !== "operator") return;
  document.querySelectorAll(".unitchip").forEach(x => x.remove());
  if (m.units.length > 1) m.units.forEach(u => { const b = el("button", "chip btn unitchip", u.unit_id); b.style.fontWeight = m.latest && u.unit_id === m.latest.unit_id ? 700 : 500; b.onclick = () => live.setUnit(u.unit_id); $("actions").prepend(b); });
}

let lastState = null;
function notify(m) {
  const cur = m.latest && m.latest.state;
  if (lastState !== null && cur !== lastState && cur !== "NORMAL") {
    if (navigator.vibrate) navigator.vibrate([200, 100, 200]);
    try { if (MODE === "client" && Notification.permission === "granted") new Notification("Fuzz: " + COPY[cur].word, { body: cleanMessage(m.latest.message) }); } catch (e) {}
  }
  lastState = cur;
}

live.onUpdate(render);
live.start();
