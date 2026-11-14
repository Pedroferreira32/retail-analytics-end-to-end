# Engineering decisions

| Decision | Reason | Tradeoff |
| --- | --- | --- |
| Python/pandas contracts before loading | Make source quality explicit and fail early | Batch processing fits this dataset; large-scale sources would need a different execution strategy |
| Exact integer cents | Monetary totals must reconcile precisely | Display measures explicitly divide by 100 |
| Multiple facts, shared dimensions | Preserve orders/items/payments without fanout | Cross-fact filtering needs intentional DAX rather than bidirectional relationships |
| Latest review per order | Multiple review events and reused IDs are legitimate | Earlier scores remain available only in immutable raw inputs |
| Median coordinates per ZIP prefix | Prevent dimension multiplication | Prefix coordinates are approximate and not a precise address |
| Keep `customer_id` plus `customer_unique_id` | Source joins and repeat-customer identity have different meanings | Consumers must use the correct identity for each question |
| Delivered merchandise GMV | Give the main KPI a consistent status scope | It is not marketplace revenue and excludes pending sales |
| Calendar-date lateness | Estimated dates are promises, not midnight timestamps | Sub-day promised delivery windows are unavailable |
| Fixed historical RFM date | Reproducible results independent of the execution date | This is retrospective segmentation, not a live customer score |
| DuckDB plus BigQuery | Credential-free execution and real cloud deployment path | Live BigQuery acceptance is a separate gate |
| Immutable local runs and cloud snapshots | Failed transformations should not replace working data | Old snapshots require explicit lifecycle management |
| PBIP/PBIR with a TMSL `model.bim` | Report/model metadata can be versioned in Git | Desktop must still refresh M/DAX and export PBIX |
| Offline vendored Microsoft schemas | CI should not depend on a documentation website at runtime | Schema updates must be reviewed and retain upstream attribution |
| Manual full-source/cloud workflows | Olist is a fixed historical dataset | A live source would require scheduling, watermarks and freshness SLAs |
| First-person project narrative | Explain what I implemented and what I actually verified | No invented business impact or unexecuted deployment claims |

I intentionally do not infer profit, refunds, Olist commissions, predictive CLV, causal delivery effects or a real collapse in late sparse months. These quantities are not supported by the available source.
