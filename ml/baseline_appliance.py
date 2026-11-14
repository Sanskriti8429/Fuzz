import json, os
import numpy as np
from xgboost import XGBClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from appliance_features import features, startup_features

BASE = "ml/data/plaid/"
CACHE = "ml/data/plaid_features_sub2.npz"
MIN_PER_TYPE = 75
USE_AMPLITUDE = False
USE_STARTUP = True

FAMILY = {
    "Heater": "heating", "Hairdryer": "heating", "Incandescent Light Bulb": "heating",
    "Air Conditioner": "motor", "Fan": "motor", "Fridge": "motor",
    "Vacuum": "motor", "Washing Machine": "motor",
    "Compact Fluorescent Lamp": "electronics", "Laptop": "electronics",
    "Microwave": "microwave",
}

def read_csv(path):
    with open(path) as f:
        a = np.fromstring(f.read().replace(",", " "), sep=" ")
    a = a.reshape(-1, 2)
    return a[:, 0], a[:, 1]

meta = json.load(open(BASE + "metadata_submetered.json"))

if os.path.exists(CACHE):
    z = np.load(CACHE, allow_pickle=True)
    F, S, types, locs = z["F"], z["S"], z["types"], z["locs"]
else:
    F, S, types, locs = [], [], [], []
    for k, m in meta.items():
        i, v = read_csv(BASE + f"submetered/{k}.csv")
        try:
            f = features(i, v)
            s = startup_features(i)
        except Exception:
            continue
        F.append(f); S.append(s)
        types.append(m["appliance"]["type"]); locs.append(m["location"])
    F, S, types, locs = np.array(F), np.array(S), np.array(types), np.array(locs)
    np.savez(CACHE, F=F, S=S, types=types, locs=locs)

X = F if USE_AMPLITUDE else F[:, :-1]
if USE_STARTUP:
    X = np.hstack([X, S])
print("features used:", X.shape[1],
      "| amplitude:", USE_AMPLITUDE, "| startup:", USE_STARTUP)

names, counts = np.unique(types, return_counts=True)
keep = [n for n, c in zip(names, counts) if c >= MIN_PER_TYPE]
mask = np.isin(types, keep)
X, types, locs = X[mask], types[mask], locs[mask]
classes = sorted(keep)
y = np.array([classes.index(t) for t in types])
fam = np.array([FAMILY[c] for c in classes])
print("records:", len(y), " types:", len(classes), " houses:", len(set(locs)))

ulocs = sorted(set(locs))
test_locs = set(ulocs[::4])
is_test = np.array([l in test_locs for l in locs])

def models():
    return {
        "Random Forest": RandomForestClassifier(n_estimators=300, class_weight="balanced",
                                                random_state=0, n_jobs=-1),
        "XGBoost": XGBClassifier(n_estimators=300, max_depth=4, learning_rate=0.1,
                                 eval_metric="mlogloss"),
    }

test = is_test
print("\nSPLIT BY HOUSE | train", (~test).sum(), "test", test.sum())
for name, model in models().items():
    model.fit(X[~test], y[~test])
    pred = model.predict(X[test])
    print(f"\n{name}: exact accuracy {accuracy_score(y[test], pred):.3f}"
          f" | family accuracy {(fam[pred] == fam[y[test]]).mean():.3f}")
    print(classification_report(y[test], pred, labels=list(range(len(classes))),
                                target_names=classes, zero_division=0))
    if name == "Random Forest":
        cm = confusion_matrix(y[test], pred, labels=list(range(len(classes))))
        short = [c[:5] for c in classes]
        print("rows = true, columns = predicted")
        print("         " + " ".join(f"{s:>5}" for s in short))
        for s, row in zip(short, cm):
            print(f"{s:>8} " + " ".join(f"{n:5d}" for n in row))