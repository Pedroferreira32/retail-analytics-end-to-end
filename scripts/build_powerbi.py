"""Generate a versionable PBIP/PBIR report and TMSL semantic model.

Only metadata is committed. Run prepare_powerbi.py to copy a validated run's CSVs.
Power BI Desktop must perform the final refresh, DAX execution and PBIX export.
"""

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import pandas as pd

from retail_analytics.pipeline import resolve_run, write_json
from retail_analytics.warehouse import MODEL_TABLES

SCHEMA = "https://developer.microsoft.com/json-schemas/"

COLORS = {
    "navy": "#142D43",
    "teal": "#087F8C",
    "mint": "#85DDD4",
    "amber": "#AD5B23",
    "text": "#20384D",
    "muted": "#52677A",
    "line": "#DDE5EC",
    "canvas": "#F2F5F8",
    "white": "#FFFFFF",
}


def field(table: str, name: str, measure: bool = False) -> dict:
    return {
        "Measure" if measure else "Column": {
            "Expression": {"SourceRef": {"Entity": table}},
            "Property": name,
        }
    }


def projection(table: str, name: str, measure: bool = False, label: str = "") -> dict:
    result = {
        "field": field(table, name, measure),
        "queryRef": f"{table}.{name}",
        "nativeQueryRef": name,
    }
    if label:
        result["displayName"] = label
    return result


def literal(value) -> dict:
    if isinstance(value, bool):
        text = "true" if value else "false"
    elif isinstance(value, str):
        text = "'" + value.replace("'", "''") + "'"
    else:
        text = str(value) + "D"
    return {"expr": {"Literal": {"Value": text}}}


def fill(value: str) -> dict:
    return {"solid": {"color": literal(value)}}


def properties(**values) -> list[dict]:
    return [
        {"properties": {k: v if isinstance(v, dict) else literal(v) for k, v in values.items()}}
    ]


def padding(size: int = 0) -> list[dict]:
    return properties(top=size, bottom=size, left=size, right=size)


def visual(
    name: str,
    visual_type: str,
    title: str,
    x: int,
    y: int,
    width: int,
    height: int,
    roles: dict | None = None,
    sort_field: dict | None = None,
    sort_direction: str = "Descending",
) -> dict:
    result = {
        "$schema": SCHEMA + "fabric/item/report/definition/visualContainer/2.4.0/schema.json",
        "name": name,
        "position": {
            "x": x,
            "y": y,
            "width": width,
            "height": height,
            "z": 1000,
            "tabOrder": y * 1440 + x,
        },
        "visual": {
            "visualType": visual_type,
            "visualContainerObjects": {
                "title": properties(
                    show=bool(title),
                    text=title,
                    fontSize=13,
                    bold=True,
                    fontFamily="Segoe UI Semibold",
                    fontColor=fill(COLORS["text"]),
                    alignment="left",
                    titleWrap=True,
                ),
                "background": properties(show=True, color=fill(COLORS["white"]), transparency=0),
                "border": properties(show=True, color=fill(COLORS["line"]), radius=10, width=1),
                "padding": padding(16),
                "visualHeader": properties(show=True, foreground=fill(COLORS["muted"])),
            },
        },
    }
    if roles:
        query = {"queryState": {role: {"projections": values} for role, values in roles.items()}}
        if sort_field:
            query["sortDefinition"] = {"sort": [{"field": sort_field, "direction": sort_direction}]}
        result["visual"]["query"] = query
    return result


def unframed(v: dict) -> dict:
    v["visual"]["visualContainerObjects"].update(
        {
            "title": properties(show=False),
            "background": properties(show=False),
            "border": properties(show=False),
            "padding": padding(),
            "visualHeader": properties(show=False),
        }
    )
    return v


def textbox(name, text, x, y, width, height, size=14, color=None, bold=False, align="left"):
    v = unframed(visual(name, "textbox", "", x, y, width, height))
    v["visual"]["objects"] = {
        "general": [
            {
                "properties": {
                    "paragraphs": [
                        {
                            "textRuns": [
                                {
                                    "value": text,
                                    "textStyle": {
                                        "fontFamily": "Segoe UI Semibold" if bold else "Segoe UI",
                                        "fontSize": f"{size}px",
                                        "color": color or COLORS["text"],
                                    },
                                }
                            ],
                            "horizontalTextAlignment": align,
                        }
                    ]
                }
            }
        ],
    }
    return v


