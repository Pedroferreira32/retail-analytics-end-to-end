# Source, access and provenance

**Publisher:** Olist. **Dataset:** Brazilian E-Commerce Public Dataset by Olist. **Canonical page:** https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce.

The source contains real anonymized Brazilian marketplace purchases from 2016–2018, including orders, products, customers, sellers, payments, reviews and ZIP-prefix geolocation. One order can have several items, potentially from different sellers. The source license is **CC BY-NC-SA 4.0**; see [DATA_LICENSE.md](../DATA_LICENSE.md).

## Download

```bash
retail download --raw-dir data/raw
```

This calls the original public Kaggle dataset download endpoint, validates the ZIP member list against the nine source contracts, rejects path traversal and archives over the configured size cap, and records an archive SHA-256. It refuses to overwrite a locally changed source.

If the publisher requires an authenticated browser download, download the archive from its canonical page and place these nine CSVs directly in `data/raw/`:

| File | Source role |
| --- | --- |
| `olist_orders_dataset.csv` | Order lifecycle and status |
| `olist_customers_dataset.csv` | Order-linked customer and repeat-customer identity |
| `olist_order_items_dataset.csv` | Product/seller, item price and freight |
| `olist_order_payments_dataset.csv` | Payment method, sequence, installments and amount |
| `olist_order_reviews_dataset.csv` | Review events and scores |
| `olist_products_dataset.csv` | Product category and physical attributes |
| `olist_sellers_dataset.csv` | Seller geography |
| `product_category_name_translation.csv` | Portuguese/English category labels |
| `olist_geolocation_dataset.csv` | ZIP-prefix coordinates, many observations per prefix |

Every run fingerprints the exact CSV bytes and records source row counts, byte sizes and extra columns. The published baseline archive SHA-256 was `967e41e04fc306fe604e2a693f488995a8b41e5047418f8a5c8e4abd6deca784`. The individual file fingerprints in `docs/evidence/manifest.json` are authoritative for reproducing the published results.

Raw CSVs, review free text and transaction-level exports are not committed. Only aggregate analytical evidence, schema/quality metadata and authored synthetic fixtures are tracked. Generated figures and aggregate CSVs carry Olist attribution and the original noncommercial share-alike license.

The pipeline is deliberately a historical batch pipeline. It does not pretend that these fixed 2016–2018 records are current retail sales.
