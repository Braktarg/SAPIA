from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.multioutput import MultiOutputRegressor

from ml.questions import DESCRIPTOR_KEYS, DIAGNOSTIC_QUESTIONS, MODEL_VERSION

ARTIFACTS_DIR = Path(__file__).resolve().parent / "artifacts"
MODEL_PATH = ARTIFACTS_DIR / f"{MODEL_VERSION}.joblib"

FEATURE_COUNT = len(DIAGNOSTIC_QUESTIONS)
OUTPUT_COUNT = len(DESCRIPTOR_KEYS)


def _generate_synthetic_data(n_samples: int = 600, seed: int = 42) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    x = rng.integers(0, 3, size=(n_samples, FEATURE_COUNT))
    y = np.zeros((n_samples, OUTPUT_COUNT))

    # Reglas heurísticas para dataset académico sintético
    y[:, 0] = (x[:, 6] * 0.35 + x[:, 1] * 0.25 + x[:, 10] * 0.2 + rng.normal(0, 0.08, n_samples)).clip(0, 1)
    y[:, 1] = (x[:, 7] * 0.4 + x[:, 1] * 0.2 + x[:, 5] * 0.15 + rng.normal(0, 0.08, n_samples)).clip(0, 1)
    y[:, 2] = (x[:, 4] * 0.4 + x[:, 9] * 0.25 + x[:, 11] * 0.15 + rng.normal(0, 0.08, n_samples)).clip(0, 1)
    y[:, 3] = (x[:, 2] * 0.35 + x[:, 0] * 0.3 + x[:, 9] * 0.2 + rng.normal(0, 0.08, n_samples)).clip(0, 1)
    y[:, 4] = (x[:, 5] * 0.45 + x[:, 9] * 0.2 + x[:, 1] * 0.15 + rng.normal(0, 0.08, n_samples)).clip(0, 1)
    y[:, 5] = (x[:, 8] * 0.4 + x[:, 3] * 0.2 + x[:, 4] * 0.15 + rng.normal(0, 0.08, n_samples)).clip(0, 1)
    return x.astype(float), y.astype(float)


def train_and_save() -> Path:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    x, y = _generate_synthetic_data()
    base = RandomForestRegressor(n_estimators=120, max_depth=8, random_state=42)
    model = MultiOutputRegressor(base)
    model.fit(x, y)
    joblib.dump({"model": model, "version": MODEL_VERSION, "descriptors": DESCRIPTOR_KEYS}, MODEL_PATH)
    return MODEL_PATH


if __name__ == "__main__":
    path = train_and_save()
    print(f"Modelo guardado en {path}")