def panel(name, x, y, width, height, color, rounded=False):
    v = unframed(visual(name, "shape", "", x, y, width, height))
    v["position"]["z"] = 0
    v["visual"]["objects"] = {
        "shape": properties(tileShape="rectangleRounded" if rounded else "rectangle", roundEdge=10),
        "fill": [
            {
                "properties": {"fillColor": fill(color), "transparency": literal(0)},
                "selector": {"id": "default"},
            }
        ],
        "outline": [{"properties": {"show": literal(False)}, "selector": {"id": "default"}}],
    }
    return v


def navigation(page_name, target, label, x):
    active = page_name == target
    v = unframed(visual(f"nav_{target}", "actionButton", "", x, 180, 190, 46))
    text_color = COLORS["white"] if active else COLORS["text"]
    v["visual"]["objects"] = {
        "text": [
            {"properties": {"show": literal(True)}},
            {
                "properties": {
                    "text": literal(label),
                    "fontSize": literal(11),
                    "fontFamily": literal("Segoe UI Semibold"),
                    "fontColor": fill(text_color),
                    "horizontalAlignment": literal("center"),
                },
                "selector": {"id": "default"},
            },
        ],
        "fill": [
            {"properties": {"show": literal(True)}},
            {
                "properties": {"fillColor": fill(COLORS["teal"] if active else "#E5EBF0")},
                "selector": {"id": "default"},
            },
            {
                "properties": {"fillColor": fill(COLORS["navy"]), "transparency": literal(0)},
                "selector": {"id": "hover"},
            },
        ],
        "icon": properties(show=False),
        "outline": properties(show=False),
        "shape": properties(tileShape="rectangleRounded", roundEdge=8),
    }
    v["visual"]["objects"]["text"].append(
        {
            "properties": {"fontColor": fill(COLORS["white"])},
            "selector": {"id": "hover"},
        }
    )
    v["visual"]["visualContainerObjects"]["visualLink"] = properties(
        show=True,
        type="PageNavigation",
        navigationSection=target,
        tooltip=f"Abrir {label} (Ctrl + clique no modo de edição)",
    )
    v["howCreated"] = "InsertVisualButton"
    return v


def slicer(name, table, column, title, x, width):
    v = visual(
        name,
        "slicer",
        "",
        x,
        152,
        width,
        84,
        {"Values": [projection(table, column, label=title)]},
        field(table, column),
        "Ascending",
    )
    v["visual"]["visualContainerObjects"].update(
        {
            "padding": padding(10),
            "visualHeader": properties(show=False),
        }
    )
    v["visual"]["objects"] = {
        "data": properties(mode="Dropdown"),
        "header": properties(
            show=True, text=title, textSize=11, bold=True, fontColor=fill(COLORS["text"])
        ),
        "items": properties(
            textSize=11, fontColor=fill(COLORS["text"]), background=fill(COLORS["white"])
        ),
        "selection": properties(singleSelect=False, selectAllCheckboxEnabled=True),
    }
    return v


def kpi(index, metric, label, note, units=1, precision=0, accent=False):
    x = 32 + index * 348
    primary = index == 0
    value_color = COLORS["white"] if primary else COLORS["amber"] if accent else COLORS["navy"]
    label_color = "#E0F5F2" if primary else COLORS["muted"]
    v = unframed(
        visual(
            f"card_{index}",
            "card",
            "",
            x + 12,
            308,
            308,
            56,
            {"Values": [projection("fct_orders", metric, True)]},
        )
    )
    v["visual"]["objects"] = {
        "labels": properties(
            color=fill(value_color),
            fontFamily="Segoe UI Semibold",
            fontSize=30,
            labelDisplayUnits=units,
            labelPrecision=precision,
        ),
        "categoryLabels": properties(show=False),
        "wordWrap": properties(show=False),
    }
    return [
        panel(
            f"kpi_bg_{index}",
            x,
            258,
            332,
            152,
            COLORS["teal"] if primary else COLORS["white"],
            True,
        ),
        textbox(f"kpi_label_{index}", label, x + 14, 278, 304, 25, 16, label_color, True, "center"),
        v,
        textbox(f"kpi_note_{index}", note, x + 16, 376, 300, 26, 13, label_color, align="center"),
    ]


