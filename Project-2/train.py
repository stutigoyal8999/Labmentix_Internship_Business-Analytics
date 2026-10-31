"""
Real Estate Investment Advisor - Model Training
------------------------------------------------
Trains classification models (Good Investment) and regression models
(Future Price after 5 years), tracks every run with MLflow, registers the
best model for each task, and saves them to the models/ folder for the
Streamlit app.

Run from the project folder:   python train.py
"""

import json
import logging
import os
import time
import warnings

import joblib
import matplotlib
matplotlib.use("Agg")  # draw charts without opening windows
import matplotlib.pyplot as plt
import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.metrics import (ConfusionMatrixDisplay, accuracy_score,
                             confusion_matrix, f1_score, mean_absolute_error,
                             mean_squared_error, r2_score)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from xgboost import XGBClassifier, XGBRegressor

# ---------------------------------------------------------------------------
# 1. Settings
# ---------------------------------------------------------------------------
logging.getLogger("mlflow").setLevel(logging.ERROR)  # hide MLflow warnings
warnings.filterwarnings("ignore")

DATA_PATH = "data/cleaned_housing_data.csv"
RANDOM_STATE = 42

mlflow.set_tracking_uri("sqlite:///mlflow.db")
mlflow.set_experiment("Real_Estate_Investment_Advisor")

# Features the models use.
# Left out on purpose: ID (just a label), State (decided by City),
# Locality (names repeat across all cities), Year_Built (same as Age),
# Amenities (replaced by the Has_ columns), Floor_Inconsistent (a cleaning
# flag), and Growth_Rate / Investment_Score (used to build the targets).
NUMERIC_FEATURES = [
    "BHK", "Size_in_SqFt", "Price_in_Lakhs", "Price_per_SqFt",
    "Age_of_Property", "Floor_No", "Total_Floors", "Nearby_Schools",
    "Nearby_Hospitals", "Amenity_Count", "Has_Gym", "Has_Pool",
    "Has_Clubhouse", "Has_Garden", "Has_Playground",
    "School_Density_Score", "Infrastructure_Score",
]
CATEGORICAL_FEATURES = [
    "City", "Property_Type", "Furnished_Status",
    "Public_Transport_Accessibility", "Parking_Space", "Security",
    "Facing", "Owner_Type", "Availability_Status",
]
FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES


def make_preprocessor():
    """Scale numeric columns and one-hot encode categorical columns.
    Fitted on training data only, so no information leaks from the test set."""
    return ColumnTransformer([
        ("num", StandardScaler(), NUMERIC_FEATURES),
        ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURES),
    ])


# ---------------------------------------------------------------------------
# 2. Load data
# ---------------------------------------------------------------------------
df = pd.read_csv(DATA_PATH)
X = df[FEATURES]
print(f"Loaded {df.shape[0]:,} rows, using {len(FEATURES)} features\n")

summary = {}

# ---------------------------------------------------------------------------
# 3. Classification: Good Investment
# ---------------------------------------------------------------------------
print("=" * 60)
print("CLASSIFICATION: Good Investment")
print("=" * 60)

y_clf = df["Good_Investment"]
X_train, X_test, y_train, y_test = train_test_split(
    X, y_clf, test_size=0.2, random_state=RANDOM_STATE, stratify=y_clf)

classifiers = {
    "Logistic_Regression": LogisticRegression(max_iter=1000),
    "Random_Forest_Classifier": RandomForestClassifier(
        n_estimators=100, max_depth=15, n_jobs=-1, random_state=RANDOM_STATE),
    "XGBoost_Classifier": XGBClassifier(
        n_estimators=300, max_depth=6, learning_rate=0.1,
        n_jobs=-1, random_state=RANDOM_STATE, eval_metric="logloss"),
}

clf_results = []
for name, model in classifiers.items():
    start = time.time()
    with mlflow.start_run(run_name=name):
        pipe = Pipeline([("preprocessor", make_preprocessor()), ("model", model)])
        pipe.fit(X_train, y_train)
        y_pred = pipe.predict(X_test)

        acc = accuracy_score(y_test, y_pred)
        f1 = f1_score(y_test, y_pred)

        mlflow.log_param("task", "classification")
        mlflow.log_param("model_type", name)
        mlflow.log_params({k: v for k, v in model.get_params().items()
                           if k in ("n_estimators", "max_depth", "learning_rate", "max_iter")})
        mlflow.log_metrics({"accuracy": acc, "f1_score": f1})

        fig, ax = plt.subplots(figsize=(5, 4))
        ConfusionMatrixDisplay(confusion_matrix(y_test, y_pred),
                               display_labels=["Not Good", "Good"]).plot(ax=ax, colorbar=False)
        ax.set_title(f"Confusion Matrix: {name}")
        mlflow.log_figure(fig, "confusion_matrix.png")
        plt.close(fig)

        model_info = mlflow.sklearn.log_model(pipe, name="model",
                                              serialization_format="cloudpickle")

    clf_results.append({"name": name, "pipeline": pipe, "accuracy": acc,
                        "f1": f1, "model_uri": model_info.model_uri,
                        "confusion_matrix": confusion_matrix(y_test, y_pred).tolist()})
    print(f"{name:<26} Accuracy: {acc:.4f}   F1: {f1:.4f}   ({time.time() - start:.0f}s)")

