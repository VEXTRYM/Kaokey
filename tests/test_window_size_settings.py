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


def test_default_window_size():
    settings = SettingsManager(
        FakeStore()
    )

    assert settings.window_size == (
        500,
        350,
    )


def test_window_size_is_saved():
    store = FakeStore()

    settings = SettingsManager(
        store
    )

    settings.set_window_size(
        900,
        600,
    )

    assert settings.window_size == (
        900,
        600,
    )

    assert store.sync_count == 1


def test_window_size_is_clamped():
    store = FakeStore()

    settings = SettingsManager(
        store
    )

    settings.set_window_size(
        10,
        10000,
    )

    assert settings.window_size == (
        400,
        2000,
    )
