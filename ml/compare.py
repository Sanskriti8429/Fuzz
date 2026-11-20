"""Why a Random Forest?  Five other model types, tested against it on the SAME data and the SAME split.

Put this file in  ml/  and run from the repo root:

    python ml\\compare.py                       # needs the two .npz files, see "ONE-TIME SETUP"
    python ml\\compare.py --demo                # runs on stand-in random data, only to check the script works

ONE-TIME SETUP (2 lines, in ml/train_models.py, right after the appliance features X, labels y and house ids are built,
and right after the distance features and distances are built; use your own variable names):

    np.savez("ml/results/appliance_xy.npz", X=X_app, y=y_app, groups=house_id)
    np.savez("ml/results/distance_xy.npz",  X=X_dist, y=dist_m, groups=house_id_or_block_id)

X is the feature matrix the Random Forest is trained on, y the appliance label (or the distance in metres),
groups the house (or block) of each row, so that no house is ever in both the training and the test side.

Models compared with the Random Forest (appliance = classification, distance = regression).
Five well-known ones, then (unless --core) six less common ones that are genuinely reasonable on small tabular data:
    Extra Trees, single decision tree, AdaBoost, LDA / Bayesian ridge, Gaussian naive Bayes (classification only), Gaussian process.
    1  Logistic / Linear regression      (the simplest sensible model)
    2  k-Nearest Neighbours
    3  Support Vector Machine (RBF kernel)
    4  Neural network (small MLP)
    5  Gradient boosting (XGBoost if installed, else scikit-learn HistGradientBoosting)

What is measured, for every model:  accuracy / error on unseen houses, how much it drops when the features are noisy,
training time, prediction time, model file size.  Nothing here is tuned for the Random Forest: every model gets
a reasonable default setting, and all use the same GroupKFold split by house.
Results are written to  ml/results/compare_rf.json, .md and .png.
"""
import argparse, io, json, os, sys, time, warnings
import numpy as np
import joblib
from sklearn.base import clone
from sklearn.ensemble import (RandomForestClassifier, RandomForestRegressor, ExtraTreesClassifier, ExtraTreesRegressor,
                              AdaBoostClassifier, AdaBoostRegressor)
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.naive_bayes import GaussianNB
from sklearn.gaussian_process import GaussianProcessClassifier, GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF, WhiteKernel, ConstantKernel as C
from sklearn.linear_model import BayesianRidge
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import accuracy_score, f1_score, mean_absolute_error
from sklearn.model_selection import GroupKFold
from sklearn.neighbors import KNeighborsClassifier, KNeighborsRegressor
from sklearn.neural_network import MLPClassifier, MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC, SVR

warnings.filterwarnings("ignore")
SEED = 0
EXTRA = True   # set by --core
HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "results")

try:
    from xgboost import XGBClassifier, XGBRegressor
    HAVE_XGB = True
except Exception:
    from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
    HAVE_XGB = False
BOOST = "XGBoost" if HAVE_XGB else "Gradient boosting (sklearn)"


def classifiers(n_classes):
    boost = (XGBClassifier(n_estimators=300, max_depth=6, learning_rate=0.1, subsample=0.8, colsample_bytree=0.8,
                           n_jobs=-1, random_state=SEED, verbosity=0)
             if HAVE_XGB else HistGradientBoostingClassifier(random_state=SEED))
    d = {
        "Random Forest":       RandomForestClassifier(n_estimators=300, class_weight="balanced", n_jobs=-1, random_state=SEED),
        "Logistic regression": make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, class_weight="balanced")),
        "k-NN (k=5)":          make_pipeline(StandardScaler(), KNeighborsClassifier(n_neighbors=5)),
        "SVM (RBF)":           make_pipeline(StandardScaler(), SVC(probability=True, class_weight="balanced", random_state=SEED)),
        "Neural net (MLP)":    make_pipeline(StandardScaler(), MLPClassifier(hidden_layer_sizes=(64, 32), max_iter=600, early_stopping=True, random_state=SEED)),
        BOOST:                 boost,
    }
    if EXTRA:   # less famous models that are still reasonable for ~1,300 hand-made features
        d.update({
            "Extra Trees":          ExtraTreesClassifier(n_estimators=300, class_weight="balanced", n_jobs=-1, random_state=SEED),
            "Single decision tree": DecisionTreeClassifier(class_weight="balanced", random_state=SEED),
            "AdaBoost":             AdaBoostClassifier(n_estimators=200, random_state=SEED),
            "LDA":                  make_pipeline(StandardScaler(), LinearDiscriminantAnalysis()),
            "Gaussian naive Bayes": GaussianNB(),
            "Gaussian process":     make_pipeline(StandardScaler(), GaussianProcessClassifier(1.0 * RBF(3.0), optimizer=None, n_jobs=-1, random_state=SEED)),
        })
    return d


