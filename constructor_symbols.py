import json

from constants import (
    CONSTRUCTOR_SYMBOLS_PATH,
)


def load_constructor_symbols(
) -> dict[str, list[str]]:
    with CONSTRUCTOR_SYMBOLS_PATH.open(
        encoding="utf-8"
    ) as file:
        raw_data = json.load(
            file
        )

    if not isinstance(
        raw_data,
        dict,
    ):
        raise ValueError(
            "Constructor symbols data is invalid."
        )

    categories: dict[
        str,
        list[str],
    ] = {}

    for category, raw_symbols in (
        raw_data.items()
    ):
        if not isinstance(
            category,
            str,
        ):
            raise ValueError(
                "Constructor category is invalid."
            )

        if not isinstance(
            raw_symbols,
            list,
        ):
            raise ValueError(
                (
                    "Constructor category "
                    f'"{category}" is invalid.'
                )
            )

        symbols: list[str] = []

        for symbol in raw_symbols:
            if (
                not isinstance(
                    symbol,
                    str,
                )
                or not symbol
            ):
                raise ValueError(
                    (
                        "Invalid constructor symbol "
                        f'in category "{category}".'
                    )
                )

            if symbol not in symbols:
                symbols.append(
                    symbol
                )

        categories[
            category
        ] = symbols

    return categories