import copy
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Literal, Optional, Union

import numpy as np
import pandas as pd

# Define unified data input type
DataType = Union[np.ndarray, pd.DataFrame]


@dataclass
class ValidationConfig:
    """Configuration for model validation."""

    method: Literal["walk_forward"] = "walk_forward"
    train_window: Union[str, int] = "1y"
    test_window: Union[str, int] = (
        "3m"  # Not strictly used in rolling execution, but useful for evaluation
    )
    rolling_step: Union[str, int] = "3m"
    frequency: str = "1d"
    incremental: bool = False
    verbose: bool = False


class QuantModel(ABC):
    """
    Abstract base class for all quantitative models.

    The strategy layer only interacts with this class, not directly with sklearn or
    torch.
    """

    def __init__(self) -> None:
        """Initialize the model."""
        self.validation_config: Optional[ValidationConfig] = None

    def set_validation(
        self,
        method: Literal["walk_forward"] = "walk_forward",
        train_window: Union[str, int] = "1y",
        test_window: Union[str, int] = "3m",
        rolling_step: Union[str, int] = "3m",
        frequency: str = "1d",
        incremental: bool = False,
        verbose: bool = False,
    ) -> None:
        """
        Configure validation method (e.g., Walk-forward).

        :param method: Validation method (currently only 'walk_forward').
        :param train_window: Training data duration (e.g., '1y', '250d') or bar count.
        :param test_window: Testing/Prediction duration (e.g., '3m') or bar count.
        :param rolling_step: How often to retrain (e.g., '3m') or bar count.
        :param frequency: Data frequency ('1d', '1h', '1m') used for parsing time
            strings.
        :param incremental: Whether to use incremental learning (continue from last
            training) or retrain from scratch. Default False.
        :param verbose: Whether to print training logs (default False).
        """
        self.validation_config = ValidationConfig(
            method=method,
            train_window=train_window,
            test_window=test_window,
            rolling_step=rolling_step,
            frequency=frequency,
            incremental=incremental,
            verbose=verbose,
        )

    def clone(self) -> "QuantModel":
        """Return a deep-copied model instance for a new validation window."""
        return copy.deepcopy(self)

    @abstractmethod
    def fit(self, X: DataType, y: DataType) -> None:
        """
        Train the model.

        Args:
            X: Training features
            y: Training labels
        """
        pass

    @abstractmethod
    def predict(self, X: DataType) -> np.ndarray:
        """
        Predict using the model.

        Args:
            X: Input features

        Returns:
            np.ndarray: Prediction results (numpy array)
        """
        pass

    @abstractmethod
    def save(self, path: str) -> None:
        """Save the model to the specified path."""
        pass

    @abstractmethod
    def load(self, path: str) -> None:
        """Load the model from the specified path."""
        pass


class SklearnAdapter(QuantModel):
    """Adapter for Scikit-learn style models."""

    def __init__(self, estimator: Any):
        """
        Initialize the adapter.

        Args:
            estimator: A sklearn-style estimator instance (e.g., XGBClassifier,
                LGBMRegressor)
        """
        super().__init__()
        self.model = estimator

    def fit(self, X: DataType, y: DataType) -> None:
        """Train the sklearn model."""
        if self.validation_config and self.validation_config.verbose:
            print(f"Training Sklearn Model: {type(self.model).__name__}")

        if self.validation_config and self.validation_config.incremental:
            if hasattr(self.model, "partial_fit"):
                # Note: partial_fit might require 'classes' for the first call
                # This is a basic support.
                try:
                    self.model.partial_fit(X, y)
                    return
                except Exception as e:
                    print(f"partial_fit failed: {e}. Falling back to fit.")
            else:
                print(
                    f"Warning: {type(self.model).__name__} does not support "
                    "incremental learning (partial_fit). Retraining from scratch."
                )

        # Convert DataFrame to numpy if necessary, or let sklearn handle it
        self.model.fit(X, y)

    def predict(self, X: DataType) -> np.ndarray:
        """Predict using the sklearn model."""
        # For classification, we usually care about the probability of class 1
        if hasattr(self.model, "predict_proba"):
            # Return probability of class 1
            # Note: This assumes binary classification. For multi-class, this might
            # need adjustment.
            proba = self.model.predict_proba(X)
            if proba.shape[1] > 1:
                return proba[:, 1]  # type: ignore
            return proba  # type: ignore
        else:
            return self.model.predict(X)  # type: ignore

    def save(self, path: str) -> None:
        """Save the sklearn model using joblib."""
        import joblib  # type: ignore

        joblib.dump(self.model, path)

    def load(self, path: str) -> None:
        """Load the sklearn model using joblib."""
        import joblib  # type: ignore

        self.model = joblib.load(path)


