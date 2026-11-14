import json, os, collections
import numpy as np

base = "ml/data/plaid/"
sub = json.load(open(base + "metadata_submetered.json"))
agg = json.load(open(base + "metadata_aggregated.json"))

print("SUBMETERED: records", len(sub), " csv files", len(os.listdir(base + "submetered")))
types = collections.Counter(v["appliance"]["type"] for v in sub.values())
for t, n in types.most_common():
    print(f"  {n:5d}  {t}")

print("\nAGGREGATED: records", len(agg), " csv files", len(os.listdir(base + "aggregated")))
keys = sorted(int(k) for k in agg)
files = sorted(int(f.split('.')[0]) for f in os.listdir(base + "aggregated"))
print("  metadata keys", keys[0], "to", keys[-1], "| csv names", files[0], "to", files[-1])
agg_types = collections.Counter(a["type"] for v in agg.values() for a in v["appliances"])
for t, n in agg_types.most_common():
    print(f"  {n:5d}  {t}")
sizes = collections.Counter(len(v["appliances"]) for v in agg.values())
print("  appliances per record:", dict(sorted(sizes.items())))

print("\nOne example per submetered type (current RMS of last second, voltage RMS):")
seen = {}
for k, v in sub.items():
    seen.setdefault(v["appliance"]["type"], k)
for t, k in seen.items():
    d = np.genfromtxt(base + f"submetered/{k}.csv", delimiter=",")
    i, v = d[:, 0], d[:, 1]
    print(f"  {t:30s} I_rms {np.sqrt((i[-30000:]**2).mean()):6.2f} A   V_rms {np.sqrt((v**2).mean()):6.1f} V")

d = np.genfromtxt(base + "submetered/1.csv", delimiter=",")
v = d[:, 1]
crossings = ((v[:-1] < 0) & (v[1:] >= 0)).sum()
print("\nMains frequency estimate from record 1:", crossings / 2.0, "Hz")