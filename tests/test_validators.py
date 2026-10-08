from kaokey.core.validators import(
    parse_tags,
    validate_kaomoji_content,
    validate_name,
    )

from kaokey.config.constants import (
    MAX_KAOMOJI_LENGTH,
    MAX_TAGS,
    MAX_TAG_LENGTH,
)

# parse_tags

def test_parse_tags_works_one_value():
    assert parse_tags("dog") == ["dog"]

def test_parse_tags_ignores_empty():
    assert parse_tags("") == []

def test_parse_tags_ignores_spaces():
    assert parse_tags("   ") == []

def test_parse_tags_ignores_empty_commas():
    assert parse_tags(",,,") == []

def test_parse_tags_removes_duplicates():
    assert parse_tags("dog, dog, dog") == ["dog"]

def test_parse_tags_saves_order():
    assert parse_tags("dog, cat, cat, dog") == ["dog", "cat"]

def test_parse_tags_deletes_empty_adds_normal():
    assert parse_tags("dog,   , cat,, bird,, penis,,,") == ["dog", "cat", "bird", "penis"]

def test_parse_tags_works_multiple_values():
    assert parse_tags("dog, cat, bird") == ["dog", "cat", "bird"]

def test_parse_tags_preserve_register():
    assert parse_tags("DOG, dog, DoG") == ["DOG", "dog", "DoG"]

# validate_kaomoji_content

def test_validate_kaomoji_content_simple():
    text = "dog"
    tags = ["dog"]

    result = validate_kaomoji_content(text, tags)

    assert result == None

def test_validate_kaomoji_content_empty_text_returns_message():
    text = ""
    tags = ["dog"]

    result = validate_kaomoji_content(text, tags)

    assert result is not None

def test_validate_kaomoji_content_kaomoji_eq_max_kaomoji_length_accept():
    text = "a" * MAX_KAOMOJI_LENGTH
    tags = ["dog"]

    result = validate_kaomoji_content(text, tags)

    assert result is None

def test_validate_kaomoji_content_kaomoji_over_max_kaomoji_length_reject():
    text = "a" * (MAX_KAOMOJI_LENGTH + 1)
    tags = ["dog"]

    result = validate_kaomoji_content(text, tags)

    assert result is not None

def test_validate_kaomoji_content_tags_eq_max_tags_accept():
    text = "dog"
    tags = ["dog" * MAX_TAGS]

    result = validate_kaomoji_content(text, tags)

    assert result is None

def test_validate_kaomoji_content_tags_over_max_tags_reject():
    text = "dog"
    tags = ["dog" * (MAX_TAGS + 1)]

    result = validate_kaomoji_content(text, tags)

    assert result is not None

def test_validate_kaomoji_content_tag_length_eq_tag_length_accept():
    text = "dog"
    tags = ["a"]
    tags[0] = tags[0] * MAX_TAG_LENGTH

    result = validate_kaomoji_content(text, tags)

    assert result is None

def test_validate_kaomoji_content_tag_length_over_tag_length_reject():
    text = "dog"
    tags = ["a"]
    tags[0] = tags[0] * (MAX_TAG_LENGTH + 1)

    result = validate_kaomoji_content(text, tags)

    assert result is not None

#validate_name

def test_validate_name_accepts_unique():
    name = "dog"
    existing_names = set(["cat", "bird"])

    result = validate_name(name, existing_names)

    assert result is None

def test_validate_name_rejects_existing():
    name = "dog"
    existing_names = set(["cat", "dog"])

    result = validate_name(name,existing_names)

    assert result is not None

def test_validate_name_rejects_existing_ignore_register():
    name = "DoG"
    existing_names = set(["cat", "dog"])

    result = validate_name(name, existing_names)

    assert result is not None

def test_validate_name_rejects_existing_ignore_tag_register():
    name = "DOG"
    existing_names = set(["CAT", "DOG"])

    result = validate_name(name,existing_names)

    assert result is not None