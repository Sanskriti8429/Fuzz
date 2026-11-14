import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import precision_recall_fscore_support

z = np.load("ml/data/plaid_aggregated_windows.npz", allow_pickle=True)
X, Y, REC, NACT = z["X"][:, :-1], z["Y"], z["REC"], z["NACT"]
types = list(z["types"])

test = ((REC - 1) // 20) % 4 == 0
print("train windows", (~test).sum(), " test windows", test.sum(),
      " test records", len(set(REC[test])))

rf = RandomForestClassifier(n_estimators=300, random_state=0, n_jobs=-1)
rf.fit(X[~test], Y[~test])

cols = []
for p, c in zip(rf.predict_proba(X[test]), rf.classes_):
    cols.append(p[:, list(c).index(1)] if 1 in c else np.zeros(len(p)))
P = np.column_stack(cols)
Yt, K = Y[test], NACT[test]
pred = (P >= 0.5).astype(int)

prec, rec, f1, sup = precision_recall_fscore_support(Yt, pred, zero_division=0)
print("\nper appliance type (threshold 0.5):")
print(f"  {'type':26s} {'F1':>5s} {'prec':>5s} {'recall':>6s} {'n':>5s}")
for t, a, b, c, n in zip(types, f1, prec, rec, sup):
    print(f"  {t:26s} {a:5.2f} {b:5.2f} {c:6.2f} {n:5d}")
print(f"  macro F1: {f1.mean():.3f}")

print("\nby number of appliances running:")
for k in sorted(set(K.tolist())):
    m = K == k
    exact = (pred[m] == Yt[m]).all(axis=1).mean()
    hits = []
    for row in range(m.sum()):
        top = np.argsort(-P[m][row])[:k]
        hits.append(Yt[m][row][top].sum() / k)
    print(f"  {k} running ({m.sum():4d} windows): exact set match {exact:.2f} | "
          f"true appliances found in top-{k}: {np.mean(hits):.2f}")