import json
from pathlib import Path


def test_windows_default_export_shape():
    path = (
        Path(__file__).resolve().parents[1]
        / "data"
        / "Windows Default.json"
    )

    data = json.loads(
        path.read_text(encoding="utf-8")
    )

    assert data["format_version"] == 1
    assert data["type"] == "kaokey_list"
    assert data["list"]["name"] == "Default"
    assert len(data["list"]["kaomoji"]) == 353


def test_windows_default_has_expected_categories():
    path = (
        Path(__file__).resolve().parents[1]
        / "data"
        / "Windows Default.json"
    )

    data = json.loads(
        path.read_text(encoding="utf-8")
    )

    assert data["list"]["main_tags"] == [
        "Classic ASCII",
        "Happy",
        "Greetings",
        "Acting cute",
        "Sad",
        "Angry",
        "Surprised",
    ]