class PyTorchAdapter(QuantModel):
    """Adapter for PyTorch models."""

    def __init__(
        self,
        network: Any,
        criterion: Any,
        optimizer_cls: Any,
        lr: float = 0.001,
        epochs: int = 10,
        batch_size: int = 64,
        device: str = "cpu",
    ):
        """
        Initialize the PyTorch adapter.

        Args:
            network: PyTorch neural network module (nn.Module)
            criterion: Loss function (nn.Module)
            optimizer_cls: Optimizer class (torch.optim.Optimizer)
            lr: Learning rate
            epochs: Number of training epochs
            batch_size: Batch size
            device: Device to run on ('cpu' or 'cuda')
        """
        super().__init__()
        import torch

        self.device = torch.device(device)
        self.network = network.to(self.device)
        self.criterion = criterion
        self.optimizer_cls = optimizer_cls
        self.lr = lr
        self.optimizer = optimizer_cls(self.network.parameters(), lr=lr)
        self.epochs = epochs
        self.batch_size = batch_size

        # Save initial state for non-incremental training
        self.initial_state = copy.deepcopy(self.network.state_dict())

    def fit(self, X: DataType, y: DataType) -> None:
        """Train the PyTorch model."""
        import torch
        from torch.utils.data import DataLoader, TensorDataset

        # Check for incremental training
        incremental = False
        if self.validation_config:
            incremental = self.validation_config.incremental

        if not incremental:
            # Reset network weights
            self.network.load_state_dict(self.initial_state)
            # Reset optimizer
            self.optimizer = self.optimizer_cls(self.network.parameters(), lr=self.lr)

        # 1. Data conversion: Numpy/Pandas -> Tensor
        X_array = X.values if isinstance(X, pd.DataFrame) else X
        y_array = (
            y.values if isinstance(y, pd.DataFrame) or isinstance(y, pd.Series) else y
        )

        X_tensor = torch.tensor(X_array, dtype=torch.float32).to(self.device)
        y_tensor = torch.tensor(y_array, dtype=torch.float32).to(self.device)

        # 2. Wrap in DataLoader
        dataset = TensorDataset(X_tensor, y_tensor)
        loader = DataLoader(dataset, batch_size=self.batch_size, shuffle=True)

        # 3. Standard training loop
        self.network.train()

        verbose = False
        if self.validation_config and self.validation_config.verbose:
            verbose = True

        for epoch in range(self.epochs):
            total_loss = 0.0
            num_batches = 0
            for batch_X, batch_y in loader:
                self.optimizer.zero_grad()
                outputs = self.network(batch_X)

                # Note: Adjust loss calculation dimensions based on task
                # (regression/classification)
                # Squeeze last dim if it's 1 (e.g. (N, 1) -> (N)) to match batch_y
                if outputs.dim() > 1 and outputs.shape[-1] == 1:
                    outputs = outputs.squeeze(-1)

                loss = self.criterion(outputs, batch_y)
                loss.backward()
                self.optimizer.step()
                total_loss += loss.item()
                num_batches += 1

            if verbose:
                avg_loss = total_loss / num_batches if num_batches > 0 else 0
                print(f"Epoch [{epoch + 1}/{self.epochs}], Loss: {avg_loss:.4f}")

    def predict(self, X: DataType) -> np.ndarray:
        """
        Predict using the PyTorch model.

        Note:
            This returns the raw output from the network (logits or probabilities
            depending on the network's last layer). User should handle any necessary
            activations (e.g. sigmoid, softmax) in the network definition or
            post-processing.
        """
        import torch

        self.network.eval()
        with torch.no_grad():
            X_array = X.values if isinstance(X, pd.DataFrame) else X
            X_tensor = torch.tensor(X_array, dtype=torch.float32).to(self.device)
            outputs = self.network(X_tensor)
            # Convert back to Numpy for strategy layer
            return outputs.cpu().numpy().flatten()  # type: ignore

    def save(self, path: str) -> None:
        """Save the PyTorch model state dict."""
        import torch

        torch.save(self.network.state_dict(), path)

    def load(self, path: str) -> None:
        """Load the PyTorch model state dict."""
        import torch

        self.network.load_state_dict(torch.load(path))


