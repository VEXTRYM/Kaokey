import json
from pathlib import Path


def test_default_windows_list_is_valid():
    path = (
        Path(__file__).resolve().parents[1]
        / "data"
        / "kaomoji.json"
    )

    data = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    assert data["format_version"] == 1
    assert data["active_list"] == "Default"
    assert len(data["lists"]) == 1

    default_list = data["lists"][0]

    assert default_list["name"] == "Default"
    assert default_list["main_tags"] == [
        "Classic ASCII",
        "Happy",
        "Greetings",
        "Acting cute",
        "Sad",
        "Angry",
        "Surprised",
    ]

    kaomoji = default_list["kaomoji"]
    texts = [item["text"] for item in kaomoji]

    assert len(texts) == len(set(texts))
    assert len(texts) >= 250

    for expected in (
        "(✿◕‿◕✿)",
        "¯\_(ツ)_/¯",
        "ヾ(⌐■_■)ノ♪",
        "ლ(╹◡╹ლ)",
        "(⊙_◎)",
        "(∩^o^)⊃━☆",
        "/ᐠ｡ꞈ｡ᐟ\",
        "ᓚᘏᗢ",
    ):
        assert expected in texts
