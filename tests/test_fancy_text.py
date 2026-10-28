import unicodedata

from kaokey.core.fancy_text import generate_fancy_text


def test_fancy_text_produces_many_distinct_copyable_styles() -> None:
    original = "Ab 9!?"
    variants = generate_fancy_text(original)
    by_name = {variant.name: variant.text for variant in variants}

    assert len(variants) >= 20
    assert len(by_name) == len(variants)
    assert len({variant.text for variant in variants}) == len(variants)
    assert original not in by_name.values()
    assert by_name["Bold"] == "𝐀𝐛 𝟗!?"
    assert by_name["Circled"] == "Ⓐⓑ ⑨!?"
    assert by_name["Fullwidth"] == "Ａｂ　９！？"
    assert by_name["Sparkles"] == "✨ Ab 9!? ✨"


def test_mathematical_styles_use_valid_unicode_letters_and_preserve_other_scripts() -> None:
    original = "Bhe Привет ☺"
    variants = generate_fancy_text(original)
    by_name = {variant.name: variant.text for variant in variants}

    assert by_name["Script"][0] == "ℬ"
    assert by_name["Script"][2] == "ℯ"
    assert by_name["Italic"][1] == "ℎ"
    for name in (
        "Bold", "Italic", "Bold italic", "Script", "Bold script",
        "Fraktur", "Bold fraktur", "Double-struck", "Sans serif",
        "Sans bold", "Sans italic", "Sans bold italic", "Monospace",
    ):
        styled = by_name[name]
        assert unicodedata.normalize("NFKC", styled) == original
        assert styled.endswith(" Привет ☺")


def test_fancy_text_skips_blank_input_and_deduplicates_unmapped_input() -> None:
    assert generate_fancy_text(" \n\t ") == []
    variants = generate_fancy_text("Привет")
    assert variants
    assert all(variant.text != "Привет" for variant in variants)
    assert len({variant.text for variant in variants}) == len(variants)
