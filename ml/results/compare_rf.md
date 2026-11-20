# Why Random Forest: comparison with other models

Split by house (GroupKFold, 5 folds), same folds for every model. Noise test: test features perturbed by 0.3 x their own spread. ± is the standard error over folds.

## Appliance identification (11 classes, 1824 records)

| Model | Accuracy (unseen houses) | Macro-F1 | Top-3 | With noisy features | Fit (s) | Predict (ms/row) | File (KB) | vs Random Forest |
|---|---|---|---|---|---|---|---|---|
| Random Forest | 69.3 ± 1.6% | 0.639 | 89.9% | 35.4% | 0.71 | 0.215 | 13771 | — |
| Logistic regression | 54.2 ± 2.3% | 0.490 | 78.0% | 39.1% | 0.11 | 0.002 | 3 | RF better |
| k-NN (k=5) | 65.1 ± 2.0% | 0.608 | 83.2% | 45.8% | 0.00 | 0.089 | 207 | RF better |
| SVM (RBF) | 48.6 ± 2.0% | 0.432 | 81.2% | 43.7% | 0.37 | 0.099 | 344 | RF better |
| Neural net (MLP) | 52.8 ± 3.0% | 0.414 | 79.5% | 45.2% | 0.33 | 0.004 | 95 | RF better |
| XGBoost | 66.6 ± 1.6% | 0.612 | 89.7% | 35.6% | 1.36 | 0.017 | 3278 | tie (within noise) |
| Extra Trees | 70.6 ± 1.8% | 0.639 | 91.3% | 39.7% | 0.54 | 0.249 | 32832 | tie (within noise) |
| Single decision tree | 56.2 ± 2.8% | 0.515 | 70.5% | 30.5% | 0.02 | 0.002 | 48 | RF better |
| AdaBoost | 40.2 ± 2.2% | 0.325 | 82.1% | 22.9% | 0.87 | 0.114 | 186 | RF better |
| LDA | 55.5 ± 2.8% | 0.461 | 78.7% | 28.8% | 0.01 | 0.002 | 7 | RF better |
| Gaussian naive Bayes | 53.2 ± 1.8% | 0.455 | 80.1% | 20.7% | 0.00 | 0.003 | 4 | RF better |
| Gaussian process | 50.6 ± 2.2% | 0.374 | 78.7% | 46.7% | 8.29 | 3.921 | 185686 | RF better |

What the numbers say:
- Logistic regression: RF 69.3% vs 54.2% -> RF better.
- k-NN (k=5): RF 69.3% vs 65.1% -> RF better.
- SVM (RBF): RF 69.3% vs 48.6% -> RF better.
- Neural net (MLP): RF 69.3% vs 52.8% -> RF better.
- XGBoost: RF 69.3% vs 66.6% -> tie (within noise). No real accuracy gap, so the choice is made on size, speed, simplicity and explainability.
- Extra Trees: RF 69.3% vs 70.6% -> tie (within noise). No real accuracy gap, so the choice is made on size, speed, simplicity and explainability.
- Single decision tree: RF 69.3% vs 56.2% -> RF better.
- AdaBoost: RF 69.3% vs 40.2% -> RF better.
- LDA: RF 69.3% vs 55.5% -> RF better.
- Gaussian naive Bayes: RF 69.3% vs 53.2% -> RF better.
- Gaussian process: RF 69.3% vs 50.6% -> RF better.

## Distance estimate (12000 events)

