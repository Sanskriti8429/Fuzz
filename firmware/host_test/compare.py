"""Checks the C++ firmware logic against the Python code the models and the simulator use.
Run from the repo root:  python firmware\\host_test\\compare.py
Needs g++ (or any C++17 compiler) on the PATH."""
import os, random, subprocess, sys
from collections import deque
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path[:0] = [os.path.join(ROOT, "demo"), os.path.join(ROOT, "ml")]
import simulator as sim
from baseline_appliance_proxy import shape_features

def build(name):
    exe = os.path.join(HERE, name + (".exe" if os.name == "nt" else ""))
    subprocess.run(["g++", "-std=c++17", "-O2", "-o", exe, os.path.join(HERE, name + ".cpp")], check=True)
    return exe

def reference_states(scenario, seed, distance):
    random.seed(seed)
    rows, states = [], []
    tripped, warn_until, window = False, -1.0, deque(maxlen=5)
    for t in range(61):
        r = sim.reading(scenario, float(t), distance)
        state = sim.fuse(r, window, tripped)
        if state == "WARNING":
            warn_until = t + 10
        elif state == "NORMAL" and t < warn_until:
            state = "WARNING"
        tripped = tripped or state == "TRIP"
        rows.append(f"{t} {r['rf']} {r['leak_ma']} {r['didt']} {r['temp_c']} {r['volt']}")
        states.append({"NORMAL": 0, "WARNING": 1, "TRIP": 2}[state])
    return rows, states

def main():
    exe = build("fusion_test")
    bad = total = 0
    for scenario in ["normal", "arc", "leakage", "overheat", "surge"]:
        for seed in range(40):
            rows, ref = reference_states(scenario, seed, random.Random(seed).uniform(1, 20))
            out = subprocess.run([exe], input="\n".join(rows), capture_output=True, text=True).stdout.split()
            got = [int(x) for x in out]
            total += 1
            if got != ref:
                bad += 1
                print(f"MISMATCH {scenario} seed {seed}")
    print(f"fusion: {total - bad} of {total} runs identical to the Python rule")

    exe = build("features_test")
    rng = np.random.default_rng(0)
    xs = []
    for _ in range(50):
        t = np.arange(500) / 500 * 2 * np.pi
        x = np.clip(np.sin(t) * rng.uniform(0.05, 1.0) + sum(rng.uniform(0, .3) * np.sin(h * t + rng.normal()) for h in (2, 3, 5, 7, 9)), 0, 1.8)
        xs.append(np.round(x / 0.0008) * 0.0008)
    inp = "\n".join(" ".join(f"{v:.6f}" for v in x) for x in xs)
    out = subprocess.run([exe], input=inp, capture_output=True, text=True).stdout.strip().split("\n")
    got = np.array([[float(v) for v in line.split()] for line in out])
    ref = np.array([shape_features(np.array([float(f"{v:.6f}") for v in x])) for x in xs])
    print(f"features: largest difference between C++ and numpy over 50 waveforms = {np.abs(got - ref).max():.2e}")

if __name__ == "__main__":
    main()
