# anomaly-detection-xai

`notebook/Anomaly_Detection.ipynb` now supports both Google Colab and local Jupyter.

Dataset paths:

- Colab: `/content/drive/MyDrive/Practicum/NGIDS/NGIDS-DS-v1/parquet`
- Local: `../dataset` with a fallback to `./dataset`

Local layout:

- `../dataset/host_logs.parquet`
- `../dataset/ground_truth.parquet`

Baseline modeling table build:

```bash
.venv/bin/python scripts/build_baseline_modeling_table.py --overwrite
```

Default output:

- `dataset/modeling_baseline/train.parquet`
- `dataset/modeling_baseline/validation.parquet`
- `dataset/modeling_baseline/test.parquet`
- `dataset/modeling_baseline/metadata.json`
