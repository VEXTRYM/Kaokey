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


def test_popup_size_defaults():
    settings = SettingsManager(
        FakeStore()
    )

    assert settings.popup_size == (
        440,
        300,
    )


def test_popup_size_is_saved():
    store = FakeStore()
    settings = SettingsManager(
        store
    )

    settings.set_popup_size(
        700,
        500,
    )

    assert settings.popup_size == (
        700,
        500,
    )


def test_popup_size_is_clamped():
    store = FakeStore()
    settings = SettingsManager(
        store
    )

    settings.set_popup_size(
        10,
        5000,
    )

    assert settings.popup_size == (
        320,
        1400,
    )


def test_add_space_after_insert_defaults_to_false():
    settings = SettingsManager(
        FakeStore()
    )

    assert settings.add_space_after_insert is False


def test_add_space_after_insert_is_saved():
    store = FakeStore()
    settings = SettingsManager(
        store
    )

    settings.add_space_after_insert = True

    assert settings.add_space_after_insert is True