def regressors():
    boost = (XGBRegressor(n_estimators=300, max_depth=6, learning_rate=0.1, subsample=0.8, colsample_bytree=0.8,
                          n_jobs=-1, random_state=SEED, verbosity=0)
             if HAVE_XGB else HistGradientBoostingRegressor(random_state=SEED))
    d = {
        "Random Forest":     RandomForestRegressor(n_estimators=100, min_samples_leaf=30, n_jobs=-1, random_state=SEED),
        "Linear (Ridge)":    make_pipeline(StandardScaler(), Ridge(1.0)),
        "k-NN (k=5)":        make_pipeline(StandardScaler(), KNeighborsRegressor(n_neighbors=5)),
        "SVM (RBF, SVR)":    make_pipeline(StandardScaler(), SVR()),
        "Neural net (MLP)":  make_pipeline(StandardScaler(), MLPRegressor(hidden_layer_sizes=(64, 32), max_iter=600, early_stopping=True, random_state=SEED)),
        BOOST:               boost,
    }
    if EXTRA:
        d.update({
            "Extra Trees":          ExtraTreesRegressor(n_estimators=300, n_jobs=-1, random_state=SEED),
            "Single decision tree": DecisionTreeRegressor(random_state=SEED),
            "AdaBoost":             AdaBoostRegressor(n_estimators=200, random_state=SEED),
            "Bayesian ridge":       make_pipeline(StandardScaler(), BayesianRidge()),
            "Gaussian process":     make_pipeline(StandardScaler(), GaussianProcessRegressor(C(1.0) * RBF(3.0) + WhiteKernel(1.0), normalize_y=True, optimizer=None, random_state=SEED)),
        })
    return d


def size_kb(model):
    buf = io.BytesIO(); joblib.dump(model, buf); return len(buf.getvalue()) / 1024


def top3(model, Xte, yte, enc_classes):
    p = model.predict_proba(Xte)
    cls = np.asarray(enc_classes)[np.asarray(model.classes_) if hasattr(model, "classes_") else model[-1].classes_]
    best = cls[np.argsort(-p, axis=1)[:, :3]]
    return float(np.mean([t in row for t, row in zip(yte, best)]))


def run_classification(X, y, groups, folds, noise):
    classes, y_enc = np.unique(y, return_inverse=True)            # labels as 0..K-1 so XGBoost accepts them
    rng = np.random.RandomState(SEED)
    sd = X.std(axis=0) + 1e-12
    gkf = GroupKFold(n_splits=min(folds, len(np.unique(groups))))
    out = {}
    for name, proto in classifiers(len(classes)).items():
        r = dict(acc=[], f1=[], top3=[], acc_noisy=[], fit_s=[], pred_ms=[], kb=[])
        for tr, te in gkf.split(X, y_enc, groups):
            m = clone(proto)
            t0 = time.time(); m.fit(X[tr], y_enc[tr]); r["fit_s"].append(time.time() - t0)
            t0 = time.time(); pr = m.predict(X[te]); r["pred_ms"].append(1000 * (time.time() - t0) / len(te))
            r["acc"].append(accuracy_score(y_enc[te], pr))
            r["f1"].append(f1_score(y_enc[te], pr, average="macro"))
            try:
                p = m.predict_proba(X[te]); mc = np.asarray(m.classes_ if hasattr(m, "classes_") else m[-1].classes_)
                r["top3"].append(float(np.mean([t in mc[np.argsort(-row)[:3]] for t, row in zip(y_enc[te], p)])))
            except Exception:
                r["top3"].append(np.nan)
            Xn = X[te] + rng.normal(0, noise, X[te].shape) * sd       # feature noise = noise x each feature's own spread
            r["acc_noisy"].append(accuracy_score(y_enc[te], m.predict(Xn)))
            r["kb"].append(size_kb(m))
        out[name] = r
    return out, len(classes)


def run_regression(X, y, groups, folds, noise):
    rng = np.random.RandomState(SEED)
    sd = X.std(axis=0) + 1e-12
    gkf = GroupKFold(n_splits=min(folds, len(np.unique(groups))))
    out = {}
    for name, proto in regressors().items():
        r = dict(mae=[], mae_noisy=[], mid=[], fit_s=[], pred_ms=[], kb=[])
        for tr, te in gkf.split(X, y, groups):
            m = clone(proto)
            t0 = time.time(); m.fit(X[tr], y[tr]); r["fit_s"].append(time.time() - t0)
            t0 = time.time(); pr = m.predict(X[te]); r["pred_ms"].append(1000 * (time.time() - t0) / len(te))
            r["mae"].append(mean_absolute_error(y[te], pr))
            r["mid"].append(mean_absolute_error(y[te], np.full(len(te), np.median(y[tr]))))
            r["mae_noisy"].append(mean_absolute_error(y[te], m.predict(X[te] + rng.normal(0, noise, X[te].shape) * sd)))
            r["kb"].append(size_kb(m))
        out[name] = r
    return out


