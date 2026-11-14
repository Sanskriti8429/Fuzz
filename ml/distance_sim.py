import numpy as np
from sklearn.ensemble import RandomForestRegressor

rng = np.random.default_rng(0)

F1, F2 = 0.97e6, 3.0e6
Q = 9.0
P_SRC = 1.0
A_SKIN, A_DIEL = 7e-4, 3.3e-4
N_EVENTS = 4000
D_MIN, D_MAX = 1.0, 20.0

def band_grid(fc, n=64):
    bw = fc / Q
    return np.linspace(fc - 3 * bw, fc + 3 * bw, n)

GRID = {1: band_grid(F1), 2: band_grid(F2)}
FC = {1: F1, 2: F2}

def band_power_db(band, d, loss_extra_db):
    f = GRID[band]
    fm = f / 1e6
    cable_db = 8.686 * (A_SKIN * np.sqrt(fm) + A_DIEL * fm) * d
    loss_db = cable_db + loss_extra_db(fm, d)
    src = fm ** (-P_SRC)
    sel = 1.0 / (1.0 + (2 * Q * (f - FC[band]) / FC[band]) ** 2)
    p = np.sum(src ** 2 * 10 ** (-loss_db / 10) * sel)
    return 10 * np.log10(p + 1e-30)

def simulate(x0_db_per_m, dual):
    X, y = [], []
    for _ in range(N_EVENTS):
        d = rng.uniform(D_MIN, D_MAX)
        x = x0_db_per_m * np.exp(rng.normal(0, 0.5))
        taus = rng.uniform(0.1, 1.0, 3)
        amps = rng.uniform(0, 3.0, 3)
        phis = rng.uniform(0, 2 * np.pi, 3)
        def extra(fm, dd, x=x, taus=taus, amps=amps, phis=phis):
            ripple = sum(a * np.sin(2 * np.pi * fm * t + ph) for a, t, ph in zip(amps, taus, phis))
            return x * dd * fm ** 0.7 + ripple
        g0 = rng.normal(0, 6.0)
        tilt = rng.normal(0, 3.0)
        arc = rng.uniform(0, 20)
        didt_coupling = rng.normal(0, 6.0)
        p1 = band_power_db(1, d, extra) + arc + g0 + rng.normal(0, 1.5)
        p2 = band_power_db(2, d, extra) + arc + g0 + tilt * np.log2(F2 / F1) + rng.normal(0, 1.5)
        pd = arc + didt_coupling + rng.normal(0, 1.5)
        feats = [p1 - pd]
        if dual:
            feats += [p2 - pd, p1 - p2]
        X.append(feats)
        y.append(d)
    return np.array(X), np.array(y)

def evaluate(x0, dual):
    X, y = simulate(x0, dual)
    n = len(y)
    tr, ca, te = slice(0, int(.6 * n)), slice(int(.6 * n), int(.8 * n)), slice(int(.8 * n), n)
    rf = RandomForestRegressor(n_estimators=200, min_samples_leaf=5, random_state=0, n_jobs=-1)
    rf.fit(X[tr], y[tr])
    q = np.quantile(np.abs(y[ca] - rf.predict(X[ca])), 0.9)
    pred = rf.predict(X[te])
    err = np.abs(pred - y[te])
    lo = np.clip(pred - q, D_MIN, D_MAX)
    hi = np.clip(pred + q, D_MIN, D_MAX)
    cover = np.mean((y[te] >= lo) & (y[te] <= hi))
    return err.mean(), cover, np.mean(hi - lo)

def make_home(x0):
    return dict(x=x0 * np.exp(rng.normal(0, 0.5)), taus=rng.uniform(0.1, 1.0, 3),
                amps=rng.uniform(0, 3.0, 3), phis=rng.uniform(0, 2 * np.pi, 3),
                g0=rng.normal(0, 6.0), tilt=rng.normal(0, 3.0), dc=rng.normal(0, 6.0))

def home_event(h, d, dual):
    def extra(fm, dd):
        rip = sum(a * np.sin(2 * np.pi * fm * t + ph) for a, t, ph in zip(h["amps"], h["taus"], h["phis"]))
        return h["x"] * dd * fm ** 0.7 + rip
    arc = rng.uniform(0, 20)
    p1 = band_power_db(1, d, extra) + arc + h["g0"] + rng.normal(0, 1.5)
    p2 = band_power_db(2, d, extra) + arc + h["g0"] + h["tilt"] * np.log2(F2 / F1) + rng.normal(0, 1.5)
    pd = arc + h["dc"] + rng.normal(0, 1.5)
    return [p1 - pd, p2 - pd, p1 - p2] if dual else [p1 - pd]

def calibrated_mae(x0, dual, n_cal, homes=15):
    maes = []
    for _ in range(homes):
        h = make_home(x0)
        dtr, dte = rng.uniform(D_MIN, D_MAX, n_cal), rng.uniform(D_MIN, D_MAX, 200)
        Xtr = np.array([home_event(h, d, dual) for d in dtr])
        Xte = np.array([home_event(h, d, dual) for d in dte])
        rf = RandomForestRegressor(n_estimators=100, min_samples_leaf=3, random_state=0, n_jobs=-1)
        rf.fit(Xtr, dtr)
        maes.append(np.abs(rf.predict(Xte) - dte).mean())
    return np.mean(maes)

if __name__ == "__main__":
    print("guessing the middle (10.5 m) gives an average error of about 4.75 m\n")
    print(f"{'excess loss':>12s} {'bands':>7s} {'MAE (m)':>8s} {'90% range covers':>17s} {'avg range width (m)':>20s}")
    for x0 in [0.0, 0.1, 0.3, 0.6, 1.0]:
        for dual in (False, True):
            mae, cov, w = evaluate(x0, dual)
            print(f"{x0:9.1f} dB/m {'two' if dual else 'one':>7s} {mae:8.2f} {cov:17.2f} {w:20.1f}")

    print("\nAFTER A PER-HOME CALIBRATION: average error (m) when the unit has seen n labelled events in this home")
    for x0 in [0.1, 0.3, 1.0]:
        for dual in (False, True):
            res = " ".join(f"n={n}: {calibrated_mae(x0, dual, n):.2f}" for n in (20, 60, 200))
            print(f"{x0:6.1f} dB/m  {'two' if dual else 'one'} band(s)   {res}")