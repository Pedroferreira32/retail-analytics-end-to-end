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

## External acceptance still required

- [ ] Select and authorize the actual GCP project and location.
- [ ] Execute a live BigQuery load and retain `bigquery_publication.json`.
- [ ] Open and refresh the PBIP in Windows Power BI Desktop.
- [ ] Execute DAX and filter acceptance against the documented SQL baseline.
- [ ] Export a genuine verified PBIX and capture actual report screenshots.
- [ ] Connect an authorized Power BI workspace and publish/refresh there.

Do not mark these items complete solely because metadata was generated or an API client was mocked. A source-backed project can be published on GitHub while these account-specific integrations are explicitly pending.

## Suggested next working session

1. Configure the `bigquery` environment and project IAM/WIF using [bigquery.md](bigquery.md).
2. Validate the Desktop project using [powerbi/README.md](../powerbi/README.md).
3. Add cloud job evidence and genuine report screenshots; update the status table and create a tagged release once external acceptance is complete.

CI passed on Linux and Windows. The complete [Olist workflow run](https://github.com/Pedroferreira32/retail-analytics-end-to-end/actions/runs/43622267281) also passed: original download, full ETL, reconciliation, aggregate evidence, Power BI data preparation and artifact upload. The generated artifact has seven-day retention; the committed code and source fingerprints remain the reproducible long-term record.