def mean_se(v):
    v = np.asarray(v, float); v = v[~np.isnan(v)]
    return float(v.mean()), float(v.std(ddof=1) / np.sqrt(len(v))) if len(v) > 1 else 0.0


def verdict(rf, other, key, higher_better):
    d = np.asarray(rf[key]) - np.asarray(other[key])               # paired by fold
    if not higher_better: d = -d                                    # positive d = RF better
    m, se = d.mean(), d.std(ddof=1) / np.sqrt(len(d))
    if m > 2 * se and m > 0: return "RF better"
    if m < -2 * se and m < 0: return "RF worse"
    return "tie (within noise)"


def report(task, res, extra=""):
    key, hb = ("acc", True) if task == "appliance" else ("mae", False)
    nkey = "acc_noisy" if task == "appliance" else "mae_noisy"
    rf = res["Random Forest"]
    lines = []
    head = "| Model | " + ("Accuracy (unseen houses) | Macro-F1 | Top-3 |" if task == "appliance" else "Mean error (m) | Guess-the-middle (m) |") + \
           " With noisy features | Fit (s) | Predict (ms/row) | File (KB) | vs Random Forest |"
    lines += [head, "|" + "---|" * (head.count("|") - 1)]
    for name, r in res.items():
        a = mean_se(r[key]); n = mean_se(r[nkey])
        if task == "appliance":
            mid = f"{a[0]*100:.1f} ± {a[1]*100:.1f}% | {mean_se(r['f1'])[0]:.3f} | {mean_se(r['top3'])[0]*100:.1f}%"
            noisy = f"{n[0]*100:.1f}%"
        else:
            mid = f"{a[0]:.2f} ± {a[1]:.2f} | {mean_se(r['mid'])[0]:.2f}"
            noisy = f"{n[0]:.2f}"
        v = "—" if name == "Random Forest" else verdict(rf, r, key, hb)
        lines.append(f"| {name} | {mid} | {noisy} | {mean_se(r['fit_s'])[0]:.2f} | {mean_se(r['pred_ms'])[0]:.3f} | {mean_se(r['kb'])[0]:.0f} | {v} |")
    return "\n".join(lines)


def reasons(task, res):
    """Plain-language 'why Random Forest', written from the numbers just measured, never in advance."""
    key, hb = ("acc", True) if task == "appliance" else ("mae", False)
    nkey = "acc_noisy" if task == "appliance" else "mae_noisy"
    rf = res["Random Forest"]; out = []
    for name, r in res.items():
        if name == "Random Forest": continue
        v = verdict(rf, r, key, hb)
        a, b = mean_se(rf[key])[0], mean_se(r[key])[0]
        fmt = (lambda x: f"{x*100:.1f}%") if task == "appliance" else (lambda x: f"{x:.2f} m")
        dn = mean_se(r[nkey])[0] - mean_se(r[key])[0]; dr = mean_se(rf[nkey])[0] - mean_se(rf[key])[0]
        worse_noise = (dn < dr) if hb else (dn > dr)
        s = f"- {name}: RF {fmt(a)} vs {fmt(b)} -> {v}."
        if v == "RF worse":
            s += " This model is more accurate; the case for RF then rests only on the points below (size, speed, no scaling, feature importance)."
        elif v.startswith("tie"):
            s += " No real accuracy gap, so the choice is made on size, speed, simplicity and explainability."
        if worse_noise: s += " It also degrades more when the features are noisy."
        out.append(s)
    return "\n".join(out)


def plot(task, res, path):
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    key = "acc" if task == "appliance" else "mae"; nkey = "acc_noisy" if task == "appliance" else "mae_noisy"
    names = list(res); x = np.arange(len(names)); w = 0.38
    sc = 100 if task == "appliance" else 1
    fig, ax = plt.subplots(figsize=(9, 4.2))
    a = [mean_se(res[n][key]) for n in names]; b = [mean_se(res[n][nkey]) for n in names]
    ax.bar(x - w/2, [m*sc for m, _ in a], w, yerr=[s*sc for _, s in a], label="clean features", color="#2f6f9f", capsize=3)
    ax.bar(x + w/2, [m*sc for m, _ in b], w, label="noisy features", color="#d98f3a")
    ax.set_xticks(x); ax.set_xticklabels(names, rotation=18, ha="right", fontsize=9)
    ax.set_ylabel("accuracy on unseen houses (%)" if task == "appliance" else "mean distance error (m)")
    ax.set_title(("Appliance identification" if task == "appliance" else "Distance estimate") + ": Random Forest against other models")
    ax.legend(); fig.tight_layout(); fig.savefig(path, dpi=200); plt.close(fig)


