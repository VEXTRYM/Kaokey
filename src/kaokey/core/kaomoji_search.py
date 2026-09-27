from kaokey.core.models import Kaomoji


def matches_kaomoji_search(
    kaomoji: Kaomoji,
    query: str,
) -> bool:
    normalized_query = query.strip().lower()

    tags = kaomoji.get(
        "tags",
        [],
    )

    searchable_text = " ".join(
        [
            kaomoji.get(
                "name",
                "",
            ),
            kaomoji["text"],
            *tags,
        ]
    ).lower()

    return normalized_query in searchable_text
