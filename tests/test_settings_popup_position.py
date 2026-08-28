from settings import SettingsManager


class FakeStore:
    def __init__(
        self,
    ) -> None:
        self.values: dict[str, object] = {}
        self.sync_count = 0

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
        self.sync_count += 1


def test_clear_popup_position_removes_saved_coordinates():
    store = FakeStore()

    settings = SettingsManager(
        store
    )

    settings.set_popup_position(
        120,
        340,
    )

    assert settings.popup_position == (
        120,
        340,
    )

    settings.clear_popup_position()

    assert settings.popup_position is None


def test_clear_popup_position_syncs_store():
    store = FakeStore()

    settings = SettingsManager(
        store
    )

    settings.clear_popup_position()

    assert store.sync_count == 1