def top_n(v, table, column, metric, count=10):
    # Top-N is scoped to this visual, evaluated again after the page's slicers.
    col = {"Column": {"Expression": {"SourceRef": {"Source": "c"}}, "Property": column}}
    measure = {"Measure": {"Expression": {"SourceRef": {"Source": "m"}}, "Property": metric}}
    v["filterConfig"] = {
        "filters": [
            {
                "name": "top_categories",
                "field": field(table, column),
                "type": "TopN",
                "howCreated": "User",
                "filter": {
                    "Version": 2,
                    "From": [
                        {
                            "Name": "subquery",
                            "Type": 2,
                            "Expression": {
                                "Subquery": {
                                    "Query": {
                                        "Version": 2,
                                        "From": [
                                            {"Name": "c", "Entity": table, "Type": 0},
                                            {"Name": "m", "Entity": "fct_orders", "Type": 0},
                                        ],
                                        "Select": [{**col, "Name": "group"}],
                                        "OrderBy": [{"Direction": 2, "Expression": measure}],
                                        "Top": count,
                                    }
                                }
                            },
                        },
                        {"Name": "c", "Entity": table, "Type": 0},
                    ],
                    "Where": [
                        {
                            "Condition": {
                                "In": {
                                    "Expressions": [col],
                                    "Table": {"SourceRef": {"Source": "subquery"}},
                                }
                            }
                        }
                    ],
                },
            }
        ]
    }
    return v


def minimum_sample(v, metric, minimum):
    """Hide sparse trend points, without changing KPI calculations or the model."""
    v["filterConfig"] = {
        "filters": [
            {
                "name": "minimum_monthly_sample",
                "field": field("fct_orders", metric, True),
                "type": "Advanced",
                "howCreated": "User",
                "filter": {
                    "Version": 2,
                    "From": [{"Name": "m", "Entity": "fct_orders", "Type": 0}],
                    "Where": [
                        {
                            "Condition": {
                                "Comparison": {
                                    "ComparisonKind": 2,
                                    "Left": {
                                        "Measure": {
                                            "Expression": {"SourceRef": {"Source": "m"}},
                                            "Property": metric,
                                        }
                                    },
                                    "Right": {"Literal": {"Value": f"{minimum}L"}},
                                }
                            }
                        }
                    ],
                },
            }
        ]
    }
    return v


def chart(
    name,
    kind,
    title,
    subtitle,
    x,
    width,
    table,
    column,
    metric,
    color=None,
    units=1,
    precision=0,
    tooltips=(),
):
    roles = {"Category": [projection(table, column)], "Y": [projection("fct_orders", metric, True)]}
    if tooltips:
        roles["Tooltips"] = [projection("fct_orders", m, True) for m in tooltips]
    is_line = kind == "lineChart"
    v = visual(
        name,
        kind,
        title,
        x,
        464,
        width,
        328,
        roles,
        field(table, column) if is_line else field("fct_orders", metric, True),
        "Ascending" if is_line else "Descending",
    )
    v["visual"]["visualContainerObjects"]["subTitle"] = properties(
        show=True,
        text=subtitle,
        fontSize=10,
        fontColor=fill(COLORS["muted"]),
        titleWrap=True,
    )
    color = color or COLORS["teal"]
    v["visual"]["objects"] = {
        "legend": properties(show=False),
        "dataPoint": properties(defaultColor=fill(color), fill=fill(color)),
        "categoryAxis": properties(
            show=True,
            showAxisTitle=False,
            fontSize=10,
            labelColor=fill(COLORS["muted"]),
            maxMarginFactor=35,
        ),
        "valueAxis": properties(
            show=True,
            showAxisTitle=False,
            fontSize=10,
            start=0,
            labelColor=fill(COLORS["muted"]),
            gridlineShow=True,
            gridlineColor=fill("#E5EBF0"),
            gridlineThickness=1,
            labelDisplayUnits=units,
            labelPrecision=precision,
        ),
        "labels": properties(
            show=not is_line,
            color=fill(COLORS["text"]),
            fontSize=10,
            labelDisplayUnits=units,
            labelPrecision=precision,
        ),
    }
    if is_line:
        v["visual"]["objects"]["lineStyles"] = properties(
            strokeWidth=3,
            showMarker=False,
            strokeColor=fill(color),
        )
    return v


