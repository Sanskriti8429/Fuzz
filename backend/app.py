import importlib.util, json, os, threading
import numpy as np
import joblib
from flask import Flask, jsonify, request, send_from_directory

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS = os.path.join(HERE, "models")

DASH = os.path.join(HERE, "..", "dashboard")
app = Flask(__name__, static_folder=DASH, static_url_path="/s")
latest = {}          # unit_id -> most recent reading (with model output)
history = {}         # unit_id -> last 300 readings
last_live = {}       # unit_id -> model output and reason from the last reading while the circuit was live

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


@app.get("/")
def operator_page():
    return send_from_directory(DASH, "console.html")


@app.get("/client")
def client_page():
    return send_from_directory(DASH, "app.html")


lock = threading.Lock()


def ingest(r):
    uid = r["unit_id"]
    state = r.get("state", "NORMAL")
    live = r.get("volt", 0) > 0 and r.get("relay") != "OPEN"
    with lock:
        if live:
            last_live[uid] = dict(ai=infer(r), reason=dominant_channel(r))
        ctx = last_live.get(uid, dict(ai={}, reason=None))
        r["ai"] = ctx["ai"] if state != "NORMAL" else {}
        r["message"] = write_message(state, ctx["reason"], ctx["ai"])
        r.pop("appliance_features", None)
        latest[uid] = r
        history.setdefault(uid, []).append(r)
        history[uid] = history[uid][-300:]


@app.post("/api/telemetry")
def telemetry():
    ingest(request.get_json())
    return jsonify(ok=True)


@app.get("/api/units")
def units():
    return jsonify(list(latest.values()))


@app.get("/api/history/<uid>")
def hist(uid):
    return jsonify(history.get(uid, []))



# ------------------------------------------------------------------ demo runner (plays the ESP32 inside the server)
_spec = importlib.util.spec_from_file_location("fuzz_sim", os.path.join(HERE, "..", "demo", "simulator.py"))
sim = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sim)

SCENARIOS = ["normal", "arc", "leakage", "overheat", "surge"]
DEMO_UNIT = "fuzz-01"
run_state = dict(running=False, t=0, duration=60, scenario=None, stop=None, thread=None)


def appliance_names():
    try:
        return list(json.load(open(sim.BANK))["appliance"].keys())
    except OSError:
        return []


def clear_unit(uid):
    with lock:
        for d in (latest, history, last_live):
            d.pop(uid, None)


def stop_run():
    if run_state["stop"] is not None:
        run_state["stop"].set()
    if run_state["thread"] is not None:
        run_state["thread"].join(timeout=3)
    run_state.update(running=False, stop=None, thread=None)


def play(scenario, distance, appliance, interval, duration, stop):
    try:
        for payload in sim.run(scenario, distance, appliance, duration, DEMO_UNIT):
            if stop.is_set():
                break
            ingest(payload)
            run_state["t"] = payload["sim_truth"]["t"]
            stop.wait(interval)
    finally:
        if run_state["stop"] is stop:
            run_state["running"] = False


@app.get("/api/sim/options")
def sim_options():
    return jsonify(scenarios=SCENARIOS, appliances=appliance_names(), unit=DEMO_UNIT)


@app.get("/api/sim/status")
def sim_status():
    return jsonify({k: run_state[k] for k in ("running", "t", "duration", "scenario")})


@app.post("/api/sim/start")
def sim_start():
    b = request.get_json() or {}
    scenario = b.get("scenario", "normal")
    if scenario not in SCENARIOS:
        return jsonify(error="unknown scenario"), 400
    names = appliance_names()
    appliance = b.get("appliance") or (names[0] if names else "heater")
    distance = min(20.0, max(1.0, float(b.get("distance", 10))))
    interval = min(2.0, max(0.1, float(b.get("interval", 0.5))))
    stop_run()
    clear_unit(DEMO_UNIT)
    stop = threading.Event()
    run_state.update(running=True, t=0, duration=60, scenario=scenario, stop=stop)
    t = threading.Thread(target=play, args=(scenario, distance, appliance, interval, 60.0, stop), daemon=True)
    run_state["thread"] = t
    t.start()
    return jsonify(ok=True)


@app.post("/api/sim/stop")
def sim_stop():
    stop_run()
    return jsonify(ok=True)


@app.post("/api/sim/reset")
def sim_reset():
    stop_run()
    clear_unit(DEMO_UNIT)
    run_state.update(t=0, scenario=None)
    return jsonify(ok=True)


if __name__ == "__main__":
    app.run(port=5000)