| Model | Mean error (m) | Guess-the-middle (m) | With noisy features | Fit (s) | Predict (ms/row) | File (KB) | vs Random Forest |
|---|---|---|---|---|---|---|---|
| Random Forest | 4.40 ± 0.02 | 4.70 | 4.42 | 0.38 | 0.049 | 2229 | — |
| Linear (Ridge) | 4.36 ± 0.02 | 4.70 | 4.38 | 0.00 | 0.000 | 1 | RF worse |
| k-NN (k=5) | 4.65 ± 0.03 | 4.70 | 4.66 | 0.01 | 0.004 | 326 | RF better |
| SVM (RBF, SVR) | 4.33 ± 0.03 | 4.70 | 4.36 | 8.49 | 2.026 | 261 | RF worse |
| Neural net (MLP) | 4.36 ± 0.03 | 4.70 | 4.38 | 1.12 | 0.001 | 61 | RF worse |
| XGBoost | 4.39 ± 0.02 | 4.70 | 4.39 | 0.25 | 0.002 | 852 | tie (within noise) |
| Extra Trees | 5.29 ± 0.02 | 4.70 | 5.34 | 0.41 | 0.040 | 405067 | RF better |
| Single decision tree | 5.79 ± 0.02 | 4.70 | 5.82 | 0.03 | 0.000 | 1351 | RF better |
| AdaBoost | 4.39 ± 0.03 | 4.70 | 4.41 | 0.07 | 0.001 | 15 | tie (within noise) |
| Bayesian ridge | 4.36 ± 0.02 | 4.70 | 4.38 | 0.00 | 0.000 | 1 | RF worse |
| Gaussian process | 4.35 ± 0.03 | 4.70 | 4.37 | 15.04 | 0.282 | 720232 | RF worse |

What the numbers say:
- Linear (Ridge): RF 4.40 m vs 4.36 m -> RF worse. This model is more accurate; the case for RF then rests only on the points below (size, speed, no scaling, feature importance).
- k-NN (k=5): RF 4.40 m vs 4.65 m -> RF better.
- SVM (RBF, SVR): RF 4.40 m vs 4.33 m -> RF worse. This model is more accurate; the case for RF then rests only on the points below (size, speed, no scaling, feature importance). It also degrades more when the features are noisy.
- Neural net (MLP): RF 4.40 m vs 4.36 m -> RF worse. This model is more accurate; the case for RF then rests only on the points below (size, speed, no scaling, feature importance). It also degrades more when the features are noisy.
- XGBoost: RF 4.40 m vs 4.39 m -> tie (within noise). No real accuracy gap, so the choice is made on size, speed, simplicity and explainability.
- Extra Trees: RF 4.40 m vs 5.29 m -> RF better. It also degrades more when the features are noisy.
- Single decision tree: RF 4.40 m vs 5.79 m -> RF better. It also degrades more when the features are noisy.
- AdaBoost: RF 4.40 m vs 4.39 m -> tie (within noise). No real accuracy gap, so the choice is made on size, speed, simplicity and explainability.
- Bayesian ridge: RF 4.40 m vs 4.36 m -> RF worse. This model is more accurate; the case for RF then rests only on the points below (size, speed, no scaling, feature importance).
- Gaussian process: RF 4.40 m vs 4.35 m -> RF worse. This model is more accurate; the case for RF then rests only on the points below (size, speed, no scaling, feature importance). It also degrades more when the features are noisy.

## The general reasons that apply to this project (check each against the table above before you say it)

- Small tabular data (about 1,300 appliance records from 16 houses): neural nets and SVMs have little to learn from and tend to overfit; trees and forests are the usual strong choice on small, hand-made features.
- Features are on very different scales (amplitudes, ratios, counts): forests need no scaling; k-NN, SVM, logistic regression and the MLP all depend on it.
- Random Forest gives class probabilities, which the app uses for 'top 3 likely appliances', and feature importances, which let us explain a decision.
- Bagging averages many trees, so the result varies little between random seeds and houses; a single model with a few knobs (SVM C/gamma, MLP layers, boosting depth/rate) can win only after tuning, and with 16 houses tuning itself overfits.
- It runs on the backend laptop/server, so size (KB) and speed (ms) are not limits here; if a model is smaller or faster the table shows by how much.
- Honest limit: if a row above says 'RF worse' or 'tie', do not claim RF is the most accurate; say it is the simplest model that is as good, and why that matters.