"""Offline Microsoft JSON-schema checks plus model/report referential checks.

This validates serialized definitions, not the Desktop engine, M connector or DAX runtime.
"""

import json
import re
from pathlib import Path
from uuid import UUID

import jsonschema
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT7

ROOT = Path(__file__).resolve().parents[1]
PREFIX = "https://developer.microsoft.com/json-schemas/"


def validate(root: Path = ROOT / "powerbi") -> dict:
    root = root.resolve()
    schemas = root / "schemas"
    required_checked = 0

    def require_file(path):
        nonlocal required_checked
        if not path.is_file():
            raise ValueError(f"Missing required Power BI file: {path.relative_to(root)}")
        required_checked += 1

    for relative in [
        "RetailAnalytics.pbip",
        "RetailAnalytics.Report/definition.pbir",
        "RetailAnalytics.Report/.platform",
        "RetailAnalytics.Report/definition/version.json",
        "RetailAnalytics.Report/definition/report.json",
        "RetailAnalytics.Report/definition/pages/pages.json",
        "RetailAnalytics.SemanticModel/.platform",
        "RetailAnalytics.SemanticModel/definition.pbism",
        "RetailAnalytics.SemanticModel/model.bim",
    ]:
        require_file(root / relative)

    # A valid JSON file does not prove that the complete Desktop item exists.
    logical_ids = []
    for kind in ["Report", "SemanticModel"]:
        platform = json.loads(
            (root / f"RetailAnalytics.{kind}" / ".platform").read_text(encoding="utf-8")
        )
        if platform.get("metadata", {}).get("type") != kind:
            raise ValueError(f"Invalid Power BI item type: RetailAnalytics.{kind}")
        logical_ids.append(UUID(platform["config"]["logicalId"]))
    if len(set(logical_ids)) != 2:
        raise ValueError("Power BI report and semantic model must have distinct logical IDs")

    def retrieve(uri: str):
        if not uri.startswith(PREFIX):
            raise ValueError(f"Unexpected schema URI: {uri}")
        path = (schemas / uri.removeprefix(PREFIX)).resolve()
        if not path.is_relative_to(schemas.resolve()):
            raise ValueError("Invalid schema path")
        return Resource.from_contents(
            json.loads(path.read_text(encoding="utf-8")), default_specification=DRAFT7
        )

    registry = Registry(retrieve=retrieve)
    checked = 0
    for path in root.rglob("*"):
        if schemas in path.parents or (
            path.suffix not in {".json", ".pbip", ".pbir", ".pbism"} and path.name != ".platform"
        ):
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        uri = data.get("$schema")
        if not uri:
            continue
        schema = retrieve(uri).contents
        validator = jsonschema.validators.validator_for(schema)(schema, registry=registry)
        errors = sorted(validator.iter_errors(data), key=lambda e: str(e.path))
        if errors:
            raise ValueError(f"{path}: {errors[0].message}")
        checked += 1
    model = json.loads(
        (root / "RetailAnalytics.SemanticModel" / "model.bim").read_text(encoding="utf-8")
    )["model"]
    tables = {t["name"]: {c["name"] for c in t["columns"]} for t in model["tables"]}
    measures = {t["name"]: {m["name"] for m in t.get("measures", [])} for t in model["tables"]}
    for relation in model["relationships"]:
        assert relation["fromColumn"] in tables[relation["fromTable"]]
        assert relation["toColumn"] in tables[relation["toTable"]]
        assert relation["crossFilteringBehavior"] == "oneDirection"
        assert relation["toTable"].startswith("dim_")
    for table in model["tables"]:
        for measure in table.get("measures", []):
            for source, column in re.findall(r"(\w+)\[([^\]]+)\]", measure["expression"]):
                assert column in tables[source], (
                    f"{measure['name']}: unknown field {source}.{column}"
                )
    report = root / "RetailAnalytics.Report" / "definition"
    version = json.loads((report / "version.json").read_text(encoding="utf-8"))
    if version["version"] != "2.0.0":
        raise ValueError("Expected PBIR definition format 2.0.0")
    metadata = json.loads((report / "pages" / "pages.json").read_text(encoding="utf-8"))
    if metadata.get("activePageName") not in metadata["pageOrder"]:
        raise ValueError("Power BI active page must be included in pageOrder")
    settings = json.loads((report / "report.json").read_text(encoding="utf-8"))
    custom_theme = settings["themeCollection"].get("customTheme")
    if not custom_theme:
        raise ValueError("The report must register its custom theme")
    registered = [
        item
        for package in settings.get("resourcePackages", [])
        if package["name"] == custom_theme["type"]
        for item in package["items"]
        if item["name"] == custom_theme["name"] and item["type"] == "CustomTheme"
    ]
    if len(registered) != 1:
        raise ValueError("The custom theme must have one matching resource registration")
    asset_root = root / "RetailAnalytics.Report" / "StaticResources" / custom_theme["type"]
    asset = (asset_root / registered[0]["path"]).resolve()
    if not asset.is_relative_to(asset_root.resolve()):
        raise ValueError("Invalid custom theme resource path")
    require_file(asset)
    theme_schema = json.loads(
        (schemas / "reportThemeSchema-2.159.json").read_text(encoding="utf-8")
    )
    jsonschema.Draft7Validator(theme_schema).validate(json.loads(asset.read_text(encoding="utf-8")))
    visuals = 0
    data_visuals = 0
    navigation_actions = 0
    for page_name in metadata["pageOrder"]:
        folder = report / "pages" / page_name
        require_file(folder / "page.json")
        page = json.loads((folder / "page.json").read_text(encoding="utf-8"))
        for path in (folder / "visuals").glob("*/visual.json"):
            visual = json.loads(path.read_text(encoding="utf-8"))
            position = visual["position"]
            assert position["x"] >= 0 and position["y"] >= 0
            assert position["x"] + position["width"] <= page["width"]
            assert position["y"] + position["height"] <= page["height"]
            config = visual["visual"]
            if config["visualType"] == "textbox":
                paragraphs = config["objects"]["general"][0]["properties"]["paragraphs"]
                if not isinstance(paragraphs, list) or not paragraphs:
                    raise ValueError(f"{path}: textbox paragraphs must be a native array")
            links = config.get("visualContainerObjects", {}).get("visualLink", [])
            for link in links:
                props = link["properties"]
                if props.get("type", {}).get("expr", {}).get("Literal", {}).get("Value") == (
                    "'PageNavigation'"
                ):
                    target = props["navigationSection"]["expr"]["Literal"]["Value"].strip("'")
                    if target not in metadata["pageOrder"]:
                        raise ValueError(f"{path}: navigation points to an unknown page")
                    navigation_actions += 1
            if config.get("query", {}).get("queryState"):
                data_visuals += 1
            for role in visual["visual"].get("query", {}).get("queryState", {}).values():
                for projection in role["projections"]:
                    kind, field = next(iter(projection["field"].items()))
                    table = field["Expression"]["SourceRef"]["Entity"]
                    names = measures[table] if kind == "Measure" else tables[table]
                    assert field["Property"] in names, f"{path}: unbound field"
            visuals += 1
    result = {
        "status": "passed",
        "microsoft_schema_documents_checked": checked,
        "required_project_files_checked": required_checked,
        "platform_descriptors_checked": len(logical_ids),
        "pbir_format_version": version["version"],
        "tables": len(tables),
        "relationships": len(model["relationships"]),
        "measures": sum(map(len, measures.values())),
        "pages": len(metadata["pageOrder"]),
        "visuals": visuals,
        "data_visuals": data_visuals,
        "navigation_actions": navigation_actions,
        "registered_custom_themes_checked": len(registered),
        "desktop_runtime_validated": False,
    }
    return result


if __name__ == "__main__":
    print(json.dumps(validate(), indent=2))
