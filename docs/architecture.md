# Architecture and data grains

I separate the project into immutable sources, validated Python transformations, conformed facts/dimensions, SQL business marts and Power BI consumption. Each layer can be inspected without a cloud account. BigQuery remains the cloud warehouse target; DuckDB runs the same business logic locally for reproducibility and CI.

## Source contracts

| Source | Source grain | Handling |
| --- | --- | --- |
| Orders | `order_id` | Keep every order status |
| Customers | `customer_id` | Preserve `customer_unique_id` for repeat-customer analysis |
| Order items | `(order_id, order_item_id)` | Preserve product and seller per item |
| Payments | `(order_id, payment_sequential)` | Preserve split payments; aggregate before order joins |
| Reviews | Review event; `review_id` is not globally unique | Select one latest event per order deterministically |
| Products | `product_id` | Retain products with missing/untranslated categories |
| Sellers | `seller_id` | Separate seller geography from customer geography |
| Translation | `product_category_name` | Portuguese category is the fallback when untranslated |
| Geolocation | Observation, many rows per ZIP prefix | Median coordinates per ZIP before joining dimensions |

## Conformed analytical model

| Table | Grain | Main relationships |
| --- | --- | --- |
| `dim_date` | One calendar date | `date_key` to each fact |
| `dim_customers` | One `customer_id` | `customer_id` to each fact |
| `dim_products` | One product | `product_id` to order items |
| `dim_sellers` | One seller | `seller_id` to order items |
| `fct_orders` | One order | Aggregated items, payments and latest review |
| `fct_order_items` | One order item | Products/sellers, purchase date and order flags |
| `fct_payments` | One payment sequence within an order | Payment type/installments, purchase date and order flags |

Power BI relationships flow one way from dimensions to facts. There are no fact-to-fact or bidirectional relationships. Product and seller filters reach order-level KPI measures through explicit DAX `TREATAS`, avoiding ambiguous model paths. Category order counts are not additive: one order can contain multiple categories.

`customer_id` is the source join key, not a reusable person identifier. The separate `customer_unique_id` supports frequency/RFM analysis without falsely counting every order as a new customer. No customer name, email, telephone or review free text is exposed in the analytical layer.

## SQL marts

| Mart | Grain | Primary use |
| --- | --- | --- |
| `mart_monthly_sales` | Purchase month | Executive commercial and delivery indicators |
| `mart_category_sales` | Purchase month × category | Product mix and category relevance |
| `mart_state_sales` | Purchase month × customer state | Commercial concentration and delivery experience |
| `mart_customer_rfm` | `customer_unique_id` | Historical recency, frequency and monetary features |

SQL templates use an allow-listed relation marker and a dialect-specific date-difference expression. The business aggregations are shared. DuckDB executes them in tests and on the full source; the BigQuery dialect is parsed in CI and the loader executes it in GCP when configured.

## Publication semantics

Local runs are built in a temporary directory. A successful run is moved to its immutable run directory, then `latest.json` is replaced atomically. Failed validation cannot advance the pointer. Source SHA-256 values and Parquet hashes support provenance and tamper checks. Raw files are never edited by the pipeline.

BigQuery uses a new dataset for each release. All tables and marts load there first. Row counts, six GMV totals and the recorded-payment total must reconcile before the canonical dataset's views are updated. Each view update is atomic; the collection of view updates is not one atomic transaction. Consumers needing an exact release should connect to the snapshot dataset reported in the publication manifest.

Facts are partitioned by purchase timestamp/date and clustered by order status and customer ID. This is a batch full refresh for a small historical dataset. There is no fictional incremental source, CDC feed or daily sales refresh.

## Time and money

Source timestamps do not carry a timezone. I retain timezone-unspecified civil times in pandas/Parquet and do not assume they are UTC. BigQuery's Parquet logical mapping must be checked during live cloud acceptance; Power BI uses import mode and explicit types. Delivery durations compare source timestamps consistently. Lateness compares calendar dates, because the estimated date is a promise date rather than a precise midnight deadline.

All source monetary fields are parsed through `Decimal` and stored as signed INT64 cents after rejecting negative, nonfinite and fractional-cent values. Real-valued ratios/averages may be floating point; monetary totals remain integers. Power BI converts cents to BRL inside measures.
