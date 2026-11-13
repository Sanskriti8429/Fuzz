from pathlib import Path
import numpy as np
from scipy.io import loadmat
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from xgboost import XGBClassifier

PATH = Path("ml/data/ferracuti/Datasets/dataset_2classes_20ms_10kHz.mat")

from arc_features import features

d = loadmat(PATH, squeeze_me=True)
X_tr, y_tr = features(d["yTrain"]), d["labelsTrain"]
X_te, y_te = features(d["yTest"]), d["labelsTest"]

models = {
    "Random Forest": RandomForestClassifier(
        n_estimators=300, class_weight="balanced", random_state=0, n_jobs=-1
    ),
    "XGBoost": XGBClassifier(
        n_estimators=300, max_depth=4, learning_rate=0.1, eval_metric="logloss"
    ),
}

for name, model in models.items():
    model.fit(X_tr, y_tr)
    pred = model.predict(X_te)
    print(f"\n=== {name} ===")
    print("accuracy:", round(accuracy_score(y_te, pred), 4))
    print("confusion matrix (rows = true, columns = predicted):")
    print(confusion_matrix(y_te, pred))
    print(classification_report(y_te, pred, target_names=["class 0", "class 1"], digits=3))