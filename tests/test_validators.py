from kaokey.core.validators import parse_tags

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

def test_parse_tags_deletes_empty_add_normal():
    assert parse_tags("dog,   , cat,, bird,, penis,,,") == ["dog", "cat", "bird", "penis"]

def test_parse_tags_works_multiple_values():
    assert parse_tags("dog, cat, bird") == ["dog", "cat", "bird"]

def test_parse_tags_preserve_register():
    assert parse_tags("DOG, dog, DoG") == ["DOG", "dog", "DoG"]