# Data quality and validation

I validate contracts before transformation and reconcile all monetary totals after SQL mart construction. A successful run means the documented contracts passed. It does not mean every source observation is complete or every payment difference has a known cause.

## Blocking checks

- All nine files exist, have required columns and contain rows.
- Primary keys are nonnull and unique after type normalization.
- Required identifiers/status/date fields are present.
- Integer columns do not silently truncate decimals.
- Monetary values are finite, nonnegative and representable as exact INT64 cents.
- Timestamps parse explicitly; malformed nonblank values fail.
- Item/product/seller/order/payment/review relationships have no orphan foreign keys.
- Order statuses, review scores (1–5), state codes, ZIP prefixes and coordinates meet their contracts.
- Post-transformation order/item grains and ten local reconciliation checks pass.
- BigQuery publication checks source output hashes, cloud row counts, six GMV totals and recorded payments before canonical promotion.

Errors stop the run. They are not silently dropped or coerced to zero. Extra source columns are captured in the manifest, then excluded until the contract is intentionally updated.

## Observed nonblocking findings on the complete source

| Finding | Count | Treatment |
| --- | ---: | --- |
| Orders without items | 775 | Keep the order, zero item totals; preserve status |
| Orders without payments | 1 | Keep order and expose missing payment |
| Orders without reviews | 768 | No invented rating |
| Orders with multiple reviews | 547 | One deterministic latest review per order |
| Exact duplicate review rows | 0 | Exact duplicate events would be removed before latest selection |
| Delivered orders without actual delivery timestamp | 8 | Exclude from observed delivery denominator |
| Actual delivery before purchase | 0 | Would remain flagged and excluded from delivery-duration KPIs |
| Payment rows with zero installments | 2 | Retain; installment zero is not silently changed to one |
| Products without a category | 610 | Explicit `unknown` category |
| Products with an untranslated category | 13 | Retain Portuguese category as English-label fallback |
| Repeated geolocation ZIP-prefix rows | 981,148 | Median coordinates per prefix before dimension joins |
| Orders with payment difference greater than one cent | 1,076 | Preserve and investigate through SQL |

Repeated geolocation rows and multiple review events are source-grain features, not automatically corrupt data. The latest review is selected by answer timestamp, creation date, review ID, score and text as deterministic tie breakers. Only one score is included per order. Review free text is not exported.

## Test strategy

Small authored fixtures deliberately contain multi-item, split-payment and multi-review orders, reused review IDs, repeat customers, a no-item order, canceled/open orders, leading-zero ZIP prefixes, missing product attributes and same-day delivery promises. They are labeled **synthetic** everywhere and are not the evidence for real Olist results.

Tests exercise exact currency conversion, invalid integers/types, broken foreign keys, preserved grains, deterministic reruns, calendar-day lateness, censored deliveries, SQL reconciliation, historical RFM, failed-run publication behavior and BigQuery promotion ordering. CI also validates Microsoft report schemas and every visual's model binding. A cloud-client fake checks request behavior and failure ordering; it does not replace a real cloud acceptance test.

## Reproduce

```bash
pytest --cov=retail_analytics --cov-report=term-missing
retail download --raw-dir data/raw
retail run --raw-dir data/raw --output-dir data/processed --source-kind olist
python scripts/publish_evidence.py
```

Source hashes and observed counts are available in `docs/evidence/manifest.json`. A later official dataset version must be treated as a new source snapshot; changed results require explanation, not forced compatibility with these baseline counts.
