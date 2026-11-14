import json, os
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import precision_recall_fscore_support
from appliance_features import features

BASE = "ml/data/plaid/"
CACHE = "ml/data/plaid_aligned_sub.npz"
MIN_PER_TYPE = 75
N_SYNTH = 6000
CYCLE, NCYC = 500, 60
SEG = CYCLE * NCYC

def read_csv(path):
    with open(path) as f:
        a = np.fromstring(f.read().replace(",", " "), sep=" ")
    a = a.reshape(-1, 2)
    return a[:, 0], a[:, 1]

meta = json.load(open(BASE + "metadata_submetered.json"))

if os.path.exists(CACHE):
    z = np.load(CACHE, allow_pickle=True)
    A, T = z["A"], z["T"]
else:
    A, T = [], []
    for k, m in meta.items():
        i, v = read_csv(BASE + f"submetered/{k}.csv")
        i, v = i[-(SEG + CYCLE):], v[-(SEG + CYCLE):]
        zc = np.where((v[:-1] < 0) & (v[1:] >= 0))[0]
        if len(zc) == 0 or zc[0] + 1 + SEG > len(i):
            continue
        A.append(i[zc[0] + 1: zc[0] + 1 + SEG].astype(np.float32))
        T.append(m["appliance"]["type"])
    A, T = np.array(A), np.array(T)
    np.savez(CACHE, A=A, T=T)

classes = sorted(c for c in set(T.tolist()) if (T == c).sum() >= MIN_PER_TYPE)
idx = {c: np.where(T == c)[0] for c in classes}
vnom = 169.7 * np.sin(2 * np.pi * (np.arange(SEG) + 0.5) / CYCLE)
rng = np.random.default_rng(0)
Xs, Ys = [], []
for _ in range(N_SYNTH):
    k = rng.choice([1, 2, 3, 4], p=[0.3, 0.4, 0.2, 0.1])
    chosen = rng.choice(len(classes), size=k, replace=False)
    i_sum = np.zeros(SEG)
    y = np.zeros(len(classes), int)
    for c in chosen:
        i_sum += A[rng.choice(idx[classes[c]])]
        y[c] = 1
    try:
        f = features(i_sum, vnom)
    except Exception:
        continue
    Xs.append(f[:-1]); Ys.append(y)
Xs, Ys = np.array(Xs), np.array(Ys)
print("synthetic training windows:", len(Xs), " classes:", len(classes))

rf = RandomForestClassifier(n_estimators=300, random_state=0, n_jobs=-1)
rf.fit(Xs, Ys)

z = np.load("ml/data/plaid_aggregated_windows.npz", allow_pickle=True)
Xr, Yr, types13 = z["X"][:, :-1], z["Y"], list(z["types"])
shared = [c for c in classes if c in types13]
nonshared = [j for j, t in enumerate(types13) if t not in classes]
ok = (Yr[:, nonshared].sum(axis=1) == 0) & (Yr.sum(axis=1) > 0)
Xr, Yr = Xr[ok], Yr[ok]
Y11 = np.zeros((len(Xr), len(classes)), int)
for c in shared:
    Y11[:, classes.index(c)] = Yr[:, types13.index(c)]
print("real test windows:", len(Xr), " shared types:", shared)

cols = []
for p, c in zip(rf.predict_proba(Xr), rf.classes_):
    cols.append(p[:, list(c).index(1)] if 1 in c else np.zeros(len(p)))
P = np.column_stack(cols)
pred = (P >= 0.5).astype(int)
sc = [classes.index(c) for c in shared]

prec, rec, f1, sup = precision_recall_fscore_support(Y11[:, sc], pred[:, sc], zero_division=0)
print("\nper shared type, trained only on synthetic mixtures:")
print(f"  {'type':26s} {'F1':>5s} {'prec':>5s} {'recall':>6s} {'n':>5s}")
for t, a, b, c, n in zip(shared, f1, prec, rec, sup):
    print(f"  {t:26s} {a:5.2f} {b:5.2f} {c:6.2f} {n:5d}")
print(f"  macro F1: {f1.mean():.3f}")
others = [j for j in range(len(classes)) if j not in sc]
print(f"windows with a false alarm for an appliance not present in this test: "
      f"{(pred[:, others].sum(axis=1) > 0).mean():.2f}")

K = Y11.sum(axis=1)
print("\nby number of appliances running:")
for k in sorted(set(K.tolist())):
    m = K == k
    exact = (pred[m] == Y11[m]).all(axis=1).mean()
    hits = [Y11[m][r][np.argsort(-P[m][r])[:k]].sum() / k for r in range(m.sum())]
    print(f"  {k} running ({m.sum():4d} windows): exact set match {exact:.2f} | "
          f"true appliances found in top-{k}: {np.mean(hits):.2f}")