from settings import SettingsManager


class FakeStore:
    def __init__(
        self,
    ) -> None:
        self.values: dict[str, object] = {}

    def value(
        self,
        key: str,
        defaultValue: object = None,
        type: object = None,
    ) -> object:
        del type
        return self.values.get(
            key,
            defaultValue,
        )

    def setValue(
        self,
        key: str,
        value: object,
    ) -> None:
        self.values[key] = value

    def remove(
        self,
        key: str,
    ) -> None:
        self.values.pop(
            key,
            None,
        )

    def sync(
        self,
    ) -> None:
        pass


def test_hotkey_defaults_to_alt_k():
    settings = SettingsManager(
        FakeStore()
    )

    assert settings.hotkey == (
        "Alt",
        "K",
    )


def test_hotkey_round_trip():
    store = FakeStore()
    settings = SettingsManager(
        store
    )

    settings.set_hotkey(
        "Ctrl",
        "F12",
    )

    assert settings.hotkey == (
        "Ctrl",
        "F12",
    )


def test_invalid_saved_hotkey_falls_back():
    store = FakeStore()
    store.values[
        "input/hotkey_modifier"
    ] = "Win"
    store.values[
        "input/hotkey_key"
    ] = "Mouse4"

    settings = SettingsManager(
        store
    )

    assert settings.hotkey == (
        "Alt",
        "K",
    )