def reconciliation_table():
    columns = [
        ("order_status", "Status"),
        ("Pedidos realizados", "Pedidos"),
        ("Diferença de pagamentos", "Saldo (R$)"),
        ("Pedidos com divergência", "Divergências"),
    ]
    v = visual(
        "status_reconciliation",
        "tableEx",
        "Em quais status há diferenças?",
        736,
        464,
        672,
        328,
        {
            "Values": [
                projection("fct_orders", name, i > 0, label)
                for i, (name, label) in enumerate(columns)
            ]
        },
        field("fct_orders", "Pedidos com divergência", True),
    )
    v["visual"]["visualContainerObjects"].update(
        {
            "subTitle": properties(
                show=True,
                text="Saldo = pagamento − itens − frete • todos os status",
                fontSize=10,
                fontColor=fill(COLORS["muted"]),
            ),
            "stylePreset": properties(name="None"),
        }
    )
    v["visual"]["objects"] = {
        "grid": properties(
            gridVertical=False,
            gridHorizontal=True,
            gridHorizontalColor=fill("#E5EBF0"),
            rowPadding=4,
            textSize=11,
        ),
        "columnHeaders": properties(
            fontColor=fill(COLORS["white"]),
            backColor=fill(COLORS["navy"]),
            bold=True,
            fontSize=10,
            wordWrap=True,
            autoSizeColumnWidth=True,
            columnAdjustment="growToFit",
        ),
        "values": properties(
            fontColorPrimary=fill(COLORS["text"]),
            fontColorSecondary=fill(COLORS["text"]),
            backColorPrimary=fill(COLORS["white"]),
            backColorSecondary=fill("#F1F5F8"),
            fontSize=11,
            wordWrap=False,
        ),
        "total": properties(
            totals=True,
            label="Total",
            bold=True,
            fontSize=11,
            backColor=fill("#E5EFF1"),
            fontColor=fill(COLORS["text"]),
        ),
    }
    return v


PAGE_LAYOUTS = [
    {
        "name": "overview",
        "label": "01 | Visão executiva",
        "nav": "01  Visão geral",
        "title": "Quanto vendemos e onde está a demanda?",
        "subtitle": "Valor vendido, volume de pedidos e experiência de entrega em uma única visão.",
        "sections": ["EVOLUÇÃO DAS VENDAS", "CONCENTRAÇÃO POR DESTINO"],
        "cards": [
            (
                "GMV entregue",
                "Valor das mercadorias (GMV)",
                "Pedidos entregues • sem frete",
                1000000,
                2,
            ),
            ("Pedidos entregues", "Pedidos entregues", "Cada pedido é contado uma vez", 1, 0),
            ("Ticket médio", "Ticket médio por pedido", "GMV ÷ pedidos entregues", 1, 2),
            (
                "Taxa de atraso",
                "Entregas em atraso",
                "Entre entregas com datas válidas",
                1,
                2,
                True,
            ),
        ],
        "read": "GMV soma mercadorias entregues, sem frete; não é receita da Olist. "
        "Os meses nas bordas da base são incompletos: compare períodos fechados.",
    },
    {
        "name": "commerce",
        "label": "02 | Produtos e regiões",
        "nav": "02  Produtos",
        "title": "O que vende mais e de onde sai o pedido?",
        "subtitle": "Compare o mix de produtos e a origem dos vendedores no recorte selecionado.",
        "sections": ["MIX DE PRODUTOS", "ORIGEM DOS VENDEDORES"],
        "cards": [
            (
                "GMV entregue",
                "Valor das mercadorias (GMV)",
                "Pedidos entregues • sem frete",
                1000000,
                2,
            ),
            ("Itens entregues", "Itens entregues", "Linhas de itens, não pedidos", 1, 0),
            (
                "Frete entregue",
                "Frete dos itens entregues",
                "Separado do valor das mercadorias",
                1000000,
                2,
            ),
            ("Ticket médio", "Ticket médio por pedido", "GMV ÷ pedidos entregues", 1, 2),
        ],
        "read": "Passe o mouse nos rankings para ver pedidos e ticket. "
        "Um pedido pode ter várias categorias ou UFs de vendedor; "
        "os pedidos de cada grupo não devem ser somados.",
    },
    {
        "name": "delivery",
        "label": "03 | Entregas e satisfação",
        "nav": "03  Entregas",
        "title": "Como está a experiência de entrega?",
        "subtitle": "Acompanhe atrasos, prazo e satisfação com a base de cada indicador explícita.",
        "sections": ["ATRASO AO LONGO DO TEMPO", "ONDE INVESTIGAR PRIMEIRO"],
        "cards": [
            ("Taxa de atraso", "Entregas em atraso", "Entre entregas com datas válidas", 1, 2),
            (
                "Prazo médio dias",
                "Prazo médio de entrega",
                "Dias corridos • compra até entrega",
                1,
                1,
            ),
            ("Nota média", "Nota média dos clientes", "Escala de 1 a 5 • última avaliação", 1, 2),
            (
                "Cobertura de avaliação",
                "Pedidos entregues avaliados",
                "Com nota ÷ total entregue",
                1,
                1,
            ),
        ],
        "read": "Curva: mínimo de 100 entregas válidas por mês no recorte. "
        "Atraso = entrega após a data prometida. A nota usa a última avaliação do pedido entregue; "
        "cobertura é a proporção avaliada.",
    },
    {
        "name": "quality",
        "label": "04 | Pagamentos e qualidade",
        "nav": "04  Pagamentos",
        "title": "Os pagamentos conciliam com os pedidos?",
        "subtitle": "Observe os valores registrados e investigue diferenças; "
        "todos os status entram nesta análise.",
        "sections": ["MEIOS DE PAGAMENTO", "CONFERÊNCIA DOS VALORES"],
        "cards": [
            (
                "Pagamentos registrados",
                "Pagamentos registrados",
                "Todos os status de pedido",
                1000000,
                2,
            ),
            (
                "Diferença de pagamentos",
                "Saldo da reconciliação",
                "Pagamentos − itens − frete • R$ mil",
                1000,
                2,
            ),
            (
                "Pedidos com divergência",
                "Pedidos com divergência",
                "Diferença absoluta acima de R$ 0,01",
                1,
                0,
                True,
            ),
            ("Taxa de cancelamento", "Pedidos cancelados", "Cancelados ÷ pedidos realizados", 1, 2),
        ],
        "read": "Divergência = |pagamento − itens − frete| > R$ 0,01 por pedido. "
        "O saldo pode compensar diferenças: não é perda comprovada nem liquidação bancária. "
        "Pagamentos e GMV têm escopos distintos.",
    },
]


