"""Which di/dt rule leaves real appliances alone?  Scores candidate rules on COOLL (normal appliance use only).

A rule fires when, inside one 20 ms mains cycle, at least N current steps (10 us apart) are faster than T kA/s.
With blanking on, the first 3 cycles after a large jump in load current (switch-on) are ignored.
A good rule fires on none of the normal recordings; separately it must still fire on real arc recordings
(see arc_fires() below, which takes any current array sampled at fs).

Run from the repository root:
    python ml/cooll_didt_rules.py ml/data/cooll
Writes ml/results/cooll_didt_rules.csv and prints the fraction of recordings that fire, per appliance type.
"""
import sys, re, csv, pathlib, itertools
import numpy as np
from cooll_didt_check import read_flac, FS

T_GRID = [16.5, 25, 40, 60, 100]      # kA/s
N_GRID = [1, 3, 5, 10]                 # fast steps per 20 ms cycle
BLANK_CYCLES = 3
W = FS // 50

def cycle_counts(x, T):
    """Number of steps faster than T kA/s in each consecutive 20 ms cycle."""
    s = np.abs(np.diff(x)) * FS / 1e3
    n = len(s) // W
    return (s[: n * W].reshape(n, W) > T).sum(axis=1)

def cycle_rms(x):
    n = len(x) // W
    return np.sqrt((x[: n * W].reshape(n, W) ** 2).mean(axis=1))

def blank_mask(x):
    """True for cycles to ignore: BLANK_CYCLES cycles after any cycle whose RMS jumps by more than 3 A."""
    r = cycle_rms(x); m = np.zeros(len(r), bool)
    for i in np.where(np.diff(r, prepend=r[0]) > 3.0)[0]:
        m[i: i + 1 + BLANK_CYCLES] = True
    return m

def fires(x, T, N, blank):
    c = cycle_counts(x, T)
    if blank:
        c = np.where(blank_mask(x)[: len(c)], 0, c)
    return bool((c >= N).any())

def arc_fires(x, T=40, N=3, blank=True):
    """Use on a real arc recording (current in amps, sampled at FS) to check the same rule still catches arcs."""
    return fires(np.asarray(x, float), T, N, blank)

def main(folder):
    d = pathlib.Path(folder)
    scales = [float(l.split()[0]) for l in open(d / "scaleFactors.txt") if l.strip()]
    names = {}
    for l in open(d / "appliances_and_action_delays.txt"):
        m = re.match(r"(\d+):\s*(.+)_(\d+)_(\d+)ms", l.strip())
        if m: names[int(m.group(1))] = m.group(2)
    res = {}                                   # (T, N, blank) -> {appliance: [fired, total]}
    for f in sorted(d.glob("scenarioC1_*.flac"), key=lambda p: int(p.stem.split("_")[1])):
        i = int(f.stem.split("_")[1]); x = read_flac(f) * scales[i - 1]
        if np.sqrt((x ** 2).mean()) < 0.02: continue
        for T, N, bl in itertools.product(T_GRID, N_GRID, (False, True)):
            cell = res.setdefault((T, N, bl), {}).setdefault(names.get(i, "?"), [0, 0])
            cell[0] += fires(x, T, N, bl); cell[1] += 1
    out = pathlib.Path("ml/results"); out.mkdir(parents=True, exist_ok=True)
    with open(out / "cooll_didt_rules.csv", "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["T_kA_s", "N_per_cycle", "blanking", "appliance", "fired", "recordings"])
        for (T, N, bl), per in res.items():
            for a, (k, n) in sorted(per.items()): w.writerow([T, N, bl, a, k, n])
    tot = lambda per: (sum(v[0] for v in per.values()), sum(v[1] for v in per.values()))
    print("normal recordings that fire (lower is better; each cell = fired / total)")
    print(f"{'T kA/s':>7}{'N':>4}{'blank':>7}{'fired':>8}{'worst appliance type':>32}")
    for (T, N, bl), per in sorted(res.items()):
        k, n = tot(per); worst = max(per.items(), key=lambda kv: kv[1][0] / kv[1][1])
        print(f"{T:7}{N:4}{str(bl):>7}{f'{k}/{n}':>8}{f'{worst[0]} {worst[1][0]}/{worst[1][1]}':>32}")

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "ml/data/cooll")
