from constants import (
    MAX_KAOMOJI_LENGTH,
    MAX_TAG_LENGTH,
    MAX_TAGS,
)


def parse_tags(
    text: str,
) -> list[str]:
    tags = [
        clean_tag
        for tag in text.split(",")
        if (clean_tag := tag.strip())
    ]

    return list(
        dict.fromkeys(
            tags
        )
    )


def validate_kaomoji_content(
    text: str,
    tags: list[str],
) -> str | None:
    if not text:
        return (
            "Kaomoji cannot be empty."
        )

    if (
        len(text)
        > MAX_KAOMOJI_LENGTH
    ):
        return (
            "Kaomoji cannot be longer "
            f"than {MAX_KAOMOJI_LENGTH} "
            "characters."
        )

    if len(tags) > MAX_TAGS:
        return (
            "Maximum number of tags "
            f"is {MAX_TAGS}."
        )

    for tag in tags:
        if (
            len(tag)
            > MAX_TAG_LENGTH
        ):
            return (
                f'Tag "{tag}" is too long. '
                "Maximum length is "
                f"{MAX_TAG_LENGTH}."
            )

    return None


def validate_name(
    name: str,
    existing_names: set[str],
) -> str | None:
    if not name:
        return None

    if (
        name.casefold()
        in existing_names
    ):
        return (
            f'Name "{name}" already exists.'
        )

    return None