def theme():
    return {
        "name": "Retail Analytics",
        "dataColors": [COLORS["teal"], COLORS["navy"], COLORS["amber"], "#5B83A1", "#6C9E86"],
        "background": COLORS["white"],
        "foreground": COLORS["text"],
        "foregroundNeutralSecondary": COLORS["muted"],
        "foregroundNeutralTertiary": COLORS["muted"],
        "backgroundLight": "#E5EBF0",
        "backgroundNeutral": COLORS["canvas"],
        "tableAccent": COLORS["teal"],
        "textClasses": {
            "label": {"fontFace": "Segoe UI", "fontSize": 11, "color": COLORS["text"]},
            "title": {"fontFace": "Segoe UI Semibold", "fontSize": 13, "color": COLORS["text"]},
            "header": {"fontFace": "Segoe UI Semibold", "fontSize": 12, "color": COLORS["text"]},
            "callout": {"fontFace": "Segoe UI Semibold", "fontSize": 30, "color": COLORS["navy"]},
        },
        "visualStyles": {
            "*": {
                "*": {
                    "title": [
                        {
                            "fontColor": {"solid": {"color": COLORS["text"]}},
                            "fontFamily": "Segoe UI Semibold",
                            "fontSize": 13,
                        }
                    ],
                    "subTitle": [
                        {"fontColor": {"solid": {"color": COLORS["muted"]}}, "fontSize": 10}
                    ],
                    "background": [
                        {
                            "show": True,
                            "color": {"solid": {"color": COLORS["white"]}},
                            "transparency": 0,
                        }
                    ],
                    "padding": [{"top": 16, "bottom": 16, "left": 16, "right": 16}],
                }
            }
        },
    }


