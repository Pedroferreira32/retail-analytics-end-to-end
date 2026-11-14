"""Generate a versionable PBIP/PBIR report and TMSL semantic model.

Only metadata is committed. Run prepare_powerbi.py to copy a validated run's CSVs.
Power BI Desktop must perform the final refresh, DAX execution and PBIX export.
"""

import argparse
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import pandas as pd

from retail_analytics.pipeline import resolve_run, write_json
from retail_analytics.warehouse import MODEL_TABLES

SCHEMA = "https://developer.microsoft.com/json-schemas/"


def field(table: str, name: str, measure: bool = False) -> dict:
    return {
        "Measure" if measure else "Column": {
            "Expression": {"SourceRef": {"Entity": table}},
            "Property": name,
        }
    }


def projection(table: str, name: str, measure: bool = False) -> dict:
    return {
        "field": field(table, name, measure),
        "queryRef": f"{table}.{name}",
        "nativeQueryRef": name,
    }


def literal(value) -> dict:
    if isinstance(value, bool):
        text = "true" if value else "false"
    elif isinstance(value, str):
        text = "'" + value.replace("'", "''") + "'"
    else:
        text = str(value) + "D"
    return {"expr": {"Literal": {"Value": text}}}


def visual(
    name: str,
    visual_type: str,
    title: str,
    x: int,
    y: int,
    width: int,
    height: int,
    roles: dict,
    sort_field: dict | None = None,
) -> dict:
    query = {"queryState": {role: {"projections": values} for role, values in roles.items()}}
    if sort_field:
        query["sortDefinition"] = {"sort": [{"field": sort_field, "direction": "Descending"}]}
    return {
        "$schema": SCHEMA + "fabric/item/report/definition/visualContainer/2.4.0/schema.json",
        "name": name,
        "position": {
            "x": x,
            "y": y,
            "width": width,
            "height": height,
            "z": y + x,
            "tabOrder": y + x,
        },
        "visual": {
            "visualType": visual_type,
            "query": query,
            "visualContainerObjects": {
                "title": [
                    {
                        "properties": {
                            "show": literal(True),
                            "text": literal(title),
                            "fontSize": literal(13),
                        }
                    }
                ],
                "background": [
                    {
                        "properties": {
                            "show": literal(True),
                            "color": {"solid": {"color": literal("#FFFFFF")}},
                            "transparency": literal(0),
                        }
                    }
                ],
            },
        },
    }


def order_context(base: str) -> str:
    """Apply product/seller item filters explicitly to an order-level measure."""
    return (
        "VAR _HasItemFilter = ISCROSSFILTERED(dim_products) || ISCROSSFILTERED(dim_sellers)\n"
        "RETURN IF(_HasItemFilter,\n"
        f"    CALCULATE({base}, KEEPFILTERS(TREATAS(VALUES(fct_order_items[order_id]), "
        "fct_orders[order_id]))),\n"
        f"    {base})"
    )


