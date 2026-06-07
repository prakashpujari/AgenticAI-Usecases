import logging
import pickle
import os
from typing import List, Tuple, Optional, Dict, Any
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import precision_score, recall_score, f1_score
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers

logger = logging.getLogger(__name__)


class IsolationForestAnomalyDetector:
    """Isolation Forest based anomaly detector."""

    def __init__(
        self,
        contamination: float = 0.05,
        random_state: int = 42,
        n_estimators: int = 100,
    ):
        self.contamination = contamination
        self.random_state = random_state
        self.n_estimators = n_estimators
        self.model = IsolationForest(
            contamination=contamination,
            random_state=random_state,
            n_estimators=n_estimators,
            n_jobs=-1,
        )
        self.scaler = StandardScaler()
        self.feature_names = []

    def train(
        self,
        X: np.ndarray,
        feature_names: Optional[List[str]] = None,
    ) -> Dict[str, float]:
        """Train the Isolation Forest model."""
        try:
            X_scaled = self.scaler.fit_transform(X)
            self.model.fit(X_scaled)

            if feature_names:
                self.feature_names = feature_names

            # For evaluation, we'll use synthetic labels (no ground truth)
            scores = self.model.score_samples(X_scaled)
            predictions = self.model.predict(X_scaled)

            metrics = {
                "anomalies_detected": int(np.sum(predictions == -1)),
                "normal_samples": int(np.sum(predictions == 1)),
            }

            logger.info(f"Trained Isolation Forest: {metrics}")
            return metrics

        except Exception as e:
            logger.error(f"Failed to train Isolation Forest: {e}")
            raise

    def predict(self, X: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Predict anomalies.
        Returns: (predictions, scores)
        predictions: -1 for anomaly, 1 for normal
        scores: anomaly scores (higher = more anomalous)
        """
        try:
            X_scaled = self.scaler.transform(X)
            predictions = self.model.predict(X_scaled)
            scores = self.model.score_samples(X_scaled)
            anomaly_scores = -scores  # Convert to 0-1 range
            anomaly_scores = (anomaly_scores - anomaly_scores.min()) / (
                anomaly_scores.max() - anomaly_scores.min() + 1e-6
            )
            return predictions, anomaly_scores

        except Exception as e:
            logger.error(f"Failed to predict with Isolation Forest: {e}")
            raise

    def save(self, path: str) -> None:
        """Save model to disk."""
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as f:
                pickle.dump(
                    {"model": self.model, "scaler": self.scaler, "feature_names": self.feature_names},
                    f,
                )
            logger.info(f"Saved Isolation Forest model to {path}")
        except Exception as e:
            logger.error(f"Failed to save model: {e}")

    @classmethod
    def load(cls, path: str) -> "IsolationForestAnomalyDetector":
        """Load model from disk."""
        try:
            with open(path, "rb") as f:
                data = pickle.load(f)

            detector = cls()
            detector.model = data["model"]
            detector.scaler = data["scaler"]
            detector.feature_names = data["feature_names"]

            logger.info(f"Loaded Isolation Forest model from {path}")
            return detector

        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise


class LSTMAnomalyDetector:
    """LSTM-based anomaly detector for time series data."""

    def __init__(
        self,
        lookback_window: int = 24,
        prediction_horizon: int = 1,
        encoding_dim: int = 16,
        threshold: float = 0.02,
    ):
        self.lookback_window = lookback_window
        self.prediction_horizon = prediction_horizon
        self.encoding_dim = encoding_dim
        self.threshold = threshold
        self.model = None
        self.scaler = StandardScaler()
        self.feature_names = []

    def build_model(self, input_shape: Tuple[int, int]) -> None:
        """Build LSTM autoencoder model."""
        try:
            inputs = keras.Input(shape=input_shape)

            # Encoder
            encoded = layers.LSTM(self.encoding_dim, activation="relu", input_shape=input_shape)(inputs)
            encoded = layers.RepeatVector(input_shape[0])(encoded)

            # Decoder
            decoded = layers.LSTM(input_shape[1], activation="relu", return_sequences=True)(encoded)

            autoencoder = keras.Model(inputs, decoded)
            autoencoder.compile(optimizer="adam", loss="mse")

            self.model = autoencoder
            logger.info(f"Built LSTM autoencoder model")

        except Exception as e:
            logger.error(f"Failed to build LSTM model: {e}")
            raise

    def create_sequences(
        self,
        data: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Create sequences for LSTM."""
        X, y = [], []
        for i in range(len(data) - self.lookback_window - self.prediction_horizon + 1):
            X.append(data[i : i + self.lookback_window])
            y.append(data[i + self.lookback_window : i + self.lookback_window + self.prediction_horizon])

        return np.array(X), np.array(y)

    def train(
        self,
        X: np.ndarray,
        epochs: int = 50,
        batch_size: int = 32,
        feature_names: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Train the LSTM model."""
        try:
            X_scaled = self.scaler.fit_transform(X)

            if feature_names:
                self.feature_names = feature_names

            X_seq, _ = self.create_sequences(X_scaled)

            if len(X_seq) == 0:
                raise ValueError("Not enough data to create sequences")

            # Build model if not already built
            if self.model is None:
                self.build_model((X_seq.shape[1], X_seq.shape[2]))

            history = self.model.fit(
                X_seq,
                X_seq,
                epochs=epochs,
                batch_size=batch_size,
                verbose=0,
                validation_split=0.1,
            )

            metrics = {
                "final_loss": float(history.history["loss"][-1]),
                "final_val_loss": float(history.history["val_loss"][-1]),
            }

            logger.info(f"Trained LSTM model: {metrics}")
            return metrics

        except Exception as e:
            logger.error(f"Failed to train LSTM model: {e}")
            raise

    def predict(self, X: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Predict anomalies using reconstruction error.
        Returns: (predictions, scores)
        predictions: -1 for anomaly, 1 for normal
        scores: anomaly scores (0-1)
        """
        try:
            if self.model is None:
                raise ValueError("Model not trained yet")

            X_scaled = self.scaler.transform(X)
            X_seq, _ = self.create_sequences(X_scaled)

            reconstructions = self.model.predict(X_seq, verbose=0)
            mse = np.mean(np.power(X_seq - reconstructions, 2), axis=(1, 2))

            # Normalize MSE to 0-1
            mse_normalized = (mse - mse.min()) / (mse.max() - mse.min() + 1e-6)

            predictions = np.where(mse_normalized > self.threshold, -1, 1)

            return predictions, mse_normalized

        except Exception as e:
            logger.error(f"Failed to predict with LSTM: {e}")
            raise

    def save(self, path: str) -> None:
        """Save model to disk."""
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            self.model.save(os.path.join(path, "lstm_model.h5"))

            with open(os.path.join(path, "lstm_metadata.pkl"), "wb") as f:
                pickle.dump(
                    {
                        "scaler": self.scaler,
                        "feature_names": self.feature_names,
                        "lookback_window": self.lookback_window,
                        "prediction_horizon": self.prediction_horizon,
                        "encoding_dim": self.encoding_dim,
                        "threshold": self.threshold,
                    },
                    f,
                )

            logger.info(f"Saved LSTM model to {path}")

        except Exception as e:
            logger.error(f"Failed to save LSTM model: {e}")

    @classmethod
    def load(cls, path: str) -> "LSTMAnomalyDetector":
        """Load model from disk."""
        try:
            model = keras.models.load_model(os.path.join(path, "lstm_model.h5"))

            with open(os.path.join(path, "lstm_metadata.pkl"), "rb") as f:
                metadata = pickle.load(f)

            detector = cls(
                lookback_window=metadata["lookback_window"],
                prediction_horizon=metadata["prediction_horizon"],
                encoding_dim=metadata["encoding_dim"],
                threshold=metadata["threshold"],
            )
            detector.model = model
            detector.scaler = metadata["scaler"]
            detector.feature_names = metadata["feature_names"]

            logger.info(f"Loaded LSTM model from {path}")
            return detector

        except Exception as e:
            logger.error(f"Failed to load LSTM model: {e}")
            raise


class HybridAnomalyDetector:
    """Hybrid detector combining Isolation Forest and LSTM."""

    def __init__(
        self,
        contamination: float = 0.05,
        lookback_window: int = 24,
    ):
        self.isolation_forest = IsolationForestAnomalyDetector(contamination=contamination)
        self.lstm = LSTMAnomalyDetector(lookback_window=lookback_window)

    def train(
        self,
        X: np.ndarray,
        feature_names: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Train both models."""
        try:
            if_metrics = self.isolation_forest.train(X, feature_names)
            lstm_metrics = self.lstm.train(X, feature_names=feature_names)

            return {
                "isolation_forest": if_metrics,
                "lstm": lstm_metrics,
            }

        except Exception as e:
            logger.error(f"Failed to train hybrid detector: {e}")
            raise

    def predict(self, X: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Predict using ensemble of both models.
        Returns: (predictions, combined_scores)
        """
        try:
            if_preds, if_scores = self.isolation_forest.predict(X)
            lstm_preds, lstm_scores = self.lstm.predict(X)

            # Ensure LSTM scores match IF predictions length
            if len(lstm_scores) < len(if_scores):
                lstm_scores = np.pad(
                    lstm_scores,
                    (len(if_scores) - len(lstm_scores), 0),
                    mode="constant",
                    constant_values=0.5,
                )

            combined_scores = 0.5 * if_scores + 0.5 * lstm_scores
            combined_predictions = np.where(combined_scores > 0.5, -1, 1)

            return combined_predictions, combined_scores

        except Exception as e:
            logger.error(f"Failed to predict with hybrid detector: {e}")
            raise

    def save(self, path: str) -> None:
        """Save both models."""
        try:
            os.makedirs(path, exist_ok=True)
            self.isolation_forest.save(os.path.join(path, "isolation_forest.pkl"))
            self.lstm.save(os.path.join(path, "lstm"))
            logger.info(f"Saved hybrid detector to {path}")
        except Exception as e:
            logger.error(f"Failed to save hybrid detector: {e}")

    @classmethod
    def load(cls, path: str) -> "HybridAnomalyDetector":
        """Load both models."""
        try:
            detector = cls()
            detector.isolation_forest = IsolationForestAnomalyDetector.load(
                os.path.join(path, "isolation_forest.pkl")
            )
            detector.lstm = LSTMAnomalyDetector.load(os.path.join(path, "lstm"))
            logger.info(f"Loaded hybrid detector from {path}")
            return detector
        except Exception as e:
            logger.error(f"Failed to load hybrid detector: {e}")
            raise
