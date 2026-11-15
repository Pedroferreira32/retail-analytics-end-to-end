# Power BI report

This directory contains an editable Power BI project with **four report pages, seven imported tables, eight single-direction relationships and 20 DAX measures**. The semantic model is TMSL (`model.bim`), and the report uses the documented PBIR JSON format.

**Verification status:** Microsoft JSON schemas, visual/model bindings, relationship references and canvas bounds have been checked automatically. This environment has not executed Power BI Desktop, the DAX engine or a live BigQuery refresh. The PBIP is an authored project awaiting Desktop acceptance; a `.pbix` has not been fabricated.

The user supplied a native Desktop screenshot on 2026-11-15 showing the initial executive page loaded with the expected GMV, delivered-order, ticket and late-rate values. The redesigned layout described below still needs to be opened in Desktop; its static design previews are explicitly labelled and are not native screenshots.

## Atualizar o layout de um projeto que já funciona

1. Salve o relatório atual e **feche o Power BI Desktop**.
2. Extraia o ZIP novo em um caminho curto, por exemplo `C:\RA_novo`. Evite várias pastas do repositório dentro de outras pastas.
3. Na pasta `powerbi` do download novo, execute **`ATUALIZAR_LAYOUT.cmd`**.
4. Quando a janela abrir, selecione o **`RetailAnalytics.pbip` antigo**, que já carrega seus dados.
5. Abra novamente esse mesmo PBIP antigo. O atualizador troca somente `RetailAnalytics.Report` e cria um backup `RetailAnalytics.Report.bak-*` ao lado. O modelo semântico, os parâmetros, as credenciais locais e o cache de dados permanecem no projeto existente.

Alternativa manual: com o Desktop fechado, faça backup da pasta `RetailAnalytics.Report` antiga e substitua-a pela pasta de mesmo nome do download novo. Mantenha `RetailAnalytics.SemanticModel` e o PBIP atuais. Copie a pasta Report inteira, incluindo `.platform`, `definition` e `StaticResources`.

Para desfazer a atualização, feche o Desktop, retire a pasta Report nova e renomeie o backup para `RetailAnalytics.Report`.

## Redesigned four-page layout

The report now includes a navy header, readable text contrast, page navigation, dropdown filters, exact order counts, metric definitions, explicit chart units, sorted top-10 rankings and an interpretation strip. The theme is registered inside the Report item and loads with it. All 20 model measures and all M connections are unchanged.

The monthly late-rate chart displays a point only when that month's current selection has **at least 100 observed deliveries**. This visual-only sample filter prevents a month with a single delivery from setting the chart's entire scale; it does not alter the rate definition, cards or state ranking. The threshold is printed on the chart. The state ranking uses late-order counts, with rate, observed deliveries and review score in its tooltip. The product ranking similarly exposes orders and ticket in its tooltip.

[Layout guide and static previews](../docs/powerbi-layout.md). Each page keeps its own month/state slicer selection. In Desktop edit mode, use **Ctrl + click** on navigation buttons.

## Open with local data

From the repository root:

```bash
retail download --raw-dir data/raw
retail run --raw-dir data/raw --output-dir data/processed --source-kind olist
python scripts/prepare_powerbi.py
```

1. Use a current Windows Power BI Desktop version supporting PBIP/PBIR projects. Enable the project/report format features if your installed version requires it.
2. Open `powerbi/RetailAnalytics.pbip`.
3. In **Transform data → Manage parameters**, set `DataFolder` to the absolute path of the generated `powerbi/data` directory. Keep `DataSourceMode=CSV`.
4. Apply changes and refresh all seven tables. Do not combine the synthetic demonstration output with real Olist evidence.
5. The custom theme is already registered in the Report folder. `powerbi/theme.json` is also available for manual reuse in other reports.
6. Perform the acceptance checks below, then use **Save As → Power BI Desktop (.pbix)** if a PBIX export is needed.

Local source data and Desktop caches remain ignored by Git. The placeholder `C:\RetailAnalytics\powerbi\data` is a parameter default; replace it with your own checkout location.

## Recover an older project that does not open

The initial generated report omitted `RetailAnalytics.Report/definition/version.json` and the Report/SemanticModel item identity files. Checking only the JSON files that existed did not detect this incomplete Desktop structure. The generator now emits PBIR format metadata (`version: 2.0.0`), item descriptors with distinct stable logical IDs, and pages metadata 1.1.0 with the active page. The validator requires these startup files before checking individual schemas.

Download the updated repository ZIP, extract the complete archive into a new folder, and open the new `powerbi/RetailAnalytics.pbip`. The PBIP entry point is only a few hundred bytes; keep both `RetailAnalytics.Report` and `RetailAnalytics.SemanticModel` beside it. The corrected metadata must come from the new download, rather than an older extracted folder. `RetailAnalytics.Report/definition.pbir` is an alternative entry point.

This correction is validated against the published Microsoft schemas and missing-file regression cases. It is not a claim that the Windows Desktop engine has run in this environment. If Desktop still does not load, capture the specific error or a recent trace using **File → Options and settings → Options → Diagnostics → Enable tracing**.