def measures() -> list[dict]:
    delivered = "KEEPFILTERS(fct_orders[is_eligible_gmv] = TRUE())"
    observed = "KEEPFILTERS(fct_orders[delivery_observed] = TRUE())"
    definitions = [
        (
            "GMV entregue",
            "CALCULATE(SUM(fct_order_items[price_cents]), "
            "KEEPFILTERS(fct_order_items[is_eligible_gmv] = TRUE())) / 100",
            '"R$ "#,0.00',
            "Valor das mercadorias de pedidos entregues; exclui frete. Não é receita da Olist.",
        ),
        (
            "Frete entregue",
            "CALCULATE(SUM(fct_order_items[freight_value_cents]), "
            "KEEPFILTERS(fct_order_items[is_eligible_gmv] = TRUE())) / 100",
            '"R$ "#,0.00',
            "Frete associado aos itens entregues.",
        ),
        (
            "Pedidos realizados",
            order_context("COUNTROWS(fct_orders)"),
            "#,0",
            "Todos os status por data de compra.",
        ),
        (
            "Pedidos entregues",
            order_context(f"CALCULATE(COUNTROWS(fct_orders), {delivered})"),
            "#,0",
            "Um pedido entregue, independentemente de quantos itens ou pagamentos possui.",
        ),
        (
            "Ticket médio",
            "DIVIDE([GMV entregue], [Pedidos entregues])",
            '"R$ "#,0.00',
            "GMV dividido por pedidos entregues no contexto selecionado.",
        ),
        (
            "Pedidos cancelados",
            order_context(
                "CALCULATE(COUNTROWS(fct_orders), "
                'KEEPFILTERS(fct_orders[order_status] = "canceled"))'
            ),
            "#,0",
            "Status canceled.",
        ),
        (
            "Taxa de cancelamento",
            "DIVIDE([Pedidos cancelados], [Pedidos realizados])",
            "0.00%",
            "Pedidos cancelados divididos por todos os pedidos realizados.",
        ),
        (
            "Entregas observadas",
            order_context(f"CALCULATE(COUNTROWS(fct_orders), {observed})"),
            "#,0",
            "Entregues com timestamps válidos e duração não negativa.",
        ),
        (
            "Entregas atrasadas",
            order_context(
                "CALCULATE(COUNTROWS(fct_orders), KEEPFILTERS(fct_orders[is_late] = TRUE()))"
            ),
            "#,0",
            "Após a data prometida.",
        ),
        (
            "Taxa de atraso",
            "DIVIDE([Entregas atrasadas], [Entregas observadas])",
            "0.00%",
            "Denominador inclui somente entregas efetivamente observadas.",
        ),
        (
            "Prazo médio dias",
            order_context("AVERAGE(fct_orders[delivery_days])"),
            "0.0",
            "Dias corridos entre compra e entrega; não é prazo de pedidos ainda abertos.",
        ),
        (
            "Nota média",
            order_context(f"CALCULATE(AVERAGE(fct_orders[review_score]), {delivered})"),
            "0.00",
            "Última avaliação por pedido entregue. Não é NPS.",
        ),
        (
            "Pedidos entregues avaliados",
            order_context(f"CALCULATE(COUNT(fct_orders[review_score]), {delivered})"),
            "#,0",
            "Pedidos entregues com nota preenchida.",
        ),
        (
            "Cobertura de avaliação",
            "DIVIDE([Pedidos entregues avaliados], [Pedidos entregues])",
            "0.0%",
            "Cobertura entre pedidos entregues; não é a nota média.",
        ),
        (
            "Pagamentos registrados",
            "SUM(fct_payments[payment_value_cents]) / 100",
            '"R$ "#,0.00',
            "Todos os status; não representa receita reconhecida nem liquidação bancária.",
        ),
        (
            "Diferença de pagamentos",
            "SUM(fct_orders[payment_difference_cents]) / 100",
            '"R$ "#,0.00',
            "Pagamento registrado menos itens e frete, em todos os status.",
        ),
        (
            "Pedidos com divergência",
            "COUNTROWS(FILTER(fct_orders, ABS(fct_orders[payment_difference_cents]) > 1))",
            "#,0",
            "Diferença absoluta superior a um centavo, em todos os status.",
        ),
        (
            "Itens entregues",
            "CALCULATE(COUNTROWS(fct_order_items), "
            "KEEPFILTERS(fct_order_items[is_eligible_gmv] = TRUE()))",
            "#,0",
            "Linhas de itens entregues.",
        ),
        (
            "GMV mês anterior",
            "CALCULATE([GMV entregue], DATEADD(dim_date[date], -1, MONTH))",
            '"R$ "#,0.00',
            "Comparação por data de compra; interpretar meses de borda com cautela.",
        ),
        (
            "Variação GMV mensal",
            "DIVIDE([GMV entregue] - [GMV mês anterior], [GMV mês anterior])",
            "0.0%",
            "Meses parciais/sem fechamento não permitem inferência de queda real.",
        ),
    ]
    return [
        {
            "name": name,
            "expression": expression,
            "formatString": fmt,
            "description": desc,
            "displayFolder": "Retail KPIs",
        }
        for name, expression, fmt, desc in definitions
    ]


