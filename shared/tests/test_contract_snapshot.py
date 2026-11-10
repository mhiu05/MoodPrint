import json
from pathlib import Path


def test_contract_snapshot():
    from moodprint_shared.testing.schemas import contract_schemas

    directory = Path(__file__).resolve().parents[1] / "contract-schemas"
    expected = contract_schemas()
    assert {path.name for path in directory.glob("*.json")} == set(expected)
    for name, schema in expected.items():
        assert json.loads((directory / name).read_text(encoding="utf-8")) == schema, name