class TensorFlowAdapter(QuantModel):
    """Adapter for TensorFlow/Keras models."""

    def __init__(
        self,
        model: Any,
        optimizer: Any = None,
        loss_fn: Any = None,
        epochs: int = 10,
        batch_size: int = 64,
        device: str = "/CPU:0",
    ):
        """
        Initialize the TensorFlow adapter.

        Args:
            model: A tf.keras.Model instance.
            optimizer: TensorFlow optimizer instance (e.g. tf.keras.optimizers.Adam).
                If None, defaults to Adam(learning_rate=0.001).
            loss_fn: Loss function (e.g. tf.keras.losses.MeanSquaredError).
                If None, defaults to MeanSquaredError.
            epochs: Number of training epochs.
            batch_size: Batch size for training.
            device: Device string (e.g. '/CPU:0', '/GPU:0').
        """
        super().__init__()
        import tensorflow as tf

        self.model = model
        self.optimizer = optimizer or tf.keras.optimizers.Adam(learning_rate=0.001)
        self.loss_fn = loss_fn or tf.keras.losses.MeanSquaredError()
        self.epochs = epochs
        self.batch_size = batch_size
        self.device = device

        self.initial_weights = [w.numpy().copy() for w in model.trainable_weights]

    def _reset_weights(self) -> None:
        for w, init_w in zip(self.model.trainable_weights, self.initial_weights):
            w.assign(init_w)

    def fit(self, X: DataType, y: DataType) -> None:
        """Train the TensorFlow model."""
        import tensorflow as tf

        incremental = (
            self.validation_config.incremental if self.validation_config else False
        )
        verbose = (
            self.validation_config.verbose if self.validation_config else False
        )

        if not incremental:
            self._reset_weights()

        X_array = X.values if isinstance(X, pd.DataFrame) else np.asarray(X)
        y_array = (
            y.values
            if isinstance(y, (pd.DataFrame, pd.Series))
            else np.asarray(y)
        )
        if y_array.ndim > 1 and y_array.shape[-1] == 1:
            y_array = y_array.squeeze(-1)

        dataset = (
            tf.data.Dataset.from_tensor_slices(
                (X_array.astype(np.float32), y_array.astype(np.float32))
            )
            .shuffle(min(self.batch_size * 10, len(X_array)))
            .batch(self.batch_size)
        )

        with tf.device(self.device):
            for epoch in range(self.epochs):
                total_loss = 0.0
                num_batches = 0
                for batch_X, batch_y in dataset:
                    with tf.GradientTape() as tape:
                        outputs = self.model(batch_X, training=True)
                        if isinstance(outputs, (list, tuple)):
                            outputs = outputs[0]
                        if outputs.ndim > 1 and outputs.shape[-1] == 1:
                            outputs = tf.squeeze(outputs, axis=-1)
                        loss = self.loss_fn(batch_y, outputs)
                    grads = tape.gradient(loss, self.model.trainable_variables)
                    self.optimizer.apply_gradients(
                        zip(grads, self.model.trainable_variables)
                    )
                    total_loss += float(loss)
                    num_batches += 1

                if verbose:
                    avg_loss = total_loss / num_batches if num_batches > 0 else 0
                    print(f"Epoch [{epoch + 1}/{self.epochs}], Loss: {avg_loss:.4f}")

    def predict(self, X: DataType) -> np.ndarray:
        """Predict using the TensorFlow model."""
        import tensorflow as tf

        X_array = X.values if isinstance(X, pd.DataFrame) else np.asarray(X)
        with tf.device(self.device):
            outputs = self.model(X_array.astype(np.float32), training=False)
            if isinstance(outputs, (list, tuple)):
                outputs = outputs[0]
        return np.asarray(outputs).flatten()

    def save(self, path: str) -> None:
        """Save the TensorFlow model using SavedModel format."""
        self.model.save(path)

    def load(self, path: str) -> None:
        """Load the TensorFlow model from SavedModel format."""
        import tensorflow as tf

        self.model = tf.keras.models.load_model(path)


