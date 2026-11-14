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
3. Partitions facts by `purchase_date`, clustering by status and customer ID.
4. Creates the four SQL marts inside the snapshot.
5. Compares all 11 cloud row counts with the validated local manifest.
6. Reconciles delivered GMV at item, order, month, category, state and customer grains, plus the recorded-payment total.
7. Creates/advances canonical views in `retail_analytics` only after snapshot validation passes.
8. Records snapshot dataset, job IDs and validation scope in `bigquery_publication.json`.

The query cap defaults to **1 GiB per query** and can be changed with `--maximum-bytes-billed`. This is a query safety limit, not a guarantee of free operation or a budget across the entire workflow. Storage and any other platform charges follow the selected GCP account's billing configuration.

`purchase_date` is stored as a Parquet timestamp without an invented timezone. Verify the resulting BigQuery column type and partitioning during live acceptance. Do not reinterpret it as a UTC business timestamp without a documented source timezone decision.

## GitHub Actions with Workload Identity Federation

Use the `Publish BigQuery` manual workflow from `main`. It validates the local source before obtaining cloud credentials. It uses GitHub OIDC and short-lived credentials; no service-account JSON key is required.

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
- [ ] Facts are partitioned/clustered as specified.
- [ ] Six GMV totals and recorded payments reconcile in GCP.
- [ ] No assumption about timestamp timezone was introduced by the Parquet mapping.
- [ ] Reporting identity can read the selected snapshot and create query jobs.
- [ ] Publication job IDs and the snapshot are recorded.

References: [batch loading](https://docs.cloud.google.com/bigquery/docs/batch-loading-data), [BigQuery authentication](https://docs.cloud.google.com/bigquery/docs/authentication), [GitHub OIDC authentication action](https://github.com/google-github-actions/auth).