## Connect to BigQuery

First complete the cloud load in [docs/bigquery.md](../docs/bigquery.md). Set:

| Parameter | Value |
| --- | --- |
| `DataSourceMode` | `BigQuery` |
| `BillingProject` | The authorized project that runs the connector's query jobs |
| `BigQueryDataset` | Canonical `retail_analytics` or a specific validated release dataset |
| `DataFolder` | Unused while in BigQuery mode |

M partitions select the BigQuery connector's project and dataset objects, then the named analytical table/view. The query definitions specify the connector's implementation 2.0. Authenticate in Desktop using an identity authorized for query jobs and reads. The project contains no embedded account credentials. The BigQuery M branch still requires live connector acceptance.

### Parameters for the published Retail Analytics warehouse

The live Cloud Shell load reported successful publication on 2026-11-14. In Windows Desktop, open **Transform data → Manage parameters** and set:

| Parameter | Value |
| --- | --- |
| `DataSourceMode` | `BigQuery` |
| `BillingProject` | `retail-analytics-514717` |
| `BigQueryDataset` | `retail_analytics` |

Authenticate the Google BigQuery connector with the Google identity authorized for this project, apply changes and refresh. `DataFolder` is unused in BigQuery mode. These deployment-specific values are documented rather than embedded into the portable project defaults.

For a fixed release, `BigQueryDataset` can instead be `retail_analytics__20261114T185754_e310b30c`. The snapshot has the Sandbox's 60-day retention. See the [visible cloud publication receipt](../docs/evidence/bigquery-cli-receipt.json); Desktop refresh and DAX acceptance remain pending.

## Pages and measures

| Page | Purpose | Main content |
| --- | --- | --- |
| 01 · Visão executiva | Understand commercial scale | GMV, delivered orders, average ticket, late rate, monthly GMV and customer-state distribution |
| 02 · Produtos e regiões | Inspect commercial mix | Category merchandise, item count, freight, ticket and seller-state distribution |
| 03 · Entregas e satisfação | Inspect the customer experience | Observed deliveries, delivery days, latest score, coverage, monthly late rate and state details |
| 04 · Pagamentos e qualidade | Inspect financial reconciliation | All-status payments, payment difference, divergent orders, cancellation rate and status detail |

Each page has purchase-month and customer-state slicers. Category counts are distinct orders in context; they must not be summed across categories. Product/seller filters use explicit `TREATAS` when an order-level KPI is needed. There are no bidirectional relationships or direct fact-to-fact joins.

The readable DAX source is [measures.dax](measures.dax). The authoritative generator is `scripts/build_powerbi.py`; update it before regenerating metadata so changes remain reproducible.

## Acceptance before publication

With every slicer cleared and the real Olist export loaded:

| Card / check | Expected |
| --- | ---: |
| GMV entregue | R$ 13.221.498,11 |
| Pedidos entregues | 96.478 |
| Ticket médio | R$ 137,04 |
| Taxa de atraso | 6,77% |
| Nota média | 4,16 |
| Cobertura de avaliação | 95.832 / 96.478 = 99,33% |
| Entregas observadas | 96.470 |
| Pagamentos registrados, all statuses | R$ 16.008.872,12 |
| Pedidos com divergência > 1 centavo | 1.076 |

- [ ] The project opens with no unsupported metadata/model errors.
- [ ] Every table refreshes; M type conversions and nullable logical values have no errors.
- [ ] All 32 data visuals and their static layout elements render, with no missing bindings or truncated values.
- [ ] The registered theme, dropdown filters and all four navigation destinations work.
- [ ] Monthly and state slicers reconcile against the corresponding SQL marts.
- [ ] Category selection filters order KPIs correctly through `TREATAS`.
- [ ] Switching CSV/BigQuery preserves baseline totals and purchase date meaning.
- [ ] Late sparse months are explained as incomplete observations.
- [ ] Export the verified PBIX and capture report screenshots only after these checks.

For Power BI Service publication, choose an authorized workspace, publish the validated Desktop report, configure the source credentials and verify the first service refresh. A local-file source usually needs an appropriate gateway/storage arrangement for refresh. A BigQuery source can be configured through the service's supported connector. Do not imply that a checked-in PBIP is already a published Service report.

## Automated checks

```bash
python scripts/validate_powerbi.py
```

The offline schemas are from [Microsoft's public JSON-schema repository](https://github.com/microsoft/json-schemas) and the [official report-theme schema collection](https://github.com/microsoft/powerbi-desktop-samples/tree/main/Report%20Theme%20JSON%20Schema). They retain their upstream license and fingerprints under `schemas/`. The validator also checks registered theme files, navigation targets and native textbox arrays. These checks validate serialized definitions; Desktop is the final runtime authority. Windows CI separately exercises the report-only updater and verifies that the existing model, cache and PBIP bytes are preserved.

Official references: [Power BI projects](https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-overview), [semantic-model folder](https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-dataset), [report folder](https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-report), [BigQuery connector](https://learn.microsoft.com/en-us/power-query/connectors/google-bigquery).