def build(run: Path, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    semantic = output / "RetailAnalytics.SemanticModel"
    report = output / "RetailAnalytics.Report"
    semantic.mkdir(exist_ok=True)
    report.mkdir(exist_ok=True)
    for folder, kind in [(semantic, "SemanticModel"), (report, "Report")]:
        write_json(
            folder / ".platform",
            {
                "$schema": SCHEMA + "fabric/gitIntegration/platformProperties/2.0.0/schema.json",
                "metadata": {"type": kind, "displayName": "Retail Analytics"},
                "config": {
                    "version": "2.0",
                    "logicalId": str(
                        uuid5(
                            NAMESPACE_URL,
                            "https://github.com/Pedroferreira32/retail-analytics-end-to-end/"
                            + folder.name,
                        )
                    ),
                },
            },
        )
    write_json(
        output / "RetailAnalytics.pbip",
        {
            "$schema": SCHEMA + "fabric/pbip/pbipProperties/1.0.0/schema.json",
            "version": "1.0",
            "artifacts": [{"report": {"path": "RetailAnalytics.Report"}}],
            "settings": {"enableAutoRecovery": True},
        },
    )
    write_json(
        semantic / "definition.pbism",
        {
            "$schema": SCHEMA + "fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
            "version": "4.0",
            "settings": {"qnaEnabled": False},
        },
    )
    write_json(
        report / "definition.pbir",
        {
            "$schema": SCHEMA + "fabric/item/report/definitionProperties/2.0.0/schema.json",
            "version": "4.0",
            "datasetReference": {"byPath": {"path": "../RetailAnalytics.SemanticModel"}},
        },
    )
    types = {
        "string": ("string", "type text"),
        "integer": ("int64", "Int64.Type"),
        "boolean": ("boolean", "type logical"),
        "datetime": ("dateTime", "type datetime"),
        "float": ("double", "type number"),
    }
    tables = []
    for name in MODEL_TABLES:
        frame = pd.read_parquet(run / "parquet" / f"{name}.parquet")
        columns, mappings = [], []
        for col in frame:
            dtype = frame[col].dtype
            kind = (
                "boolean"
                if pd.api.types.is_bool_dtype(dtype)
                else "integer"
                if pd.api.types.is_integer_dtype(dtype)
                else "datetime"
                if pd.api.types.is_datetime64_any_dtype(dtype)
                else "float"
                if pd.api.types.is_float_dtype(dtype)
                else "string"
            )
            pbi_type, m_type = types[kind]
            column = {"name": col, "dataType": pbi_type, "sourceColumn": col, "summarizeBy": "none"}
            if col.endswith("_cents") or col.endswith("_id") or col == "date_key":
                column["isHidden"] = True
            if col == "date" and name == "dim_date":
                column["isKey"] = True
                column["formatString"] = "yyyy-MM-dd"
            columns.append(column)
            mappings.append('{"' + col + '", ' + m_type + "}")
        query = [
            "let",
            '    Raw = if DataSourceMode = "BigQuery" then',
            "        let",
            "            Projects = GoogleBigQuery.Database([BillingProject=BillingProject, "
            'Implementation="2.0"]),',
            "            Project = Projects{[Name=BillingProject]}[Data],",
            '            Dataset = Project{[Name=BigQueryDataset, Kind="Schema"]}[Data]',
            f'        in Dataset{{[Name="{name}"]}}[Data]',
            "    else",
            f'        Table.PromoteHeaders(Csv.Document(File.Contents(DataFolder & "/{name}.csv"),',
            '            [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]), '
            "[PromoteAllScalars=true]),",
            '    EmptyToNull = Table.ReplaceValue(Raw, "", null, Replacer.ReplaceValue, '
            "Table.ColumnNames(Raw)),",
            "    Typed = Table.TransformColumnTypes(EmptyToNull, {"
            + ", ".join(mappings)
            + '}, "en-US")',
            "in Typed",
        ]
        table = {
            "name": name,
            "columns": columns,
            "partitions": [
                {"name": name, "mode": "import", "source": {"type": "m", "expression": query}}
            ],
        }
        if name == "fct_orders":
            table["measures"] = measures()
        if name == "dim_date":
            table["dataCategory"] = "Time"
        tables.append(table)
    relationships = []
    for fact in ["fct_orders", "fct_order_items", "fct_payments"]:
        for dim, key in [("dim_date", "date_key"), ("dim_customers", "customer_id")]:
            relationships.append(
                {
                    "name": f"{fact}_{dim}",
                    "fromTable": fact,
                    "fromColumn": key,
                    "toTable": dim,
                    "toColumn": key,
                    "fromCardinality": "many",
                    "toCardinality": "one",
                    "crossFilteringBehavior": "oneDirection",
                }
            )
    for dim, key in [("dim_products", "product_id"), ("dim_sellers", "seller_id")]:
        relationships.append(
            {
                "name": f"fct_order_items_{dim}",
                "fromTable": "fct_order_items",
                "fromColumn": key,
                "toTable": dim,
                "toColumn": key,
                "fromCardinality": "many",
                "toCardinality": "one",
                "crossFilteringBehavior": "oneDirection",
            }
        )
    expressions = []
    for name, value in [
        ("DataFolder", r"C:\RetailAnalytics\powerbi\data"),
        ("DataSourceMode", "CSV"),
        ("BillingProject", "your-project-id"),
        ("BigQueryDataset", "retail_analytics"),
    ]:
        expressions.append(
            {
                "name": name,
                "kind": "m",
                "expression": f'"{value}" meta [IsParameterQuery=true, Type="Text", '
                "IsParameterQueryRequired=true]",
            }
        )
    write_json(
        semantic / "model.bim",
        {
            "name": "RetailAnalytics",
            "compatibilityLevel": 1600,
            "model": {
                "culture": "pt-BR",
                "defaultPowerBIDataSourceVersion": "powerBI_V3",
                "dataAccessOptions": {"legacyRedirects": True, "returnErrorValuesAsNull": False},
                "tables": tables,
                "relationships": relationships,
                "expressions": expressions,
                "annotations": [{"name": "PBI_TimeIntelligenceEnabled", "value": "0"}],
            },
        },
    )
    definition = report / "definition"
    definition.mkdir(exist_ok=True)
    write_json(
        definition / "version.json",
        {
            "$schema": SCHEMA + "fabric/item/report/definition/versionMetadata/1.0.0/schema.json",
            "version": "2.0.0",
        },
    )
    write_json(
        definition / "report.json",
        {
            "$schema": SCHEMA + "fabric/item/report/definition/report/3.0.0/schema.json",
            "themeCollection": {},
        },
    )
    page_specs = [
        (
            "overview",
            "01 | Visão executiva",
            ["GMV entregue", "Pedidos entregues", "Ticket médio", "Taxa de atraso"],
        ),
        (
            "commerce",
            "02 | Produtos e regiões",
            ["GMV entregue", "Itens entregues", "Frete entregue", "Ticket médio"],
        ),
        (
            "delivery",
            "03 | Entregas e satisfação",
            ["Entregas observadas", "Prazo médio dias", "Nota média", "Cobertura de avaliação"],
        ),
        (
            "quality",
            "04 | Pagamentos e qualidade",
            [
                "Pagamentos registrados",
                "Diferença de pagamentos",
                "Pedidos com divergência",
                "Taxa de cancelamento",
            ],
        ),
    ]
    (definition / "pages").mkdir(exist_ok=True)
    write_json(
        definition / "pages" / "pages.json",
        {
            "$schema": SCHEMA + "fabric/item/report/definition/pagesMetadata/1.1.0/schema.json",
            "pageOrder": [p[0] for p in page_specs],
            "activePageName": "overview",
        },
    )
    for page_name, label, cards in page_specs:
        page = definition / "pages" / page_name
        page.mkdir(exist_ok=True)
        write_json(
            page / "page.json",
            {
                "$schema": SCHEMA + "fabric/item/report/definition/page/2.0.0/schema.json",
                "name": page_name,
                "displayName": label,
                "displayOption": "FitToPage",
                "width": 1440,
                "height": 900,
            },
        )
        visuals = [
            visual(
                f"card_{i}",
                "card",
                metric,
                24 + i * 354,
                90,
                336,
                125,
                {"Values": [projection("fct_orders", metric, True)]},
            )
            for i, metric in enumerate(cards)
        ]
        visuals.append(
            visual(
                "month_filter",
                "slicer",
                label + " | Mês da compra",
                24,
                10,
                690,
                65,
                {"Values": [projection("dim_date", "year_month")]},
            )
        )
        visuals.append(
            visual(
                "state_filter",
                "slicer",
                "Estado do cliente",
                732,
                10,
                684,
                65,
                {"Values": [projection("dim_customers", "customer_state")]},
            )
        )
        if page_name == "overview":
            visuals.extend(
                [
                    visual(
                        "monthly_gmv",
                        "lineChart",
                        "GMV por mês da compra | BRL",
                        24,
                        240,
                        870,
                        620,
                        {
                            "Category": [projection("dim_date", "year_month")],
                            "Y": [projection("fct_orders", "GMV entregue", True)],
                        },
                    ),
                    visual(
                        "state_sales",
                        "barChart",
                        "GMV por estado do cliente",
                        918,
                        240,
                        498,
                        620,
                        {
                            "Category": [projection("dim_customers", "customer_state")],
                            "Y": [projection("fct_orders", "GMV entregue", True)],
                        },
                        field("fct_orders", "GMV entregue", True),
                    ),
                ]
            )
        elif page_name == "commerce":
            visuals.extend(
                [
                    visual(
                        "category_sales",
                        "tableEx",
                        "Categorias | mercadorias entregues",
                        24,
                        240,
                        870,
                        620,
                        {
                            "Values": [
                                projection("dim_products", "product_category_name"),
                                projection("fct_orders", "GMV entregue", True),
                                projection("fct_orders", "Pedidos entregues", True),
                                projection("fct_orders", "Ticket médio", True),
                            ]
                        },
                        field("fct_orders", "GMV entregue", True),
                    ),
                    visual(
                        "seller_sales",
                        "barChart",
                        "GMV por estado do vendedor",
                        918,
                        240,
                        498,
                        620,
                        {
                            "Category": [projection("dim_sellers", "seller_state")],
                            "Y": [projection("fct_orders", "GMV entregue", True)],
                        },
                        field("fct_orders", "GMV entregue", True),
                    ),
                ]
            )
        elif page_name == "delivery":
            visuals.extend(
                [
                    visual(
                        "late_month",
                        "lineChart",
                        "Taxa de atraso por mês da compra",
                        24,
                        240,
                        690,
                        620,
                        {
                            "Category": [projection("dim_date", "year_month")],
                            "Y": [projection("fct_orders", "Taxa de atraso", True)],
                        },
                    ),
                    visual(
                        "state_delivery",
                        "tableEx",
                        "Entregas e avaliação por estado",
                        738,
                        240,
                        678,
                        620,
                        {
                            "Values": [
                                projection("dim_customers", "customer_state"),
                                projection("fct_orders", "Entregas observadas", True),
                                projection("fct_orders", "Taxa de atraso", True),
                                projection("fct_orders", "Nota média", True),
                            ]
                        },
                    ),
                ]
            )
        else:
            visuals.extend(
                [
                    visual(
                        "payment_types",
                        "barChart",
                        "Pagamentos por meio | todos os status",
                        24,
                        240,
                        690,
                        620,
                        {
                            "Category": [projection("fct_payments", "payment_type")],
                            "Y": [projection("fct_orders", "Pagamentos registrados", True)],
                        },
                        field("fct_orders", "Pagamentos registrados", True),
                    ),
                    visual(
                        "status_reconciliation",
                        "tableEx",
                        "Reconciliação por status do pedido",
                        738,
                        240,
                        678,
                        620,
                        {
                            "Values": [
                                projection("fct_orders", "order_status"),
                                projection("fct_orders", "Pedidos realizados", True),
                                projection("fct_orders", "Diferença de pagamentos", True),
                                projection("fct_orders", "Pedidos com divergência", True),
                            ]
                        },
                    ),
                ]
            )
        for v in visuals:
            folder = page / "visuals" / v["name"]
            folder.mkdir(parents=True, exist_ok=True)
            write_json(folder / "visual.json", v)
    dax = "\n\n".join(
        f"// {m['description']}\n{m['name']} =\n{m['expression']}" for m in measures()
    )
    (output / "measures.dax").write_text(dax + "\n", encoding="utf-8")
    write_json(
        output / "theme.json",
        {
            "name": "Retail Analytics",
            "dataColors": ["#176B87", "#E7A33E", "#518F76", "#CC6B5A"],
            "background": "#F3F6F8",
            "foreground": "#172B3A",
            "tableAccent": "#176B87",
            "textClasses": {
                "label": {"fontFace": "Segoe UI", "fontSize": 11},
                "title": {"fontFace": "Segoe UI Semibold", "fontSize": 14},
            },
        },
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--processed-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--output-dir", type=Path, default=Path("powerbi"))
    args = parser.parse_args()
    build(resolve_run(args.processed_dir), args.output_dir)