def demo_data():
    from sklearn.datasets import make_classification, make_regression
    X, y = make_classification(1800, 24, n_informative=14, n_classes=11, n_clusters_per_class=2, class_sep=1.2, random_state=1)
    g = np.random.RandomState(1).randint(0, 16, len(y))
    Xr, yr = make_regression(1800, 12, n_informative=8, noise=15, random_state=1)
    return (X, y, g), (Xr, (yr - yr.min()) / (yr.max() - yr.min()) * 30, np.random.RandomState(2).randint(0, 16, len(yr)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true", help="stand-in random data, only to check the script runs")
    ap.add_argument("--core", action="store_true", help="only the five well-known models (faster)")
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--noise", type=float, default=0.3, help="noise added to test features, as a fraction of each feature's spread")
    a = ap.parse_args()
    global EXTRA; EXTRA = not a.core
    os.makedirs(RES, exist_ok=True)
    tasks = {}
    if a.demo:
        (A, B) = demo_data(); tasks["appliance"] = A; tasks["distance"] = B
        tag = "_DEMO_RANDOM_DATA"
    else:
        tag = ""
        for t, f in (("appliance", "appliance_xy.npz"), ("distance", "distance_xy.npz")):
            p = os.path.join(RES, f)
            if os.path.exists(p):
                d = np.load(p, allow_pickle=True); tasks[t] = (d["X"], d["y"], d["groups"])
            else:
                print(f"missing {p}: add the np.savez line from the top of this file to train_models.py and run it once")
        if not tasks: sys.exit(1)
    md = ["# Why Random Forest: comparison with other models" + (" (stand-in data, NOT real results)" if a.demo else ""), "",
          f"Split by house (GroupKFold, {a.folds} folds), same folds for every model. Noise test: test features perturbed by {a.noise} x their own spread. ± is the standard error over folds.", ""]
    js = {}
    for t, (X, y, g) in tasks.items():
        print(f"\n=== {t}: {X.shape[0]} rows, {X.shape[1]} features, {len(np.unique(g))} groups ===")
        if t == "appliance":
            res, k = run_classification(X, y, g, a.folds, a.noise); md.append(f"## Appliance identification ({k} classes, {len(y)} records)")
        else:
            res = run_regression(X, y, g, a.folds, a.noise); md.append(f"## Distance estimate ({len(y)} events)")
        table = report(t, res); why = reasons(t, res)
        print(table); print(why)
        md += ["", table, "", "What the numbers say:", why, ""]
        js[t] = {n: {k2: (mean_se(v)[0], mean_se(v)[1]) for k2, v in r.items()} for n, r in res.items()}
        plot(t, res, os.path.join(RES, f"compare_rf_{t}{tag}.png"))
    md += ["## The general reasons that apply to this project (check each against the table above before you say it)", "",
           "- Small tabular data (about 1,300 appliance records from 16 houses): neural nets and SVMs have little to learn from and tend to overfit; trees and forests are the usual strong choice on small, hand-made features.",
           "- Features are on very different scales (amplitudes, ratios, counts): forests need no scaling; k-NN, SVM, logistic regression and the MLP all depend on it.",
           "- Random Forest gives class probabilities, which the app uses for 'top 3 likely appliances', and feature importances, which let us explain a decision.",
           "- Bagging averages many trees, so the result varies little between random seeds and houses; a single model with a few knobs (SVM C/gamma, MLP layers, boosting depth/rate) can win only after tuning, and with 16 houses tuning itself overfits.",
           "- It runs on the backend laptop/server, so size (KB) and speed (ms) are not limits here; if a model is smaller or faster the table shows by how much.",
           "- Honest limit: if a row above says 'RF worse' or 'tie', do not claim RF is the most accurate; say it is the simplest model that is as good, and why that matters."]
    with open(os.path.join(RES, f"compare_rf{tag}.md"), "w", encoding="utf-8") as f: f.write("\n".join(md))
    with open(os.path.join(RES, f"compare_rf{tag}.json"), "w") as f: json.dump(js, f, indent=1)
    print("\nsaved ml/results/compare_rf%s.md, .json and one .png per task" % tag)


if __name__ == "__main__":
    main()
