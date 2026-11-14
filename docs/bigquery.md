# BigQuery deployment and acceptance

The repository contains a working loader and cloud workflow. Live cloud execution requires a **user-selected GCP project**, an enabled BigQuery API and authorized credentials. No project is guessed and no cloud deployment is claimed from a local fake-client test.

## Local authenticated deployment

Install the project with the locked development dependencies (which include the optional BigQuery client), or use `pip install '.[bigquery]'` for the minimal cloud extra.

```bash
gcloud auth login
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID
gcloud services enable bigquery.googleapis.com

retail download --raw-dir data/raw
retail run --raw-dir data/raw --output-dir data/processed --source-kind olist
retail bigquery --project YOUR_PROJECT_ID --dataset retail_analytics --location US
```

Choose the location deliberately and keep it the same for canonical and snapshot datasets. The command validates identifiers, refuses synthetic input unless `--allow-synthetic` is explicit, checks output hashes and requires a successful local quality/reconciliation report.

## What the loader does

1. Creates a new dataset such as `retail_analytics__<run_id>`.
2. Loads the four dimensions and three facts from Parquet with `WRITE_EMPTY`.
3. By default, partitions facts by `purchase_date`, clustering by status and customer ID. The explicit `--no-partitioning` option keeps the clustering but omits date partitions for historical Sandbox loads.
4. Creates the four SQL marts inside the snapshot.
5. Runs a SQL `COUNT(*)` for all 11 cloud tables and compares the results with the validated local manifest, instead of relying on table metadata counts.
6. Reconciles delivered GMV at item, order, month, category, state and customer grains, plus the recorded-payment total.
7. Creates/advances canonical views in `retail_analytics` only after snapshot validation passes.
8. Records snapshot dataset, job IDs, queried row counts, selected partitioning, returned retention settings and validation scope in `bigquery_publication.json`.

The query cap defaults to **1 GiB per query** and can be changed with `--maximum-bytes-billed`. This is a query safety limit, not a guarantee of free operation or a budget across the entire workflow. Storage and any other platform charges follow the selected GCP account's billing configuration.

Parquet timestamps are written at microsecond precision (`timestamp[us]`) with truncation disabled. The writer preserves timezone-naive source values and refuses any conversion that would lose submicrosecond data. BigQuery's Parquet loader supports millisecond/microsecond timestamps; a nanosecond export can be read as `INT64` and rejected as a partition key. Before any cloud writes, the loader checks the on-disk timestamp units and fact partition-column types.

`purchase_date` is stored as a Parquet timestamp without an invented timezone. Verify the resulting BigQuery column type and partitioning during live acceptance. Do not reinterpret it as a UTC business timestamp without a documented source timezone decision.

## Historical Olist data in BigQuery Sandbox

The Sandbox automatically expires tables, views and partitions after 60 days. A date partition's expiration is measured from the partition's date, not the upload date. Consequently, partitioning the 2016–2018 Olist source by `purchase_date` can cause historical partitions to disappear immediately. A completed load job alone does not demonstrate that the data was retained.

For this deployment, explicitly choose an unpartitioned historical load. The facts retain their original purchase dates and clustering. The Sandbox's table expiration still applies from table creation; the pipeline does not change dataset retention or billing settings.

```bash
git pull --ff-only
source .venv/bin/activate
python -m pip install --no-deps -e .
retail run --raw-dir data/raw --output-dir data/processed --source-kind olist
retail bigquery --project YOUR_PROJECT_ID --dataset retail_analytics --location US --no-partitioning
```

Reprocessing reuses the existing CSVs and produces a new snapshot name, leaving any failed snapshot intact. Before a partitioned upload, the loader checks the expiration settings returned by dataset creation and refuses to load historical dates that would already be expired. Partitioning remains the default for projects whose retention policy preserves the source dates.

A `0 != 99441` row-count message is not, by itself, proof of partition expiration. To inspect the actual failed table, run `bq show --format=prettyjson YOUR_PROJECT_ID:SNAPSHOT_DATASET.fct_orders` and check `timePartitioning.expirationMs`. The current loader validates data through SQL, which also distinguishes real missing rows from a metadata-count discrepancy. Promotion still requires all row counts and monetary reconciliations to pass.

## Recover from an INT64 partition-column error

If an earlier export fails with `The field specified for DAY partitioning can only be of type TIMESTAMP, DATETIME or DATE. The type found is: INT64`, update the code and regenerate the processed files. Reusing the original CSVs is sufficient; no new download or deletion is necessary. Run from the repository directory, replacing `YOUR_PROJECT_ID` with the selected project:

```bash
git pull --ff-only
source .venv/bin/activate
python -m pip install --no-deps -e .
retail run --raw-dir data/raw --output-dir data/processed --source-kind olist
retail bigquery --project YOUR_PROJECT_ID --dataset retail_analytics --location US
```

The new run gets a new manifest, output hashes and snapshot name. An incomplete snapshot from the previous failed load is not reused, and canonical views are only advanced after the new cloud validation passes.

## GitHub Actions with Workload Identity Federation

Use the `Publish BigQuery` manual workflow from `main`. It validates the local source before obtaining cloud credentials. It uses GitHub OIDC and short-lived credentials; no service-account JSON key is required. For a historical Sandbox deployment, disable the workflow's `partition_facts` checkbox; it passes the same `--no-partitioning` option to the loader.

