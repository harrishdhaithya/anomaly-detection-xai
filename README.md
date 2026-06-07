# anomaly-detection-xai

`notebook/Anomaly_Detection.ipynb` now supports both Google Colab and local Jupyter.

Dataset paths:

- Colab: `/content/drive/MyDrive/Practicum/NGIDS/NGIDS-DS-v1/parquet`
- Local: `../dataset` with a fallback to `./dataset`

Local layout:

- `../dataset/host_logs.parquet`
- `../dataset/ground_truth.parquet`
- `../dataset/syscall-lookup-linux-v3_13.csv`

LSTM sequence dataset build:

```bash
python scripts/build_lstm_sequence_dataset.py --dataset-root dataset --overwrite
```

Default output:

- `dataset/lstm_sequences/train.npz`
- `dataset/lstm_sequences/validation.npz`
- `dataset/lstm_sequences/test.npz`
- `dataset/lstm_sequences/metadata.json`

LSTM training:

```bash
python scripts/train_lstm.py --sequence-dir dataset/lstm_sequences --overwrite
```

Default output:

- `dataset/lstm_model/lstm_model.keras`
- `dataset/lstm_model/metrics.json`

The LSTM pipeline uses `(pro_id, path)` only as the sequence boundary. Model inputs are syscall tokens, syscall-family tokens, and clipped `log1p` inter-event delta time. Leakage columns such as `attack_cat`, `attack_subcat`, and `label` are excluded from inputs; `label` is used only as the target.
