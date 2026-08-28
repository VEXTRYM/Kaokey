from platforms.windows.insertion import is_native_text_control_class


def test_standard_edit_class_is_supported():
    assert is_native_text_control_class("Edit") is True


def test_windows_11_notepad_richedit_is_supported():
    assert is_native_text_control_class("RichEditD2DPT") is True


def test_other_richedit_variants_are_supported():
    assert is_native_text_control_class("RICHEDIT50W") is True


def test_browser_window_class_is_not_supported():
    assert is_native_text_control_class("Chrome_WidgetWin_1") is False


def test_none_is_not_supported():
    assert is_native_text_control_class(None) is False
