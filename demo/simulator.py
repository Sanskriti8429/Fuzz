import argparse, json, os, random, time, urllib.request
from collections import deque
from datetime import datetime, timezone

# Trip limits used by the (simulated) ESP32 fusion rule
LIM_RF = 0.8        # normalised RF detector level
LIM_LEAK = 30.0     # leakage current, mA
LIM_DIDT = 1.0      # normalised di/dt integrator level
TEMP_WARN, TEMP_TRIP = 40.0, 80.0   # degrees C (score is 0 at 40 C and 1 at 80 C)
V_MIN, V_MAX = 207.0, 253.0         # +-10% of 230 V
WARN_AVG = 0.35     # a channel counts as raised when its 5-reading average passes 35% of its limit

def ramp(t, start, rise):
    """0 before `start`, climbs linearly to 1 over `rise` seconds, then stays at 1."""
    return min(max((t - start) / rise, 0.0), 1.0)

def reading(scenario, t, distance):
    r = dict(rf=random.gauss(0.03, 0.01), leak_ma=random.gauss(2.0, 0.5),
             didt=abs(random.gauss(0.03, 0.02)), temp_c=random.gauss(32.0, 0.3),
             volt=random.gauss(230.0, 1.5))
    if scenario == "arc":
        # arcing starts at 10 s; the farther away, the weaker the RF level seen at the board
        k = ramp(t, 10, 30)
        strength = max(0.35, 1.0 - 0.025 * distance)
        r["rf"] += k * strength * random.uniform(0.5, 1.0)
        if k > 0.2 and random.random() < 0.6:
            r["didt"] += k * random.uniform(0.3, 0.8)          # arc flicker
        if k > 0.85 and random.random() < 0.1:
            r["didt"] += random.uniform(0.6, 1.0)              # occasional hard spike
        r["temp_c"] += 6 * k
    elif scenario == "leakage":
        r["leak_ma"] += 38 * ramp(t, 10, 25)
    elif scenario == "overheat":
        r["temp_c"] += 55 * ramp(t, 10, 30)
        r["rf"] += 0.2 * ramp(t, 25, 10)
    elif scenario == "surge":
        if t > 10:
            r["volt"] += 35
    return {k: round(v, 3) for k, v in r.items()}

def scores_of(r):
    return dict(rf=r["rf"] / LIM_RF, leak=r["leak_ma"] / LIM_LEAK, didt=r["didt"] / LIM_DIDT,
                temp=(r["temp_c"] - TEMP_WARN) / (TEMP_TRIP - TEMP_WARN))

def fuse(r, window, tripped):
    """TRIP on any instantaneous limit; WARNING when two channels are raised on average over the last 5 s."""
    now = scores_of(r)
    window.append(now)
    avg = {k: sum(w[k] for w in window) / len(window) for k in now}
    volt_bad = not (V_MIN <= r["volt"] <= V_MAX)
    if tripped or any(s >= 1.0 for s in now.values()):
        return "TRIP"
    if sum(s >= WARN_AVG for s in avg.values()) >= 2 or max(now.values()) >= 0.8 or volt_bad:
        return "WARNING"
    return "NORMAL"

BANK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend", "models", "demo_bank.json")

def load_bank(appliance, distance):
    """Pick the (fixed) appliance feature vector and RF level for this run from the saved demo bank."""
    if not os.path.exists(BANK):
        print("demo_bank.json not found: run python ml\\train_models.py first. Running without model inputs.")
        return None, None, None
    bank = json.load(open(BANK))
    want = appliance.lower().replace("-", " ").replace("_", " ")
    hits = [c for c in bank["appliance"] if c.lower().startswith(want)]
    if len(hits) != 1:
        raise SystemExit(f"--appliance must match exactly one of: {', '.join(bank['appliance'])}")
    feats = random.choice(bank["appliance"][hits[0]])
    d, f = bank["dist"]["d"], bank["dist"]["f"]
    near = [i for i in range(len(d)) if abs(d[i] - distance) <= 1.0] or [min(range(len(d)), key=lambda i: abs(d[i] - distance))]
    return hits[0], feats, f[random.choice(near)]

def post(url, payload):
    req = urllib.request.Request(url, json.dumps(payload).encode(), {"Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=5).read()

def run(scenario, distance=10.0, appliance="heater", duration=60.0, unit="fuzz-01"):
    """Generator: yields one telemetry payload per simulated second."""
    appliance, app_feats, rf_rel = load_bank(appliance, distance)
    tripped, t, warn_until = False, 0.0, -1.0
    window = deque(maxlen=5)
    while t <= duration:
        r = reading(scenario, t, distance)
        state = fuse(r, window, tripped)
        if state == "WARNING":
            warn_until = t + 10          # hold a warning for 10 s so it does not flicker
        elif state == "NORMAL" and t < warn_until:
            state = "WARNING"
        tripped = tripped or state == "TRIP"
        if tripped:                       # relay open: the circuit is dead
            r.update(rf=0.0, leak_ma=0.0, didt=0.0, volt=0.0)
        payload = dict(unit_id=unit, time=datetime.now(timezone.utc).isoformat(), state=state,
                       relay="OPEN" if tripped else "CLOSED", **r,
                       sim_truth=dict(scenario=scenario, distance_m=distance, appliance=appliance, t=t))
        if app_feats and not tripped:
            payload["appliance_features"] = app_feats
            if scenario == "arc" and r["rf"] > 0.15:
                payload["rf_rel_db"] = round(rf_rel + random.gauss(0, 1.0), 2)
        yield payload
        t += 1.0

def main():
    p = argparse.ArgumentParser()
    p.add_argument("scenario", choices=["normal", "arc", "leakage", "overheat", "surge"])
    p.add_argument("--distance", type=float, default=10.0, help="arc distance in metres (truth, for testing)")
    p.add_argument("--appliance", default="heater", help="what is running on the circuit (prefix of a PLAID type name)")
    p.add_argument("--unit", default="fuzz-01")
    p.add_argument("--duration", type=float, default=60.0)
    p.add_argument("--interval", type=float, default=1.0)
    p.add_argument("--url", default="http://127.0.0.1:5000/api/telemetry")
    a = p.parse_args()

    for payload in run(a.scenario, a.distance, a.appliance, a.duration, a.unit):
        post(a.url, payload)
        t = payload["sim_truth"]["t"]
        print(f"t={t:5.1f}s  {payload['state']:8s} rf={payload['rf']:.2f} leak={payload['leak_ma']:5.1f}mA "
              f"didt={payload['didt']:.2f} temp={payload['temp_c']:.1f}C volt={payload['volt']:.0f}V")
        if t % 10 < 1:
            print("   ", json.loads(urllib.request.urlopen(a.url.replace("telemetry", "units")).read())[0]["message"])
        time.sleep(a.interval)

if __name__ == "__main__":
    main()
