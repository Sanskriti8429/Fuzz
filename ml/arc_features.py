import numpy as np

def features(X):
    X = X / (X.mean(axis=1, keepdims=True) + 1e-9)
    spec = np.log1p(np.abs(np.fft.rfft(X, axis=1))[:, 1:])
    roughness = np.abs(np.diff(X, axis=1)).mean(axis=1)
    near_zero = (X < 0.05 * X.max(axis=1, keepdims=True)).mean(axis=1)
    peak = X.max(axis=1)
    return np.hstack([spec, np.column_stack([roughness, near_zero, peak])])