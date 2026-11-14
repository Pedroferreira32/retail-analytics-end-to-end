# Evidence from the complete Olist source

This directory contains **real Olist aggregate results**, not synthetic demonstration values. The source is the original Kaggle dataset, fingerprinted in `manifest.json`. Derived analytical evidence is licensed under CC BY-NC-SA 4.0 with attribution to Olist.

| File | What it proves |
| --- | --- |
| `manifest.json` | Source fingerprints, measured source/output rows, pipeline version and run ID |
| `quality.json` | Validated contracts, missingness and preserved source anomalies |
| `reconciliation.json` | Source items/freight/payments and all SQL GMV marts reconcile |
| `summary.json` | Main documented KPI baseline and populations |
| `analysis.json` | Results from the four inspectable analytical SQL queries |
| `monthly_sales.csv` | Aggregate monthly sales, delivery and review indicators |
| `state_sales.csv` | Delivered merchandise GMV by customer state |

The local evidence does not claim a live BigQuery deployment or a successful Power BI Desktop refresh. Those are separate acceptance gates in [publication.md](../publication.md).

## Rebuild

```bash
retail download --raw-dir data/raw
retail run --raw-dir data/raw --output-dir data/processed --source-kind olist
python scripts/publish_evidence.py
```

The generated figures in `docs/images/` are precise matplotlib exports from this validated run. They are not screenshots of Power BI. The full purchase interval is 2016-09-04 through 2018-10-17; months at the dataset edges are incomplete/sparse. Read the [metric contract](../metrics.md) before interpreting changes.
