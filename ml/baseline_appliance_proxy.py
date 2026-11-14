import json, os
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score

BASE = "ml/data/plaid/"
CACHE = "ml/data/plaid_cycles_sub.npz"
MIN_PER_TYPE = 75
CYC, NCYC, F0 = 500, 60, 60.0
MUT, RIN, RFB, CINT = 1e-6, 10e3, 1e6, 1e-9
RAIL = 1.8
rng = np.random.default_rng(0)

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

def mean_cycle(i, v):
    """Average current cycle over the last second, aligned to a rising zero crossing of the voltage."""
    i, v = i[-(CYC * NCYC + CYC):], v[-(CYC * NCYC + CYC):]
    zc = np.where((v[:-1] < 0) & (v[1:] >= 0))[0]
    s = zc[0] + 1
    seg = i[s:s + CYC * NCYC]
    n = len(seg) // CYC
    return seg[:n * CYC].reshape(n, CYC).mean(axis=0)

def proxy_wave(c):
    """What the ESP32 would read from the di/dt integrator output (single supply, 12-bit ADC)."""
    I = np.fft.rfft(c)
    w = 2 * np.pi * F0 * np.arange(len(I))
    H = (RFB / RIN) * (1j * w * MUT) / (1 + 1j * w * RFB * CINT)
    out = np.fft.irfft(I * H, len(c))
    out = np.clip(out, 0.0, RAIL)
    out = out + rng.normal(0, 0.0003, len(c))
    return np.round(out / 0.0008) * 0.0008

def shape_features(x):
    a = np.abs(x)
    sp = np.abs(np.fft.rfft(x))[1:16]
    harm = sp[1:] / (sp[0] + 1e-9)
    rms = np.sqrt((x ** 2).mean()) + 1e-9
    crest = a.max() / rms
    thd = np.sqrt((sp[1:] ** 2).sum()) / (sp[0] + 1e-9)
    duty = (a > 0.05 * a.max()).mean()
    return np.concatenate([harm, [crest, thd, duty]])

def amp_feature(x):
    return np.array([np.log10(np.abs(x).max() + 1e-4)])

if __name__ == "__main__":
    meta = json.load(open(BASE + "metadata_submetered.json"))
    if os.path.exists(CACHE):
        z = np.load(CACHE, allow_pickle=True)
        C, types, locs = z["C"], z["types"], z["locs"]
    else:
        C, types, locs = [], [], []
        for k, m in meta.items():
            i, v = read_csv(BASE + f"submetered/{k}.csv")
            try:
                c = mean_cycle(i, v)
            except Exception:
                continue
            if len(c) != CYC:
                continue
            C.append(c); types.append(m["appliance"]["type"]); locs.append(m["location"])
        C, types, locs = np.array(C), np.array(types), np.array(locs)
        np.savez(CACHE, C=C, types=types, locs=locs)

    names, counts = np.unique(types, return_counts=True)
    keep = [n for n, c in zip(names, counts) if c >= MIN_PER_TYPE]
    mask = np.isin(types, keep)
    C, types, locs = C[mask], types[mask], locs[mask]
    classes = sorted(keep)
    y = np.array([classes.index(t) for t in types])
    fam = np.array([FAMILY[c] for c in classes])
    ulocs = sorted(set(locs))
    test = np.array([l in set(ulocs[::4]) for l in locs])
    print("records:", len(y), " types:", len(classes), " test records:", test.sum(), "(split by house)")

    P = np.array([proxy_wave(c) for c in C])
    sets = {
        "full current waveform (not available to Fuzz)": np.array([shape_features(c) for c in C]),
        "Fuzz integrator output, shape only": np.array([shape_features(p) for p in P]),
        "Fuzz integrator output, shape + amplitude": np.array([np.concatenate([shape_features(p), amp_feature(p)]) for p in P]),
    }
    print(f"\n{'features':50s} {'exact':>6s} {'family':>7s}")
    for name, X in sets.items():
        rf = RandomForestClassifier(n_estimators=300, class_weight="balanced", random_state=0, n_jobs=-1)
        rf.fit(X[~test], y[~test])
        pred = rf.predict(X[test])
        print(f"{name:50s} {accuracy_score(y[test], pred):6.3f} {(fam[pred] == fam[y[test]]).mean():7.3f}")