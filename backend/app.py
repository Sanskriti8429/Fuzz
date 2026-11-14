import os
import numpy as np
import joblib
from flask import Flask, jsonify, request

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS = os.path.join(HERE, "models")

app = Flask(__name__)
latest = {}
history = {}
last_live = {}

LIMITS = dict(rf=0.8, leak=30.0, didt=1.0)
CHANNEL_TEXT = dict(rf="Arc activity", leak="Leakage current", didt="Fast current spikes",
                    temp="Overheating", volt="Mains voltage out of range")
FAMILY_TEXT = dict(heating="a heating appliance", motor="a motor-driven appliance",
                   electronics="an electronic device", microwave="the microwave")


def load(name):
    path = os.path.join(MODELS, name)
    if not os.path.exists(path):
        print(f"[backend] {name} not found: run python ml\\train_models.py")
        return None
    m = joblib.load(path)
    m["model"].n_jobs = 1
    return m


APPLIANCE = load("appliance_model.joblib")
DISTANCE = load("distance_model.joblib")


def dominant_channel(r):
    if not 207.0 <= r.get("volt", 230.0) <= 253.0:
        return "volt"
    s = dict(rf=r.get("rf", 0) / LIMITS["rf"], leak=r.get("leak_ma", 0) / LIMITS["leak"],
             didt=r.get("didt", 0) / LIMITS["didt"], temp=(r.get("temp_c", 25) - 40.0) / 40.0)
    k = max(s, key=s.get)
    return k if s[k] >= 0.35 else None


def infer(r):
    out = {}
    f = r.get("appliance_features")
    if APPLIANCE and f:
        p = APPLIANCE["model"].predict_proba(np.array([f]))[0]
        top = np.argsort(p)[::-1][:3]
        out["appliances"] = [dict(name=APPLIANCE["classes"][i], p=round(float(p[i]), 3)) for i in top]
        fam = {}
        for fm, pi in zip(APPLIANCE["family"], p):
            fam[fm] = fam.get(fm, 0.0) + float(pi)
        best = max(fam, key=fam.get)
        out["family"] = dict(name=best, p=round(fam[best], 3))
    d = r.get("rf_rel_db")
    if DISTANCE and d is not None:
        m = float(DISTANCE["model"].predict(np.array([[d]]))[0])
        lo, hi = max(DISTANCE["dmin"], m - DISTANCE["q"]), min(DISTANCE["dmax"], m + DISTANCE["q"])
        zone = "nearer the board" if m < 7 else "towards the far end" if m > 14 else "around the middle of the circuit"
        out["distance"] = dict(m=round(m, 1), lo=round(lo, 1), hi=round(hi, 1), zone=zone)
    return out


def write_message(state, reason, ai):
    if state == "NORMAL":
        return "All normal."
    head = "Power cut. " if state == "TRIP" else "Warning. "
    text = CHANNEL_TEXT.get(reason, "A fault is developing") + (" detected." if reason else ".")
    if reason in ("rf", "didt"):
        if "family" in ai:
            names = ", ".join(f"{a['name']} {a['p']*100:.0f}%" for a in ai["appliances"][:2])
            text += f" The load on this circuit looks like {FAMILY_TEXT.get(ai['family']['name'], 'an appliance')} ({names})."
        if "distance" in ai:
            d = ai["distance"]
            if d["hi"] - d["lo"] > 12:
                text += f" The fault is probably {d['zone']} (estimate {d['m']:.0f} m, range {d['lo']:.0f} to {d['hi']:.0f} m)."
            else:
                text += f" Roughly {d['m']:.0f} m from the board (range {d['lo']:.0f} to {d['hi']:.0f} m)."
    return head + text


@app.post("/api/telemetry")
def telemetry():
    r = request.get_json()
    uid = r["unit_id"]
    state = r.get("state", "NORMAL")
    live = r.get("volt", 0) > 0
    if live:
        last_live[uid] = dict(ai=infer(r), reason=dominant_channel(r))
    ctx = last_live.get(uid, dict(ai={}, reason=None))
    r["ai"] = ctx["ai"] if state != "NORMAL" else {}
    r["message"] = write_message(state, ctx["reason"], ctx["ai"])
    r.pop("appliance_features", None)
    latest[uid] = r
    history.setdefault(uid, []).append(r)
    history[uid] = history[uid][-300:]
    return jsonify(ok=True)


@app.get("/api/units")
def units():
    return jsonify(list(latest.values()))


@app.get("/api/history/<uid>")
def hist(uid):
    return jsonify(history.get(uid, []))


if __name__ == "__main__":
    app.run(port=5000)