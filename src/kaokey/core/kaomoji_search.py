from kaokey.core.models import Kaomoji


def searchable_kaomoji_text(kaomoji: Kaomoji) -> str:
    """Return the normalized fields used by both kaomoji search views."""
    return " ".join(
        [kaomoji.get("name", ""), kaomoji["text"], *kaomoji.get("tags", [])]
    ).lower()


def matches_kaomoji_search(
    kaomoji: Kaomoji,
    query: str,
) -> bool:
    normalized_query = query.strip().lower()

    if not normalized_query:
        return True

    return normalized_query in searchable_kaomoji_text(kaomoji)
