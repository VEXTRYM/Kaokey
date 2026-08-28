def should_ignore_restore(
    scheduled_session: int,
    current_session: int,
    popup_visible: bool,
) -> bool:
    return (
        scheduled_session != current_session
        or not popup_visible
    )


def test_old_session_restore_is_ignored():
    assert should_ignore_restore(
        10,
        11,
        True,
    ) is True


def test_closed_popup_restore_is_ignored():
    assert should_ignore_restore(
        10,
        10,
        False,
    ) is True


def test_current_visible_session_can_restore():
    assert should_ignore_restore(
        10,
        10,
        True,
    ) is False
