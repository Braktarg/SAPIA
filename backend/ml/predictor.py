import json
from pathlib import Path

import joblib
import numpy as np

from ml.questions import DESCRIPTOR_KEYS, DIAGNOSTIC_QUESTIONS, MODEL_VERSION
from ml.train import MODEL_PATH, train_and_save

FEATURE_KEYS = [q["feature_key"] for q in sorted(DIAGNOSTIC_QUESTIONS, key=lambda q: q["sort_order"])]


class ProfilePredictor:
    def __init__(self) -> None:
        self._bundle: dict | None = None
        self._load()

    def _load(self) -> None:
        if not MODEL_PATH.exists():
            train_and_save()
        self._bundle = joblib.load(MODEL_PATH)

    @property
    def model_version(self) -> str:
        assert self._bundle is not None
        return str(self._bundle.get("version", MODEL_VERSION))

    def predict(self, answers_by_item_order: list[int]) -> tuple[dict[str, float], dict[str, float]]:
        """answers_by_item_order: valores 0-2 en orden sort_order 1..12."""
        assert self._bundle is not None
        if len(answers_by_item_order) != len(DIAGNOSTIC_QUESTIONS):
            raise ValueError("Se requieren 12 respuestas")

        x = np.array([answers_by_item_order], dtype=float)
        model = self._bundle["model"]
        raw = model.predict(x)[0]
        descriptors = {
            key: round(float(np.clip(raw[i], 0.0, 1.0)), 3)
            for i, key in enumerate(DESCRIPTOR_KEYS)
        }

        # Importancias promedio del primer estimador como proxy XAI
        importances: dict[str, float] = {}
        estimator = model.estimators_[0]
        if hasattr(estimator, "feature_importances_"):
            fi = estimator.feature_importances_
            pairs = sorted(zip(FEATURE_KEYS, fi), key=lambda p: p[1], reverse=True)
            for key, val in pairs[:5]:
                importances[key] = round(float(val), 4)

        return descriptors, importances


_predictor: ProfilePredictor | None = None


def get_predictor() -> ProfilePredictor:
    global _predictor
    if _predictor is None:
        _predictor = ProfilePredictor()
    return _predictor
