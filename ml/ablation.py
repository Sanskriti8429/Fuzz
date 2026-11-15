"""Channel ablation for the fusion rule: switch off one sensor at a time and replay every fault scenario.

The fusion rule is hand-written, not trained, so "removing a sensor" means ignoring that channel and running the
same simulated scenarios again. For each scenario and each missing sensor this reports how often the fault is still
caught, how often the relay still trips, and how much warning time the user gets before the trip.

Run from the repository root:  python ml\\ablation.py
"""
import importlib.util, json, os, random
from collections import deque
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("fuzz_sim", os.path.join(HERE, "..", "demo", "simulator.py"))
sim = importlib.util.module_from_spec(spec); spec.loader.exec_module(sim)

CHANNELS = ["rf", "leak", "didt", "temp", "volt"]
SCENARIOS = ["arc", "leakage", "overheat", "surge"]
RUNS, DURATION, DISTANCE = 100, 60, 12.0


def fuse(r, window, tripped, off):
    now = sim.scores_of(r)
    for c in off:
        if c in now:
            now[c] = 0.0                                       # a missing channel contributes nothing
    window.append(now)
    avg = {k: sum(w[k] for w in window) / len(window) for k in now}
    volt_bad = "volt" not in off and not (sim.V_MIN <= r["volt"] <= sim.V_MAX)
    if tripped or any(s >= 1.0 for s in now.values()):
        return "TRIP"
    if sum(s >= sim.WARN_AVG for s in avg.values()) >= 2 or max(now.values()) >= 0.8 or volt_bad:
        return "WARNING"
    return "NORMAL"


def one_run(scenario, off, seed):
    random.seed(seed)
    window, tripped, warn_until, first_warn, first_trip = deque(maxlen=5), False, -1.0, None, None
    for t in range(DURATION + 1):
        r = sim.reading(scenario, float(t), DISTANCE)
        state = fuse(r, window, tripped, off)
        if state == "WARNING":
            warn_until = t + 10
        elif state == "NORMAL" and t < warn_until:
            state = "WARNING"
        if state != "NORMAL" and first_warn is None:
            first_warn = t
        if state == "TRIP":
            tripped = True
            if first_trip is None:
                first_trip = t
        if tripped:
            break
    return first_warn, first_trip


rows = []
print(f"{RUNS} runs per cell, fault {DISTANCE:.0f} m away, {DURATION} s per run. 'caught' = warning or trip, 'trip' = relay opened.\n")
for scenario in ["normal"] + SCENARIOS:
    print(scenario)
    for off in [()] + [(c,) for c in CHANNELS]:
        res = [one_run(scenario, off, 1000 * (["normal"] + SCENARIOS).index(scenario) + i) for i in range(RUNS)]
        caught = np.mean([w is not None for w, _ in res])
        trip = np.mean([t is not None for _, t in res])
        leads = [t - w for w, t in res if w is not None and t is not None]
        warned_first = np.mean([t - w > 0 for w, t in res if w is not None and t is not None]) if leads else float("nan")
        lead = float(np.median(leads)) if leads else float("nan")
        label = "all five channels" if not off else f"without {off[0]}"
        rows.append(dict(scenario=scenario, removed=off[0] if off else None, caught=caught, trip=trip, lead_s=lead, warned_before_trip=warned_first))
        if scenario == "normal":
            print(f"  {label:20s} false alarms in {caught*100:4.0f}% of runs")
        else:
            lead_txt = f"{lead:4.0f} s median warning before the trip" if leads else "no trip"
            print(f"  {label:20s} caught {caught*100:4.0f}%   trip {trip*100:4.0f}%   {lead_txt}")
    print()

os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
json.dump(rows, open(os.path.join(HERE, "results", "ablation.json"), "w"), indent=2)
print("saved ml/results/ablation.json")
