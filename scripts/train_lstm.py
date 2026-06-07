#!/usr/bin/env python3
"""Train and evaluate the first LSTM baseline on prepared NGIDS windows."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train an LSTM anomaly detector.")
    parser.add_argument("--sequence-dir", type=Path, default=Path("dataset/lstm_sequences"))
    parser.add_argument("--output-dir", type=Path, default=Path("dataset/lstm_model"))
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--lstm-units", type=int, default=64)
    parser.add_argument("--syscall-embedding-dim", type=int, default=32)
    parser.add_argument("--family-embedding-dim", type=int, default=8)
    parser.add_argument("--dropout", type=float, default=0.3)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def load_npz(path: Path) -> tuple[dict[str, np.ndarray], np.ndarray]:
    data = np.load(path)
    x = {
        "syscall_tokens": data["syscall_tokens"],
        "family_tokens": data["family_tokens"],
        "delta_time": data["delta_time"],
    }
    return x, data["labels"].astype("float32")


def classification_metrics(y_true: np.ndarray, y_score: np.ndarray, threshold: float) -> dict:
    y_pred = (y_score >= threshold).astype(np.int32)
    y_true = y_true.astype(np.int32)
    tp = int(((y_pred == 1) & (y_true == 1)).sum())
    fp = int(((y_pred == 1) & (y_true == 0)).sum())
    fn = int(((y_pred == 0) & (y_true == 1)).sum())
    tn = int(((y_pred == 0) & (y_true == 0)).sum())
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "threshold": float(threshold),
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
    }


def best_f1_threshold(y_true: np.ndarray, y_score: np.ndarray) -> tuple[float, dict]:
    best_threshold = 0.5
    best_metrics = classification_metrics(y_true, y_score, best_threshold)
    for threshold in np.linspace(0.05, 0.95, 19):
        metrics = classification_metrics(y_true, y_score, float(threshold))
        if metrics["f1"] > best_metrics["f1"]:
            best_threshold = float(threshold)
            best_metrics = metrics
    return best_threshold, best_metrics


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = args.output_dir / "metrics.json"

    if metrics_path.exists() and not args.overwrite:
        raise FileExistsError(
            f"{metrics_path} already exists. Pass --overwrite to retrain the model."
        )

    try:
        import tensorflow as tf
    except ImportError as exc:
        raise ImportError(
            "TensorFlow is required for LSTM training. Install it with `pip install tensorflow`."
        ) from exc

    metadata = json.loads((args.sequence_dir / "metadata.json").read_text())
    train_x, train_y = load_npz(args.sequence_dir / "train.npz")
    val_x, val_y = load_npz(args.sequence_dir / "validation.npz")
    test_x, test_y = load_npz(args.sequence_dir / "test.npz")

    syscall_input = tf.keras.Input(shape=(None,), dtype="int32", name="syscall_tokens")
    family_input = tf.keras.Input(shape=(None,), dtype="int32", name="family_tokens")
    delta_input = tf.keras.Input(shape=(None, 1), dtype="float32", name="delta_time")

    syscall_emb = tf.keras.layers.Embedding(
        input_dim=metadata["syscall_vocab_size"],
        output_dim=args.syscall_embedding_dim,
        mask_zero=False,
        name="syscall_embedding",
    )(syscall_input)
    family_emb = tf.keras.layers.Embedding(
        input_dim=metadata["family_vocab_size"],
        output_dim=args.family_embedding_dim,
        mask_zero=False,
        name="family_embedding",
    )(family_input)

    x = tf.keras.layers.Concatenate(name="event_features")(
        [syscall_emb, family_emb, delta_input]
    )
    x = tf.keras.layers.LSTM(args.lstm_units, name="lstm")(x)
    x = tf.keras.layers.Dropout(args.dropout, name="dropout")(x)
    x = tf.keras.layers.Dense(32, activation="relu", name="dense")(x)
    output = tf.keras.layers.Dense(1, activation="sigmoid", name="anomaly_score")(x)

    model = tf.keras.Model(
        inputs=[syscall_input, family_input, delta_input],
        outputs=output,
        name="ngids_lstm_anomaly_detector",
    )
    model.compile(
        optimizer="adam",
        loss="binary_crossentropy",
        metrics=[
            tf.keras.metrics.Precision(name="precision"),
            tf.keras.metrics.Recall(name="recall"),
            tf.keras.metrics.AUC(curve="ROC", name="roc_auc"),
            tf.keras.metrics.AUC(curve="PR", name="pr_auc"),
        ],
    )

    callbacks = [
        tf.keras.callbacks.EarlyStopping(
            monitor="val_pr_auc",
            mode="max",
            patience=2,
            restore_best_weights=True,
        )
    ]

    history = model.fit(
        train_x,
        train_y,
        validation_data=(val_x, val_y),
        epochs=args.epochs,
        batch_size=args.batch_size,
        callbacks=callbacks,
        verbose=2,
    )

    val_scores = model.predict(val_x, batch_size=args.batch_size).reshape(-1)
    test_scores = model.predict(test_x, batch_size=args.batch_size).reshape(-1)
    threshold, val_f1_metrics = best_f1_threshold(val_y, val_scores)
    test_f1_metrics = classification_metrics(test_y, test_scores, threshold)

    model_path = args.output_dir / "lstm_model.keras"
    model.save(model_path)

    training_args = {
        key: str(value) if isinstance(value, Path) else value
        for key, value in vars(args).items()
    }

    metrics = {
        "model_path": str(model_path),
        "selected_threshold": threshold,
        "validation_threshold_metrics": val_f1_metrics,
        "test_threshold_metrics": test_f1_metrics,
        "keras_evaluation": {
            "validation": dict(zip(model.metrics_names, model.evaluate(val_x, val_y, verbose=0))),
            "test": dict(zip(model.metrics_names, model.evaluate(test_x, test_y, verbose=0))),
        },
        "history": history.history,
        "sequence_metadata": metadata,
        "training_args": training_args,
    }
    metrics_path.write_text(json.dumps(metrics, indent=2))
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
