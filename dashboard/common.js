const STATES = {
  NORMAL: { word: "Normal", sub: "Fuzz is watching this circuit.", pill: "Normal" },
  WARNING: { word: "Warning", sub: "Fuzz is picking up signs of a developing fault.", pill: "Warning" },
  TRIP: { word: "Power off", sub: "Switched off to keep you safe.", pill: "Power cut" },
};
const FAMILY_TEXT = { heating: "a heating appliance", motor: "a motor-driven appliance", electronics: "an electronic device", microwave: "the microwave" };

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

/* channel percentages of the trip limit, shared by the scene and the panel */
const CHANNELS = [
  { k: "rf", name: "RF arc", unit: "", pct: r => r.rf / 0.8 * 100, val: r => r.rf.toFixed(2) },
  { k: "leak", name: "Leakage", unit: "mA", pct: r => r.leak_ma / 30 * 100, val: r => r.leak_ma.toFixed(1) },
  { k: "didt", name: "Current spikes", unit: "", pct: r => r.didt * 100, val: r => r.didt.toFixed(2) },
  { k: "temp", name: "Temperature", unit: "°C", pct: r => Math.max(0, (r.temp_c - 40) / 40 * 100), val: r => r.temp_c.toFixed(1) },
];
function riskOf(r) { return Math.max(...CHANNELS.map(c => c.pct(r))); }

/* polls the backend; owns the selected unit and the replay (scrub) position */
class Live {
  constructor(opts = {}) {
    this.unit = opts.unit || null; this.withRun = !!opts.withRun; this.scrub = null;
    this.cb = []; this.cache = null; this.offline = false;
  }
  onUpdate(f) { this.cb.push(f); }
  start() { this.tick(); setInterval(() => this.tick(), 600); }
  async tick() {
    try {
      const units = (await getJSON("/api/units")).sort((a, b) => a.unit_id.localeCompare(b.unit_id));
      let r = units.find(u => u.unit_id === this.unit) || units[0] || null;
      const hist = r ? await getJSON("/api/history/" + encodeURIComponent(r.unit_id)) : [];
      const run = this.withRun ? await getJSON("/api/sim/status") : null;
      this.cache = { units, latest: r, hist, run }; this.offline = false;
    } catch (e) { this.offline = true; }
    this.emit();
  }
  setScrub(i) { this.scrub = i; this.emit(); }
  setUnit(u) { this.unit = u; this.tick(); }
  emit() {
    const c = this.cache || { units: [], latest: null, hist: [], run: null };
    const n = c.hist.length;
    let view = c.latest, idx = null;
    if (this.scrub !== null && n) { idx = Math.max(0, Math.min(n - 1, this.scrub)); view = c.hist[idx]; }
    const m = { ...c, view, idx, replay: idx !== null && idx !== n - 1, offline: this.offline };
    this.cb.forEach(f => f(m));
  }
}
