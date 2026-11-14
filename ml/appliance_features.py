import numpy as np

FS = 30000
CYCLE = 500
N_CYCLES = 60
N_HARM = 15

def features(i, v):
    i, v = i[-(FS + CYCLE):], v[-(FS + CYCLE):]
    z = np.where((v[:-1] < 0) & (v[1:] >= 0))[0]
    if len(z) == 0:
        raise ValueError("no zero crossing")
    s = z[0]
    n = min(N_CYCLES, (len(i) - s) // CYCLE)
    cyc = i[s:s + n * CYCLE].reshape(n, CYCLE)
    vcyc = v[s:s + n * CYCLE].reshape(n, CYCLE).mean(axis=0)

    mc = cyc.mean(axis=0)
    rms = np.sqrt((mc ** 2).mean()) + 1e-9
    crest = np.abs(mc).max() / rms
    sp = np.fft.rfft(mc)
    mag = np.abs(sp)[1:N_HARM + 1]
    harm = mag[1:] / (mag[0] + 1e-9)
    thd = np.sqrt((mag[1:] ** 2).sum()) / (mag[0] + 1e-9)
    phi = np.angle(sp[1]) - np.angle(np.fft.rfft(vcyc)[1])
    didt = np.abs(np.diff(mc)).max() / rms
    per = np.sqrt((cyc ** 2).mean(axis=1))
    var = per.std() / (per.mean() + 1e-9)

    return np.concatenate([harm, [crest, np.cos(phi), thd, didt, var, rms]])

def startup_features(i):
    n = len(i) // CYCLE
    per = np.sqrt((i[:n * CYCLE].reshape(n, CYCLE) ** 2).mean(axis=1))
    steady = np.median(per[-30:]) + 1e-9
    inrush = per[:40].max() / steady
    first = per[0] / steady
    bad = np.where(np.abs(per - steady) >= 0.1 * steady)[0]
    settle = (bad[-1] + 1) if len(bad) else 0
    drift = per[-30:].mean() / (per[-60:-30].mean() + 1e-9)
    return np.array([inrush, first, settle / n, drift])