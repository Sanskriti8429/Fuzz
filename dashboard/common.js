const STATES = {
  NORMAL: { word: "All good", sub: "Fuzz is watching this circuit", icon: "check", pill: "Normal" },
  WARNING: { word: "Needs attention", sub: "A fault may be developing", icon: "alert", pill: "Warning" },
  TRIP: { word: "Power is off", sub: "Switched off to keep you safe", icon: "off", pill: "Power cut" },
};
const ICONS = {
  check: '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
  alert: '<path d="M12 4l9 16H3z"/><path d="M12 10v4M12 17.2v.1"/>',
  off: '<path d="M12 3v8"/><path d="M6.3 6.6a8 8 0 1 0 11.4 0"/>',
  rf: '<path d="M5 18a9 9 0 0 1 0-12M8.5 15a5 5 0 0 1 0-6"/><circle cx="12.5" cy="12" r="1.3"/><path d="M16 9a5 5 0 0 1 0 6M19.5 6a9 9 0 0 1 0 12"/>',
  leak: '<path d="M12 3.5c3.5 4.2 6 7 6 10a6 6 0 0 1-12 0c0-3 2.5-5.8 6-10z"/>',
  didt: '<path d="M13 3L5 13.5h6L10 21l8-10.5h-6z"/>',
  temp: '<path d="M10 14.5V5a2 2 0 0 1 4 0v9.5a4 4 0 1 1-4 0z"/>',
  volt: '<path d="M9 3v5M15 3v5M6 8h12v3a6 6 0 0 1-12 0z"/><path d="M12 17v4"/>',
};
const FAMILY_TEXT = { heating: "a heating appliance", motor: "a motor-driven appliance", electronics: "an electronic device", microwave: "the microwave" };

function icon(name, size) {
  return `<svg viewBox="0 0 24 24" width="${size}" height="${size}" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[name]}</svg>`;
}
const LOGO = '<i><svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor" aria-hidden="true"><path d="M13.2 2L5 13.4h5.6L9.6 22 19 9.8h-5.7z"/></svg></i>Fuzz';

async function getJSON(url) {
  const r = await fetch(url, { cache: "no-store" });
  if (!r.ok) throw new Error(url + " " + r.status);
  return r.json();
}
async function post(url, body) {
  const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) });
  return r.json();
}
function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}
function clock(iso) { const d = new Date(iso); return isNaN(d) ? "" : d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }); }
function cleanMessage(m) { return (m || "").replace(/^(Warning|Power cut)\.\s*/, ""); }

/* status ring: build once, then update */
function mountRing(box) {
  const R = 84, C = 2 * Math.PI * R;
  box.classList.add("ring");
  box.innerHTML = `<svg class="ring-svg" viewBox="0 0 200 200" aria-hidden="true"><circle class="ring-bg" cx="100" cy="100" r="${R}"/>` +
    `<circle class="ring-fg" cx="100" cy="100" r="${R}" stroke-dasharray="0 ${C}" transform="rotate(-90 100 100)"/></svg><div class="ring-center"></div>`;
  box._C = C;
}
function setRing(box, pct, state) {
  const p = Math.max(3, Math.min(100, pct));
  box.querySelector(".ring-fg").setAttribute("stroke-dasharray", `${box._C * p / 100} ${box._C}`);
  box.classList.remove("NORMAL", "WARNING", "TRIP"); box.classList.add(state);
  const c = box.querySelector(".ring-center");
  if (c.dataset.s !== state) { c.innerHTML = icon(STATES[state].icon, 56); c.dataset.s = state; }
  box.setAttribute("role", "img"); box.setAttribute("aria-label", STATES[state].word);
}

/* where-is-the-fault graphic: board on the left, far end of the circuit on the right */
function wireHTML(d, truth) {
  const X = m => 56 + (m - 1) / 19 * 288;
  let s = '<svg class="wire" viewBox="0 0 400 120" role="img" aria-label="Estimated position of the fault along the circuit">';
  s += '<line class="w-line" x1="56" y1="66" x2="344" y2="66"/>';
  if (d) {
    s += `<line class="w-range" x1="${X(d.lo)}" y1="66" x2="${X(d.hi)}" y2="66"/>`;
    s += `<circle class="w-pt" cx="${X(d.m)}" cy="66" r="10"/>`;
  }
  if (truth != null) {
    const x = X(truth);
    s += `<path class="w-truth" d="M${x - 6} 30h12l-6 10z"/><text class="w-text" x="${x}" y="24" text-anchor="middle">simulated truth</text>`;
  }
  s += '<rect class="w-board" x="10" y="46" width="40" height="40" rx="12"/><path class="w-bolt" d="M32.5 52l-8 13h6l-2 10 8-13h-6z"/>';
  s += '<path class="w-house" d="M350 86V68l20-17 20 17v18z"/>';
  s += '<text class="w-text" x="30" y="106" text-anchor="middle">Board</text><text class="w-text" x="370" y="106" text-anchor="middle">Far end</text>';
  s += '<text class="w-text" x="56" y="106" text-anchor="start" opacity="0">1 m</text></svg>';
  return s;
}

function sparkHTML(values, color) {
  const n = values.length;
  if (n < 2) return '<svg class="spark" viewBox="0 0 120 34"></svg>';
  const pts = values.map((v, i) => `${(i / (n - 1) * 118 + 1).toFixed(1)},${(31 - Math.min(100, Math.max(0, v)) / 100 * 28).toFixed(1)}`).join(" ");
  return `<svg class="spark" viewBox="0 0 120 34" preserveAspectRatio="none" aria-hidden="true"><polyline points="${pts}" fill="none" stroke="${color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" vector-effect="non-scaling-stroke"/></svg>`;
}

function chips(box, ai) {
  box.replaceChildren();
  (ai.appliances || []).forEach(a => {
    const c = el("div", "chip"); c.append(el("b", "", a.name), el("span", "muted mono", Math.round(a.p * 100) + "%"));
    const bar = el("div", "bar"), i = el("i"); i.style.width = (a.p * 100) + "%"; bar.append(i); c.append(bar); box.append(c);
  });
}
