const ICON = { NORMAL: "●", WARNING: "▲", TRIP: "■" };
const LABEL = { NORMAL: "Normal", WARNING: "Warning", TRIP: "Power cut" };

async function getJSON(url) {
  const r = await fetch(url, { cache: "no-store" });
  if (!r.ok) throw new Error(url + " " + r.status);
  return r.json();
}

function badge(state) {
  const b = document.createElement("span");
  b.className = "badge " + state;
  b.textContent = (ICON[state] || "?") + " " + (LABEL[state] || state);
  return b;
}

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}

function clock(iso) {
  const d = new Date(iso);
  return isNaN(d) ? "" : d.toLocaleTimeString();
}