def build_layout(output: Path, report: Path):
    definition = report / "definition"
    definition.mkdir(exist_ok=True)
    write_json(
        definition / "version.json",
        {
            "$schema": SCHEMA + "fabric/item/report/definition/versionMetadata/1.0.0/schema.json",
            "version": "2.0.0",
        },
    )
    report_theme = theme()
    digest = hashlib.sha256(json.dumps(report_theme, sort_keys=True).encode()).hexdigest()[:8]
    theme_name = f"Retail-{digest}.json"
    resources = report / "StaticResources" / "RegisteredResources"
    resources.mkdir(parents=True, exist_ok=True)
    for old in resources.glob("Retail-*.json"):
        if old.name != theme_name:
            old.unlink()
    write_json(output / "theme.json", report_theme)
    write_json(resources / theme_name, report_theme)
    write_json(
        definition / "report.json",
        {
            "$schema": SCHEMA + "fabric/item/report/definition/report/3.0.0/schema.json",
            "themeCollection": {
                "customTheme": {
                    "name": theme_name,
                    "type": "RegisteredResources",
                    "reportVersionAtImport": {
                        "visual": "2.4.0",
                        "report": "3.0.0",
                        "page": "2.0.0",
                    },
                }
            },
            "resourcePackages": [
                {
                    "name": "RegisteredResources",
                    "type": "RegisteredResources",
                    "items": [{"name": theme_name, "path": theme_name, "type": "CustomTheme"}],
                }
            ],
            "objects": {"outspacePane": properties(expanded=False, visible=True)},
        },
    )
    (definition / "pages").mkdir(exist_ok=True)
    write_json(
        definition / "pages" / "pages.json",
        {
            "$schema": SCHEMA + "fabric/item/report/definition/pagesMetadata/1.1.0/schema.json",
            "pageOrder": [p["name"] for p in PAGE_LAYOUTS],
            "activePageName": "overview",
        },
    )
    for number, spec in enumerate(PAGE_LAYOUTS, 1):
        name = spec["name"]
        page = definition / "pages" / name
        page.mkdir(exist_ok=True)
        write_json(
            page / "page.json",
            {
                "$schema": SCHEMA + "fabric/item/report/definition/page/2.0.0/schema.json",
                "name": name,
                "displayName": spec["label"],
                "displayOption": "FitToPage",
                "width": 1440,
                "height": 900,
                "objects": {"background": properties(color=fill(COLORS["canvas"]), transparency=0)},
            },
        )
        visuals = [
            panel("header_bg", 0, 0, 1440, 130, COLORS["navy"]),
            panel("header_accent", 0, 130, 1440, 4, COLORS["teal"]),
            textbox("brand", "RETAIL / ANALYTICS", 32, 18, 700, 23, 14, COLORS["mint"], True),
            textbox(
                "page_index",
                f"0{number} / 04   •   OLIST 2016–2018",
                1078,
                20,
                330,
                22,
                12,
                "#D4E0EB",
                align="right",
            ),
            textbox("page_title", spec["title"], 32, 48, 1376, 44, 30, COLORS["white"], True),
            textbox("page_intro", spec["subtitle"], 32, 97, 1376, 27, 15, "#D4E0EB"),
            textbox(
                "nav_label", "EXPLORE O RELATÓRIO", 32, 152, 790, 22, 11, COLORS["muted"], True
            ),
            textbox(
                "nav_hint",
                "No modo de edição do Desktop, use Ctrl + clique para navegar.",
                32,
                234,
                790,
                19,
                11,
                COLORS["muted"],
            ),
            slicer("month_filter", "dim_date", "year_month", "Mês da compra", 850, 268),
            slicer("state_filter", "dim_customers", "customer_state", "UF do cliente", 1136, 272),
        ]
        visuals.extend(
            navigation(name, p["name"], p["nav"], 32 + i * 202) for i, p in enumerate(PAGE_LAYOUTS)
        )
        for i, card in enumerate(spec["cards"]):
            visuals.extend(kpi(i, *card))
        split = 736 if name == "quality" else 900
        visuals.extend(
            [
                textbox(
                    "section_left",
                    spec["sections"][0],
                    32,
                    438,
                    split - 48,
                    21,
                    11,
                    COLORS["muted"],
                    True,
                ),
                textbox(
                    "section_right",
                    spec["sections"][1],
                    split,
                    438,
                    1408 - split,
                    21,
                    11,
                    COLORS["muted"],
                    True,
                ),
            ]
        )
        if name == "overview":
            visuals.extend(
                [
                    chart(
                        "monthly_gmv",
                        "lineChart",
                        "Como as vendas evoluem?",
                        "GMV entregue por mês da compra • R$ milhões",
                        32,
                        852,
                        "dim_date",
                        "year_month",
                        "GMV entregue",
                        units=1000000,
                        precision=1,
                        tooltips=("Pedidos entregues", "Ticket médio"),
                    ),
                    top_n(
                        chart(
                            "state_sales",
                            "barChart",
                            "Onde estão os maiores mercados?",
                            "10 maiores UFs do cliente • GMV em R$ milhões",
                            900,
                            508,
                            "dim_customers",
                            "customer_state",
                            "GMV entregue",
                            color=COLORS["navy"],
                            units=1000000,
                            precision=2,
                            tooltips=("Pedidos entregues", "Ticket médio"),
                        ),
                        "dim_customers",
                        "customer_state",
                        "GMV entregue",
                    ),
                ]
            )
        elif name == "commerce":
            for vid, title, subtitle, x, width, table, column, color in [
                (
                    "category_sales",
                    "Quais categorias geram mais vendas?",
                    "10 maiores categorias • GMV em R$ milhões",
                    32,
                    852,
                    "dim_products",
                    "product_category_name",
                    COLORS["teal"],
                ),
                (
                    "seller_sales",
                    "De onde vêm os vendedores?",
                    "10 maiores UFs do vendedor • GMV em R$ milhões",
                    900,
                    508,
                    "dim_sellers",
                    "seller_state",
                    COLORS["navy"],
                ),
            ]:
                visuals.append(
                    top_n(
                        chart(
                            vid,
                            "barChart",
                            title,
                            subtitle,
                            x,
                            width,
                            table,
                            column,
                            "GMV entregue",
                            color=color,
                            units=1000000,
                            precision=2,
                            tooltips=("Pedidos entregues", "Ticket médio"),
                        ),
                        table,
                        column,
                        "GMV entregue",
                    )
                )
        elif name == "delivery":
            visuals.extend(
                [
                    minimum_sample(
                        chart(
                            "late_month",
                            "lineChart",
                            "O atraso aumenta ou diminui?",
                            "Taxa mensal • mínimo de 100 entregas válidas por ponto",
                            32,
                            852,
                            "dim_date",
                            "year_month",
                            "Taxa de atraso",
                            color=COLORS["amber"],
                            precision=1,
                            tooltips=("Entregas observadas", "Entregas atrasadas"),
                        ),
                        "Entregas observadas",
                        100,
                    ),
                    top_n(
                        chart(
                            "state_delivery",
                            "barChart",
                            "Quais UFs concentram os atrasos?",
                            "10 maiores por quantidade • taxa e base no tooltip",
                            900,
                            508,
                            "dim_customers",
                            "customer_state",
                            "Entregas atrasadas",
                            color=COLORS["amber"],
                            tooltips=("Taxa de atraso", "Entregas observadas", "Nota média"),
                        ),
                        "dim_customers",
                        "customer_state",
                        "Entregas atrasadas",
                    ),
                ]
            )
        else:
            visuals.extend(
                [
                    chart(
                        "payment_types",
                        "barChart",
                        "Como os clientes pagam?",
                        "Valor registrado por meio • R$ milhões • todos os status",
                        32,
                        688,
                        "fct_payments",
                        "payment_type",
                        "Pagamentos registrados",
                        color=COLORS["navy"],
                        units=1000000,
                        precision=2,
                    ),
                    reconciliation_table(),
                ]
            )
        visuals.extend(
            [
                panel("reading_bg", 32, 810, 1376, 62, "#E3EDF1", True),
                textbox("reading_label", "COMO LER", 48, 829, 109, 22, 12, COLORS["teal"], True),
                textbox("reading_note", spec["read"], 169, 822, 1221, 43, 13),
                textbox(
                    "source_note",
                    "Fonte: Olist / Kaggle  •  Base histórica  •  "
                    "Mês e UF filtram esta página; cada aba mantém sua própria seleção.",
                    32,
                    882,
                    1376,
                    17,
                    11,
                    COLORS["muted"],
                ),
            ]
        )
        visual_names = {v["name"] for v in visuals}
        # Remove obsolete generated visuals when changing the layout in place.
        for old in (page / "visuals").glob("*"):
            if old.is_dir() and old.name not in visual_names:
                shutil.rmtree(old)
        for v in visuals:
            folder = page / "visuals" / v["name"]
            folder.mkdir(parents=True, exist_ok=True)
            write_json(folder / "visual.json", v)


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
    build_layout(output, report)
    dax = "\n\n".join(
        f"// {m['description']}\n{m['name']} =\n{m['expression']}" for m in measures()
    )
    (output / "measures.dax").write_text(dax + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--processed-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--output-dir", type=Path, default=Path("powerbi"))
    args = parser.parse_args()
    build(resolve_run(args.processed_dir), args.output_dir)
