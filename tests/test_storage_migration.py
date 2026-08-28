import json

from storage import ensure_user_data_file


def test_first_run_copies_existing_library(tmp_path):
    bundled = tmp_path / "bundle" / "kaomoji.json"
    user = tmp_path / "user" / "kaomoji.json"

    bundled.parent.mkdir(parents=True)
    bundled.write_text(
        '{"format_version": 1, "active_list": "Default", "lists": []}',
        encoding="utf-8",
    )

    ensure_user_data_file(
        data_path=user,
        default_data_path=bundled,
    )

    assert user.read_text(encoding="utf-8") == bundled.read_text(
        encoding="utf-8"
    )


def test_existing_user_library_is_never_overwritten(tmp_path):
    bundled = tmp_path / "bundle" / "kaomoji.json"
    user = tmp_path / "user" / "kaomoji.json"

    bundled.parent.mkdir(parents=True)
    user.parent.mkdir(parents=True)

    bundled.write_text("bundled", encoding="utf-8")
    user.write_text("user-data", encoding="utf-8")

    ensure_user_data_file(
        data_path=user,
        default_data_path=bundled,
    )

    assert user.read_text(encoding="utf-8") == "user-data"
