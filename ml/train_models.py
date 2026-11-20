import json, os
import numpy as np
import joblib
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import accuracy_score

from baseline_appliance_proxy import proxy_wave, shape_features, FAMILY, MIN_PER_TYPE
import distance_sim

CACHE = "ml/data/plaid_cycles_sub.npz"
OUT = "backend/models"
os.makedirs(OUT, exist_ok=True)
os.makedirs("ml/results", exist_ok=True)
rng = np.random.default_rng(1)

z = np.load(CACHE, allow_pickle=True)
C, types, locs = z["C"], z["types"], z["locs"]
names, counts = np.unique(types, return_counts=True)
keep = [n for n, c in zip(names, counts) if c >= MIN_PER_TYPE]
mask = np.isin(types, keep)
C, types, locs = C[mask], types[mask], locs[mask]
classes = sorted(keep)
y = np.array([classes.index(t) for t in types])
fam = [FAMILY[c] for c in classes]
ulocs = sorted(set(locs))
test_locs = set(ulocs[::4])
test = np.array([l in test_locs for l in locs])

P = np.array([proxy_wave(c) for c in C])
X = np.array([shape_features(p) for p in P])

# data for ml/compare.py (the model comparison): same features, same labels, house of each record
np.savez("ml/results/appliance_xy.npz", X=X, y=np.array(types, dtype=str), groups=np.array(locs, dtype=str))

rf = RandomForestClassifier(n_estimators=300, class_weight="balanced", random_state=0, n_jobs=-1)
rf.fit(X[~test], y[~test])
pred = rf.predict(X[test])
exact = accuracy_score(y[test], pred)
famacc = np.mean([fam[a] == fam[b] for a, b in zip(pred, y[test])])
top3 = np.mean([t in np.argsort(p)[::-1][:3] for t, p in zip(y[test], rf.predict_proba(X[test]))])
print(f"appliance model (trained on {(~test).sum()} records, tested on {test.sum()} records from unseen houses)")
print(f"  exact {exact:.3f}   family {famacc:.3f}   true appliance in top 3: {top3:.3f}")

joblib.dump(dict(model=rf, classes=classes, family=fam), os.path.join(OUT, "appliance_model.joblib"), compress=3)

bank_app = {}
for ci, c in enumerate(classes):
    idx = np.where(test & (y == ci))[0]
    if len(idx) == 0:
        continue
    pick = rng.choice(idx, size=min(20, len(idx)), replace=False)
    bank_app[c] = [np.round(X[i], 5).tolist() for i in pick]

Xs, ys = [], []
for x0 in (0.3, 0.6, 1.0):
    a, b = distance_sim.simulate(x0, False)
    Xs.append(a); ys.append(b)
Xd, yd = np.vstack(Xs), np.concatenate(ys)
order = rng.permutation(len(yd))
Xd, yd = Xd[order], yd[order]
n = len(yd)
tr, ca, te = slice(0, int(.6 * n)), slice(int(.6 * n), int(.8 * n)), slice(int(.8 * n), n)

# data for ml/compare.py: blocks of 40 consecutive simulated events stay together in one fold
np.savez("ml/results/distance_xy.npz", X=Xd, y=yd, groups=(np.arange(n) // 40)[order])

dr = RandomForestRegressor(n_estimators=100, min_samples_leaf=30, random_state=0, n_jobs=-1)
dr.fit(Xd[tr], yd[tr])
q = float(np.quantile(np.abs(yd[ca] - dr.predict(Xd[ca])), 0.9))
pd_ = dr.predict(Xd[te])
lo, hi = np.clip(pd_ - q, distance_sim.D_MIN, distance_sim.D_MAX), np.clip(pd_ + q, distance_sim.D_MIN, distance_sim.D_MAX)
print(f"\ndistance model (one RF band, homes at 0.3, 0.6 and 1.0 dB/m, no calibration)")
print(f"  mean error {np.abs(pd_ - yd[te]).mean():.2f} m   90% range covers {np.mean((yd[te] >= lo) & (yd[te] <= hi)):.2f}"
      f"   average range width {np.mean(hi - lo):.1f} m   (guessing the middle: 4.75 m)")

joblib.dump(dict(model=dr, q=q, dmin=distance_sim.D_MIN, dmax=distance_sim.D_MAX),
            os.path.join(OUT, "distance_model.joblib"), compress=3)

bank = dict(appliance=bank_app, dist=dict(d=np.round(yd[te], 3).tolist(), f=np.round(Xd[te][:, 0], 3).tolist()))
json.dump(bank, open(os.path.join(OUT, "demo_bank.json"), "w"))
print("\nsaved to", OUT, ":", ", ".join(sorted(os.listdir(OUT))))
