from platforms.windows.insertion import (
    _async_key_is_down,
)


def test_async_key_high_bit_means_pressed():
    assert _async_key_is_down(
        -32768
    ) is True


def test_async_key_low_toggle_bit_does_not_mean_pressed():
    assert _async_key_is_down(
        1
    ) is False


def test_async_key_zero_means_released():
    assert _async_key_is_down(
        0
    ) is False
