def columns_for_width(
    available_width: int,
    minimum_column_width: int,
    spacing: int,
) -> int:
    """Return how many equal-width columns fit in the available width."""
    if minimum_column_width <= 0:
        raise ValueError(
            "minimum_column_width must be positive"
        )

    spacing = max(
        0,
        spacing,
    )

    available_width = max(
        0,
        available_width,
    )

    return max(
        1,
        (
            available_width
            + spacing
        )
        // (
            minimum_column_width
            + spacing
        ),
    )
