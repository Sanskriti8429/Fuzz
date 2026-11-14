import json, re, collections
import numpy as np
from appliance_features import features

BASE = "ml/data/plaid/"
OUT = "ml/data/plaid_aggregated_windows.npz"
WIN = 30500
MARGIN = 15000
MAX_PER_INTERVAL = 3

def read_csv(path):
    with open(path) as f:
        a = np.fromstring(f.read().replace(",", " "), sep=" ")
    a = a.reshape(-1, 2)
    return a[:, 0], a[:, 1]

def numbers(s):
    return [int(x) for x in re.findall(r"\d+", str(s))]

meta = json.load(open(BASE + "metadata_aggregated.json"))
all_types = sorted({a["type"] for m in meta.values() for a in m["appliances"]})
print("types:", all_types)

X, Y, REC, NACT = [], [], [], []
skipped = 0
for k, m in meta.items():
    apps = []
    for a in m["appliances"]:
        on_t, off_t = numbers(a.get("on")), numbers(a.get("off"))
        if not on_t or not off_t:
            apps = None
            break
        apps.append((a["type"], min(on_t), max(off_t), on_t + off_t))
    if not apps:
        skipped += 1
        continue
    i, v = read_csv(BASE + f"aggregated/{k}.csv")
    n = len(i)
    cuts = sorted({0, n} | {t for _, _, _, ev in apps for t in ev if t < n})
    for t0, t1 in zip(cuts[:-1], cuts[1:]):
        active = [t for t, on, off, _ in apps if on <= t0 and off >= t1]
        if not active:
            continue
        start, taken = t0 + MARGIN, 0
        while start + WIN <= min(t1, n) and taken < MAX_PER_INTERVAL:
            try:
                f = features(i[start:start + WIN], v[start:start + WIN])
            except Exception:
                break
            y = np.zeros(len(all_types), int)
            for t in active:
                y[all_types.index(t)] = 1
            X.append(f); Y.append(y); REC.append(int(k)); NACT.append(len(active))
            start += WIN
            taken += 1

X, Y, REC, NACT = np.array(X), np.array(Y), np.array(REC), np.array(NACT)
np.savez(OUT, X=X, Y=Y, REC=REC, NACT=NACT, types=np.array(all_types))

print("\nwindows:", len(X), " records used:", len(set(REC)), " records skipped:", skipped)
print("appliances running at once:", dict(sorted(collections.Counter(NACT.tolist()).items())))
print("windows containing each type:")
for t, n in zip(all_types, Y.sum(axis=0)):
    print(f"  {n:5d}  {t}")