import pytest

from kaokey.config.constants import (
    MAX_KAOMOJI_LENGTH,
    MAX_TAG_LENGTH,
    MAX_TAGS,
)
from kaokey.core.validators import (
    parse_tags,
    validate_kaomoji_content,
    validate_name,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("", []),
        ("   , , ", []),
        ("dog", ["dog"]),
        (" dog, cat, dog, , bird ", ["dog", "cat", "bird"]),
        ("DOG, dog, DoG", ["DOG", "dog", "DoG"]),
    ],
)
def test_parse_tags_strips_blanks_and_preserves_order(
    raw: str, expected: list[str]
) -> None:
    assert parse_tags(raw) == expected


@pytest.mark.parametrize(
    ("text", "tags", "valid"),
    [
        ("(o_o)", [], True),
        ("", ["tag"], False),
        ("a" * MAX_KAOMOJI_LENGTH, [], True),
        ("a" * (MAX_KAOMOJI_LENGTH + 1), [], False),
        ("(o_o)", [f"tag{index}" for index in range(MAX_TAGS)], True),
        ("(o_o)", [f"tag{index}" for index in range(MAX_TAGS + 1)], False),
        ("(o_o)", ["a" * MAX_TAG_LENGTH], True),
        ("(o_o)", ["a" * (MAX_TAG_LENGTH + 1)], False),
    ],
)
def test_kaomoji_content_boundaries(
    text: str, tags: list[str], valid: bool
) -> None:
    assert (validate_kaomoji_content(text, tags) is None) is valid


def test_name_validation_allows_empty_and_rejects_case_insensitive_duplicate() -> None:
    existing = {"Cat", "Dog"}
    assert validate_name("", existing) is None
    assert validate_name("Bird", existing) is None
    assert validate_name("dOg", existing) is not None
