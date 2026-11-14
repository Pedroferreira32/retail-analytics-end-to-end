import importlib.util
import json
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_powerbi_definitions_and_model_bindings():
    result = script("validate_powerbi").validate()
    assert result["pages"] == 4
    assert result["tables"] == 7
    assert result["relationships"] == 8
    assert result["visuals"] == 32
    assert result["measures"] == 20


def test_generator_emits_complete_desktop_bootstrap_metadata(validated_run, tmp_path):
    output = tmp_path / "powerbi"
    script("build_powerbi").build(validated_run, output)
    shutil.copytree(ROOT / "powerbi" / "schemas", output / "schemas")
    version = json.loads((output / "RetailAnalytics.Report/definition/version.json").read_text())
    assert version["version"] == "2.0.0"
    ids = []
    for kind in ["Report", "SemanticModel"]:
        platform = json.loads((output / f"RetailAnalytics.{kind}/.platform").read_text())
        assert platform["metadata"]["type"] == kind
        ids.append(platform["config"]["logicalId"])
    assert ids[0] != ids[1]
    result = script("validate_powerbi").validate(output)
    assert result["pbir_format_version"] == "2.0.0"
    assert result["platform_descriptors_checked"] == 2


@pytest.mark.parametrize(
    "relative",
    [
        "RetailAnalytics.Report/definition/version.json",
        "RetailAnalytics.Report/.platform",
        "RetailAnalytics.SemanticModel/.platform",
        "RetailAnalytics.Report/definition/report.json",
        "RetailAnalytics.Report/definition/pages/pages.json",
        "RetailAnalytics.Report/definition/pages/overview/page.json",
    ],
)
def test_missing_required_powerbi_files_are_rejected(tmp_path, relative):
    output = tmp_path / "powerbi"
    shutil.copytree(ROOT / "powerbi", output, ignore=shutil.ignore_patterns("data", ".pbi"))
    (output / relative).unlink(missing_ok=True)
    with pytest.raises(ValueError, match="Missing required Power BI file"):
        script("validate_powerbi").validate(output)