best_clf = max(clf_results, key=lambda r: r["f1"])
print(f"\nBest classifier: {best_clf['name']} (F1 = {best_clf['f1']:.4f})")
print("Confusion matrix [[TN, FP], [FN, TP]]:", best_clf["confusion_matrix"])

# ---------------------------------------------------------------------------
# 4. Regression: Future Price after 5 years
# ---------------------------------------------------------------------------
print("\n" + "=" * 60)
print("REGRESSION: Future Price after 5 Years (Lakhs)")
print("=" * 60)

y_reg = df["Future_Price_5Y"]
X_train, X_test, y_train, y_test = train_test_split(
    X, y_reg, test_size=0.2, random_state=RANDOM_STATE)

regressors = {
    "Linear_Regression": LinearRegression(),
    "Random_Forest_Regressor": RandomForestRegressor(
        n_estimators=50, max_depth=12, min_samples_leaf=20,
        n_jobs=-1, random_state=RANDOM_STATE),
    "XGBoost_Regressor": XGBRegressor(
        n_estimators=500, max_depth=6, learning_rate=0.1,
        n_jobs=-1, random_state=RANDOM_STATE),
}

reg_results = []
for name, model in regressors.items():
    start = time.time()
    with mlflow.start_run(run_name=name):
        pipe = Pipeline([("preprocessor", make_preprocessor()), ("model", model)])
        pipe.fit(X_train, y_train)
        y_pred = pipe.predict(X_test)

        rmse = np.sqrt(mean_squared_error(y_test, y_pred))
        mae = mean_absolute_error(y_test, y_pred)
        r2 = r2_score(y_test, y_pred)

        mlflow.log_param("task", "regression")
        mlflow.log_param("model_type", name)
        mlflow.log_params({k: v for k, v in model.get_params().items()
                           if k in ("n_estimators", "max_depth", "learning_rate", "min_samples_leaf")})
        mlflow.log_metrics({"rmse": rmse, "mae": mae, "r2": r2})

        fig, ax = plt.subplots(figsize=(5, 5))
        sample = np.random.RandomState(RANDOM_STATE).choice(len(y_test), 3000, replace=False)
        ax.scatter(y_test.iloc[sample], y_pred[sample], s=5, alpha=0.4)
        ax.plot([0, 850], [0, 850], color="red", linewidth=1)
        ax.set_xlabel("Actual Future Price (Lakhs)")
        ax.set_ylabel("Predicted Future Price (Lakhs)")
        ax.set_title(f"Actual vs Predicted: {name}")
        mlflow.log_figure(fig, "actual_vs_predicted.png")
        plt.close(fig)

        model_info = mlflow.sklearn.log_model(pipe, name="model",
                                              serialization_format="cloudpickle")

    reg_results.append({"name": name, "pipeline": pipe, "rmse": rmse,
                        "mae": mae, "r2": r2, "model_uri": model_info.model_uri})
    print(f"{name:<26} RMSE: {rmse:7.4f}   MAE: {mae:7.4f}   R2: {r2:.5f}   ({time.time() - start:.0f}s)")

best_reg = min(reg_results, key=lambda r: r["rmse"])
print(f"\nBest regressor: {best_reg['name']} (RMSE = {best_reg['rmse']:.4f} lakhs)")

# ---------------------------------------------------------------------------
# 5. Register the best models in MLflow and save them for the app
# ---------------------------------------------------------------------------
print("\n" + "=" * 60)
print("REGISTERING AND SAVING BEST MODELS")
print("=" * 60)

mlflow.register_model(best_clf["model_uri"], "RealEstate_GoodInvestment_Classifier")
mlflow.register_model(best_reg["model_uri"], "RealEstate_FuturePrice_Regressor")

os.makedirs("models", exist_ok=True)
joblib.dump(best_clf["pipeline"], "models/classifier.joblib", compress=3)
joblib.dump(best_reg["pipeline"], "models/regressor.joblib", compress=3)

summary = {
    "classifier": {"model": best_clf["name"], "accuracy": round(best_clf["accuracy"], 4),
                   "f1_score": round(best_clf["f1"], 4),
                   "confusion_matrix": best_clf["confusion_matrix"]},
    "regressor": {"model": best_reg["name"], "rmse": round(best_reg["rmse"], 4),
                  "mae": round(best_reg["mae"], 4), "r2": round(best_reg["r2"], 5)},
    "all_classifiers": {r["name"]: {"accuracy": round(r["accuracy"], 4), "f1_score": round(r["f1"], 4)}
                        for r in clf_results},
    "all_regressors": {r["name"]: {"rmse": round(r["rmse"], 4), "mae": round(r["mae"], 4), "r2": round(r["r2"], 5)}
                       for r in reg_results},
}
with open("models/metrics.json", "w") as f:
    json.dump(summary, f, indent=2)

print("Saved models/classifier.joblib, models/regressor.joblib and models/metrics.json")
print("Done! Run 'mlflow ui --backend-store-uri sqlite:///mlflow.db' to view the experiments.")