import difflib
from pathlib import Path

import numpy as np
from scipy.io import loadmat
from scipy.signal import resample_poly
from sklearn.metrics import confusion_matrix
from xgboost import XGBClassifier

from arc_features import features

FOLDER = Path("ml/data/lorraine")
CACHE_DIR = Path("ml/data/lorraine_cache")
FERRACUTI = Path("ml/data/ferracuti/Datasets/dataset_2classes_20ms_10kHz.mat")

WIN_HI = 20_000        # 20 ms at 1 MS/s
DOWN = 100             # 1 MS/s -> 10 kHz
WIN_LO = 200           # 20 ms at 10 kHz
USE_ANTIALIAS = False  # False = plain subsampling (delete ml/data/lorraine_cache if you change this)

# Labelling rules. Edit freely: the raw files are not re-read.
ARC_V = 5.0     # arc-voltage RMS above this (V): a fault is inserted
QUIET_V = 1.0   # arc-voltage RMS below this (V): no fault
MIN_I = 0.3     # current RMS below this (A): the appliance is not conducting

# (name, arc-voltage file C2, line-current file C3)
RECORDINGS = [
    ("drill550", "C2_drill550_carbonizedpath", "C3_drill550_carbonizedpath"),
    ("drill_titan", "C2_drill_titan__opencontact", "C3_drill_titan_opencontact"),
    ("foodprocessor", "C2_foodprocessor_carbonizedpath", "C3_foodprocessor_carbonizedpath"),
    ("halogen", "C2_halogen_carbonizedpath", "C3_halogen_carbonizedpath"),
    ("heater", "C2_heater_carbonizedpath", "C3_heater_carbonizedpath"),
    ("kettle", "C2_kettle_carbonizedpath", "C3_kettle_carbonizedpath"),
    ("moulinex", "C2_moulinex_opencontact", "C3_moulinex_opencontact"),
    ("moulinexbis", "C2_moulinexbis_opencontact", "C3_moulinexbis_opencontact"),
    ("Res4.5A", "C2_Res4.5A_opencontact", "C3_Res4.5A_opencontact"),
    ("Res7.9A", "C2_Res7.9A_opencontact", "C3_Res7.9A_opencontact"),
    ("vacuum1200", "C2_vacumcleaner1200_carbonizedpath", "C3_vacuumcleaner1200_carbonizedpath"),
    ("vacuum_a", "C2_vacumclearner_opencontact", "C3_vacuumcleaner_opencontact"),
    ("vacuum_b", "C2_vacuumcleaner2_opencontact", "C3_vacuumcleanerbis_opencontact"),  # guessed pair
]

ALL_STEMS = sorted(p.stem for p in FOLDER.glob("*.dat"))


def resolve(stem):
    """Match a wanted file name to what is really in the folder (names have typos)."""
    if stem in ALL_STEMS:
        return stem
    match = difflib.get_close_matches(stem, ALL_STEMS, n=1, cutoff=0.8)
    if not match:
        raise FileNotFoundError(f"No file close to {stem} in {FOLDER}")
    print(f"  note: {stem} -> using {match[0]}")
    return match[0]


def read_values(path):
    return np.fromfile(path, sep=" ").reshape(-1, 2)[:, 1]


def load_recording(name, f_v, f_i):
    cache = CACHE_DIR / f"{name}.npz"
    if cache.exists():
        c = np.load(cache)
        return c["X"], c["v_rms"], c["i_rms"]
    v = read_values(FOLDER / f"{resolve(f_v)}.dat")
    i = read_values(FOLDER / f"{resolve(f_i)}.dat")
    n = min(len(v), len(i)) // WIN_HI
    v, i = v[: n * WIN_HI], i[: n * WIN_HI]
    v_rms = np.sqrt((v.reshape(n, WIN_HI) ** 2).mean(axis=1))
    i_rms = np.sqrt((i.reshape(n, WIN_HI) ** 2).mean(axis=1))
    i_lo = resample_poly(i, 1, DOWN) if USE_ANTIALIAS else i[::DOWN]
    X = np.abs(i_lo).reshape(n, WIN_LO)   # Ferracuti windows are |current|
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    np.savez(cache, X=X, v_rms=v_rms, i_rms=i_rms)
    return X, v_rms, i_rms


def main():
    X_all, y_all, rec_all = [], [], []
    for r, (name, f_v, f_i) in enumerate(RECORDINGS):
        X, v_rms, i_rms = load_recording(name, f_v, f_i)
        arc = (v_rms > ARC_V) & (i_rms > MIN_I)
        normal = (v_rms < QUIET_V) & (i_rms > MIN_I)
        open_gap = (v_rms > ARC_V) & (i_rms <= MIN_I)
        keep = arc | normal
        X_all.append(X[keep])
        y_all.append(arc[keep].astype(int))
        rec_all.append(np.full(keep.sum(), r))
        print(f"{name:14s} arc {arc.sum():4d}  normal {normal.sum():4d}  "
              f"dropped (open gap) {open_gap.sum():4d}  max arc-V RMS {v_rms.max():6.1f} V")

    X, y, rec = np.vstack(X_all), np.concatenate(y_all), np.concatenate(rec_all)
    print(f"\n{len(y)} Lorraine windows: {int((y == 1).sum())} arc, {int((y == 0).sum())} normal")

    d = loadmat(FERRACUTI, squeeze_me=True)
    model = XGBClassifier(n_estimators=300, max_depth=4, learning_rate=0.1, eval_metric="logloss")
    model.fit(features(d["yTrain"]), d["labelsTrain"])
    pred = model.predict(features(X))

    tn, fp, fn, tp = confusion_matrix(y, pred).ravel()
    print("\nTrained on Ferracuti, tested on Lorraine")
    print(f"arc detected: {tp}/{tp + fn} ({tp / (tp + fn):.1%})   "
          f"false alarms: {fp}/{fp + tn} ({fp / (fp + tn):.1%})")

    print(f"\n{'recording':14s} {'arc found':>12s} {'false alarms':>14s}")
    for r, (name, *_rest) in enumerate(RECORDINGS):
        a = (rec == r) & (y == 1)
        nrm = (rec == r) & (y == 0)
        print(f"{name:14s} {int(pred[a].sum()):>5d}/{int(a.sum()):<6d} "
              f"{int(pred[nrm].sum()):>6d}/{int(nrm.sum()):<6d}")


if __name__ == "__main__":
    main()