Provision with an account allowed to enable APIs, manage service accounts and configure Workload Identity Federation. Replace `YOUR_PROJECT_ID` below with your own project. These commands are intended to run once in a dedicated project; if a named pool/provider already exists, inspect and reuse it rather than blindly recreating it.

```bash
export RETAIL_PROJECT_ID=YOUR_PROJECT_ID
export RETAIL_REPOSITORY=Pedroferreira32/retail-analytics-end-to-end
export RETAIL_PROJECT_NUMBER=$(gcloud projects describe "$RETAIL_PROJECT_ID" --format='value(projectNumber)')
export RETAIL_SA="retail-pipeline@${RETAIL_PROJECT_ID}.iam.gserviceaccount.com"

gcloud services enable bigquery.googleapis.com iamcredentials.googleapis.com sts.googleapis.com --project="$RETAIL_PROJECT_ID"
gcloud iam service-accounts create retail-pipeline --project="$RETAIL_PROJECT_ID" --display-name="Retail Analytics pipeline"

gcloud projects add-iam-policy-binding "$RETAIL_PROJECT_ID" \
  --member="serviceAccount:$RETAIL_SA" --role=roles/bigquery.user

gcloud iam workload-identity-pools create github-retail --project="$RETAIL_PROJECT_ID" \
  --location=global --display-name="GitHub Retail Analytics"

gcloud iam workload-identity-pools providers create-oidc github \
  --project="$RETAIL_PROJECT_ID" --location=global --workload-identity-pool=github-retail \
  --issuer-uri=https://token.actions.githubusercontent.com \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
  --attribute-condition="assertion.repository == '$RETAIL_REPOSITORY' && assertion.ref == 'refs/heads/main'"

gcloud iam service-accounts add-iam-policy-binding "$RETAIL_SA" --project="$RETAIL_PROJECT_ID" \
  --role=roles/iam.workloadIdentityUser \
  --member="principal://iam.googleapis.com/projects/$RETAIL_PROJECT_NUMBER/locations/global/workloadIdentityPools/github-retail/subject/repo:$RETAIL_REPOSITORY:environment:bigquery"
```

`roles/bigquery.user` permits query jobs and dataset creation. The creator has ownership of newly created datasets. For a pre-existing canonical dataset, explicitly grant the pipeline service account an appropriate dataset-scoped role such as BigQuery Data Editor. Do not grant project-wide Data Owner merely to work around an unexplained permission error.

Create the GitHub environment `bigquery` and configure these **environment variables**:

| Variable | Value |
| --- | --- |
| `GCP_PROJECT_ID` | Your selected project ID |
| `GCP_WIF_PROVIDER` | `projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/github-retail/providers/github` |
| `GCP_SERVICE_ACCOUNT` | `retail-pipeline@PROJECT_ID.iam.gserviceaccount.com` |
| `BQ_DATASET` | `retail_analytics` |
| `BQ_LOCATION` | `US`, or your deliberately selected location |

The environment subject and repository/main-branch conditions must match the workflow exactly. Forks and pull-request events do not obtain these credentials. Protected environment reviews are optional repository governance, not a requirement imposed by the project.

## Power BI access

Set `DataSourceMode=BigQuery`, `BillingProject` to the selected project and `BigQueryDataset` to either the canonical dataset or a fixed snapshot. The report uses import mode.

A reporting identity needs permission to run query jobs and read the referenced datasets. Canonical views do not automatically authorize access to their source tables: grant read access to the selected snapshot too, or intentionally configure authorized views. Authenticate through the supported Power BI connector; no credentials are embedded in PBIP files.

## Rollback and retention

A failed load/validation leaves the previous canonical views intact. A failed promotion can leave some views on the old snapshot and some on the new snapshot; the set of DDL statements is not atomic. For a consistent multi-table release, connect Power BI to a fixed snapshot dataset.

To roll back, use the previous successful `snapshot_dataset` value and replace each canonical view's `SELECT` with the same table in that snapshot. Verify all 11 view definitions before refreshing a report. A new cloud run intentionally creates a new snapshot; retrying publication for an already created dataset fails rather than appending or overwriting silently.

Snapshots are retained until deliberately removed. Review storage and retention after successful cloud acceptance; no automated deletion of historical releases is configured.

## Acceptance checklist

- [ ] BigQuery API and actual selected project are accessible.
- [ ] All 11 tables have the local manifest row counts.
- [ ] Facts use the partitioning recorded in `bigquery_publication.json` and retain the configured clustering; historical Sandbox loads use `fact_partitioning: none`.
- [ ] Dataset/table retention settings preserve the historical rows for the intended demonstration period.
- [ ] Six GMV totals and recorded payments reconcile in GCP.
- [ ] No assumption about timestamp timezone was introduced by the Parquet mapping.
- [ ] Reporting identity can read the selected snapshot and create query jobs.
- [ ] Publication job IDs and the snapshot are recorded.

References: [batch loading](https://docs.cloud.google.com/bigquery/docs/batch-loading-data), [Sandbox limitations](https://docs.cloud.google.com/bigquery/docs/sandbox#limitations), [partition expiration](https://docs.cloud.google.com/bigquery/docs/managing-partitioned-tables#set_the_partition_expiration), [Parquet type conversion](https://docs.cloud.google.com/bigquery/docs/loading-data-cloud-storage-parquet#type_conversions), [Arrow timestamp coercion](https://arrow.apache.org/docs/python/generated/pyarrow.parquet.write_table.html), [BigQuery authentication](https://docs.cloud.google.com/bigquery/docs/authentication), [GitHub OIDC authentication action](https://github.com/google-github-actions/auth).
