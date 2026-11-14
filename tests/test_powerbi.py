import importlib.util
from pathlib import Path


def test_powerbi_definitions_and_model_bindings():
    path = Path(__file__).resolve().parents[1] / "scripts" / "validate_powerbi.py"
    spec = importlib.util.spec_from_file_location("validate_powerbi", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.validate()
    assert result["pages"] == 4
    assert result["tables"] == 7
    assert result["relationships"] == 8
    assert result["visuals"] == 32
    assert result["measures"] == 20
