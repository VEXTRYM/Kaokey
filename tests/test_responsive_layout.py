from responsive_layout import columns_for_width


def test_default_sized_grid_keeps_four_columns():
    assert columns_for_width(
        440,
        96,
        8,
    ) == 4


def test_wider_grid_adds_columns():
    assert columns_for_width(
        650,
        96,
        8,
    ) == 6


def test_narrow_grid_never_returns_zero_columns():
    assert columns_for_width(
        20,
        96,
        8,
    ) == 1
