# Publication and continuation

The GitHub code publication, live BigQuery warehouse and Power BI report publication are separate deliverables with separate evidence. This avoids calling an unexecuted integration complete.

## Repository release

- [x] Repository structure, packaging and command-line entry point.
- [x] Original source download with archive checks and source fingerprints.
- [x] Complete real-source ETL, dimensional model, SQL marts and reconciliation.
- [x] Meaningful synthetic regression tests with an 80% minimum coverage gate.
- [x] Linux/Windows CI and manual full-source/cloud workflows.
- [x] Complete real Olist execution reproduced successfully on GitHub Actions; [execution evidence](evidence/validation.json).
- [x] Power BI semantic model, four-page report and 20 DAX measures.
- [x] Offline Microsoft-schema and visual/model-reference checks.
- [x] Inspectable real-source aggregate evidence and precise exported charts.
- [x] English, Portuguese, Italian and Spanish README entry points.
- [x] Attribution, licenses, quality rules, architecture, metric definitions and limitations.

## Cloud acceptance and remaining external work

- [x] Selected and authorized project `retail-analytics-514717`, location `US`.
- [x] Live BigQuery publication completed via authenticated Cloud Shell with `--no-partitioning`; [visible publication receipt](evidence/bigquery-cli-receipt.json) and [original screenshot](images/bigquery-publication.png).
- [x] All 11 SQL row counts matched; receipt reports the six GMV totals and payment reconciliation passed.
- [ ] Archive the complete Cloud Shell `bigquery_publication.json`, including all job IDs, and inspect actual table types/clustering. The current evidence is explicitly a screenshot transcription.
- [ ] Provision IAM/WIF and execute the BigQuery workflow from GitHub Actions.
- [ ] Open and refresh the PBIP in Windows Power BI Desktop.
- [ ] Execute DAX and filter acceptance against the documented SQL baseline.
- [ ] Export a genuine verified PBIX and capture actual report screenshots.
- [ ] Connect an authorized Power BI workspace and publish/refresh there.

Do not mark these items complete solely because metadata was generated or an API client was mocked. A source-backed project can be published on GitHub while these account-specific integrations are explicitly pending.

## Suggested next working session

1. Open the Desktop project and set the parameters for the published warehouse using [powerbi/README.md](../powerbi/README.md#connect-to-bigquery).
2. Complete Desktop refresh, DAX/filter acceptance, genuine screenshots and PBIX export.
3. Archive the full cloud receipt, configure IAM/WIF using [bigquery.md](bigquery.md), and complete the hosted cloud workflow and Service publication before tagging the final release.

CI passed on Linux and Windows. The complete [Olist workflow run](https://github.com/Pedroferreira32/retail-analytics-end-to-end/actions/runs/43622267281) also passed: original download, full ETL, reconciliation, aggregate evidence, Power BI data preparation and artifact upload. The generated artifact has seven-day retention; the committed code and source fingerprints remain the reproducible long-term record.
