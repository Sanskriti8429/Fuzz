"""Measure real appliance current slopes (di/dt) from the COOLL dataset.

Usage (from the Fuzz repo root):
    pip install numpy imageio-ffmpeg
    python ml/cooll_didt_check.py ml/data/cooll

Reads scenarioC1_<id>.flac, scaleFactors.txt and appliances_and_action_delays.txt,
and writes ml/results/cooll_didt.csv plus a per-appliance summary.
COOLL: Picon et al., CC BY-NC 4.0, current sampled at 100 kHz.
"""
import sys, re, subprocess, csv, pathlib
import numpy as np

FS = 100_000
TRIP_KA_S = 16.5          # simulated arc slope used by Fuzz

def _ffmpeg():
    import shutil
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    import imageio_ffmpeg            # pip install imageio-ffmpeg  (bundles ffmpeg)
    return imageio_ffmpeg.get_ffmpeg_exe()

def read_flac(path):
    # libsndfile rejects some COOLL files ("flac decoder lost sync"), so decode with ffmpeg directly.
    raw = subprocess.run([_ffmpeg(), "-v", "error", "-i", str(path), "-f", "s16le", "-ac", "1", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype="<i2").astype(float) / 32768

def analyse(x, scale):
    x = x * scale
    w = FS // 50                                   # one mains cycle
    rms = np.sqrt(np.convolve(x**2, np.ones(w) / w, "same"))
    if rms.max() < 0.05:                           # appliance never drew current
        return None
    on = np.where(rms > 0.3 * rms.max())[0]
    a, b = on[0], on[-1]
    slope = np.abs(np.diff(x)) * FS / 1e3          # kA/s at 10 us resolution
    run = slope[a + 3 * w: max(b - w, a + 3 * w + 1)]
    sw = slope[max(a - w, 0): a + 3 * w]
    return dict(on_s=a / FS, off_s=b / FS, run_rms_A=float(np.sqrt((x[a+3*w:b-w] ** 2).mean())) if b - w > a + 3*w else np.nan,
                run_p99=float(np.percentile(run, 99)) if run.size else np.nan,
                run_p999=float(np.percentile(run, 99.9)) if run.size else np.nan,
                run_max=float(run.max()) if run.size else np.nan,
                switch_max=float(sw.max()))

def main(folder):
    d = pathlib.Path(folder)
    scales = [float(l.split()[0]) for l in open(d / "scaleFactors.txt") if l.strip()]
    names = {}
    for l in open(d / "appliances_and_action_delays.txt"):
        m = re.match(r"(\d+):\s*(.+)_(\d+)_(\d+)ms", l.strip())
        if m: names[int(m.group(1))] = m.group(2)
    rows = []
    for f in sorted(d.glob("scenarioC1_*.flac"), key=lambda p: int(p.stem.split("_")[1])):
        i = int(f.stem.split("_")[1])
        r = analyse(read_flac(f), scales[i - 1])
        if r: rows.append(dict(id=i, appliance=names.get(i, "?"), **r))
    out = pathlib.Path("ml/results"); out.mkdir(parents=True, exist_ok=True)
    with open(out / "cooll_didt.csv", "w", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=rows[0].keys()); wr.writeheader(); wr.writerows(rows)
    print(f"{len(rows)} recordings analysed; trip slope in Fuzz = {TRIP_KA_S} kA/s")
    print(f"{'appliance':18}{'n':>4}{'run p99':>9}{'run max':>9}{'switch max':>12}{'run max >16.5':>15}")
    for a in sorted({r['appliance'] for r in rows}):
        g = [r for r in rows if r['appliance'] == a]
        print(f"{a:18}{len(g):4}{np.nanmedian([r['run_p99'] for r in g]):9.1f}{max(r['run_max'] for r in g):9.1f}"
              f"{max(r['switch_max'] for r in g):12.1f}{sum(r['run_max'] > TRIP_KA_S for r in g):15}")

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "ml/data/cooll")