class LightGBMAdapter(QuantModel):
    """Adapter for LightGBM models."""

    def __init__(
        self,
        params: dict[str, Any] | None = None,
        num_boost_round: int = 100,
    ) -> None:
        """
        Initialize the LightGBM adapter.

        Args:
            params: LightGBM parameters dict.
            num_boost_round: Number of boosting iterations.
        """
        super().__init__()
        self.params = params or {"objective": "regression", "metric": "rmse"}
        self.num_boost_round = num_boost_round
        self.model: Any = None

    def fit(self, X: DataType, y: DataType) -> None:
        """Train the LightGBM model."""
        import lightgbm as lgb

        if self.validation_config and self.validation_config.verbose:
            print("Training LightGBM Model")

        train_data = lgb.Dataset(X, label=y)
        self.model = lgb.train(self.params, train_data, self.num_boost_round)

    def predict(self, X: DataType) -> np.ndarray:
        """Predict using the LightGBM model."""
        return self.model.predict(X)

    def save(self, path: str) -> None:
        """Save the LightGBM model."""
        self.model.save_model(path)

    def load(self, path: str) -> None:
        """Load the LightGBM model."""
        import lightgbm as lgb

        self.model = lgb.Booster(model_file=path)


class XGBoostAdapter(QuantModel):
    """Adapter for XGBoost models."""

    def __init__(
        self,
        params: dict[str, Any] | None = None,
        num_boost_round: int = 100,
    ) -> None:
        """
        Initialize the XGBoost adapter.

        Args:
            params: XGBoost parameters dict.
            num_boost_round: Number of boosting iterations.
        """
        super().__init__()
        self.params = params or {"objective": "reg:squarederror"}
        self.num_boost_round = num_boost_round
        self.model: Any = None

    def fit(self, X: DataType, y: DataType) -> None:
        """Train the XGBoost model."""
        import xgboost as xgb

        if self.validation_config and self.validation_config.verbose:
            print("Training XGBoost Model")

        dtrain = xgb.DMatrix(X, label=y)
        self.model = xgb.train(self.params, dtrain, self.num_boost_round)

    def predict(self, X: DataType) -> np.ndarray:
        """Predict using the XGBoost model."""
        import xgboost as xgb

        dtest = xgb.DMatrix(X)
        return self.model.predict(dtest)

    def save(self, path: str) -> None:
        """Save the XGBoost model."""
        self.model.save_model(path)

    def load(self, path: str) -> None:
        """Load the XGBoost model."""
        import xgboost as xgb

        self.model = xgb.Booster()
        self.model.load_model(path)
