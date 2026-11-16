import json
import pickle
import hashlib
import json
import math
from pathlib import Path

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "Dataset"
MODELS_DIR = BASE_DIR / "Models"
MODELS_DIR.mkdir(exist_ok=True)

MODEL_VERSION = 2
MIN_SAMPLES_PER_CLASS_FOR_VALIDATION = 5
MODEL_CONFIG = {
    "traffic": {
        "file": "traffic_data.csv",
        "numeric": ["time", "vehicle_count"],
        "categorical": ["location", "weather", "road_type"],
    },
    "pollution": {
        "file": "pollution_data.csv",
        "numeric": ["co2", "pm25", "temperature", "humidity"],
        "categorical": ["traffic_level"],
    },
    "energy": {
        "file": "energy_data.csv",
        "numeric": ["population", "temperature", "time", "previous_usage"],
        "categorical": ["area"],
    },
}
MODEL_PATHS = {name: MODELS_DIR / f"{name}_pipeline.joblib" for name in MODEL_CONFIG}
MANIFEST_PATH = MODELS_DIR / "model_manifest.json"


def _dataset_fingerprints():
    return {
        name: hashlib.sha256((DATA_DIR / config["file"]).read_bytes()).hexdigest()
        for name, config in MODEL_CONFIG.items()
    }


def _read_manifest():
    try:
        with MANIFEST_PATH.open(encoding="utf-8") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError):
        return {}


def _build_pipeline(config):
    numeric_pipeline = Pipeline([("imputer", SimpleImputer(strategy="median"))])
    categorical_pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("one_hot", OneHotEncoder(handle_unknown="ignore")),
    ])
    preprocessor = ColumnTransformer([
        ("numeric", numeric_pipeline, config["numeric"]),
        ("categorical", categorical_pipeline, config["categorical"]),
    ])
    return Pipeline([
        ("preprocessor", preprocessor),
        ("classifier", RandomForestClassifier(
            n_estimators=200,
            class_weight="balanced",
            random_state=42,
        )),
    ])


def _validation_summary(features, labels, config):
    class_counts = labels.value_counts()
    if class_counts.min() < MIN_SAMPLES_PER_CLASS_FOR_VALIDATION:
        return {
            "status": "insufficient_data",
            "message": (
                "Validation withheld: at least 5 examples per class are needed "
                "for stratified 5-fold validation."
            ),
        }

    cross_validation = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    scores = cross_val_score(
        _build_pipeline(config),
        features,
        labels,
        cv=cross_validation,
        scoring="f1_macro",
    )
    return {
        "status": "validated",
        "method": "5-fold stratified cross-validation",
        "macro_f1_mean": round(float(scores.mean()), 3),
        "macro_f1_std": round(float(scores.std()), 3),
    }


def _build_models(fingerprints):
    model_summary = {}
    for name, config in MODEL_CONFIG.items():
        frame = pd.read_csv(DATA_DIR / config["file"])
        feature_columns = config["numeric"] + config["categorical"]
        required_columns = feature_columns + ["label"]
        missing_columns = sorted(set(required_columns) - set(frame.columns))
        if missing_columns:
            raise ValueError(f"{config['file']} is missing columns: {', '.join(missing_columns)}")
        if frame.empty or frame["label"].isna().any():
            raise ValueError(f"{config['file']} must contain labeled training rows.")

        features = frame[feature_columns]
        labels = frame["label"].astype(str)
        validation = _validation_summary(features, labels, config)
        model = _build_pipeline(config)
        model.fit(features, labels)
        joblib.dump(model, MODEL_PATHS[name])
        model_summary[name] = {
            "training_rows": int(len(frame)),
            "class_counts": {str(label): int(count) for label, count in labels.value_counts().items()},
            "validation": validation,
        }

    manifest = {
        "version": MODEL_VERSION,
        "dataset_fingerprints": fingerprints,
        "models": model_summary,
    }
    with MANIFEST_PATH.open("w", encoding="utf-8") as file:
        json.dump(manifest, file, indent=2)
    return model_summary


def train_models_if_needed():
    fingerprints = _dataset_fingerprints()
    manifest = _read_manifest()
    artifacts_exist = all(path.exists() for path in MODEL_PATHS.values())
    if (
        artifacts_exist
        and manifest.get("version") == MODEL_VERSION
        and manifest.get("dataset_fingerprints") == fingerprints
    ):
        return manifest["models"]
    return _build_models(fingerprints)


def load_models():
    train_models_if_needed()
    return {name: joblib.load(path) for name, path in MODEL_PATHS.items()}


def get_model_summary():
    return {
        "models": list(MODEL_CONFIG),
        "metrics": train_models_if_needed(),
        "message": "CSV-trained classifiers; validation is reported only when class counts support it.",
    }


def _predict(module, payload):
    config = MODEL_CONFIG[module]
    feature_columns = config["numeric"] + config["categorical"]
    missing = [key for key in feature_columns if payload.get(key) in (None, "")]
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")

    row = {}
    for key in config["numeric"]:
        try:
            row[key] = float(payload[key])
        except (TypeError, ValueError):
            raise ValueError(f"{key} must be a number.") from None
        if not math.isfinite(row[key]):
            raise ValueError(f"{key} must be a finite number.")
    for key in config["categorical"]:
        row[key] = str(payload[key]).strip()
        if not row[key]:
            raise ValueError(f"{key} cannot be empty.")

    models = load_models()
    frame = pd.DataFrame([row], columns=feature_columns)
    prediction = str(models[module].predict(frame)[0])
    probabilities = models[module].predict_proba(frame)[0]
    confidence = round(float(max(probabilities)) * 100, 1)
    details = _read_manifest()["models"][module]
    return {
        "module": module,
        "prediction": prediction,
        "confidence": confidence,
        "model": "RandomForestClassifier",
        "training_rows": details["training_rows"],
        "validation": details["validation"],
        "data_source": "csv_training_dataset",
    }


def predict_traffic(payload):
    return _predict("traffic", payload)


def predict_pollution(payload):
    return _predict("pollution", payload)


def predict_energy(payload):
    return _predict("energy", payload)
