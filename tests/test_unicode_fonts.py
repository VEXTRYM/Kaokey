from PySide6.QtGui import QFont, QFontMetrics
from PySide6.QtWidgets import QApplication, QPlainTextEdit

from kaokey.ui.styling import unicode_fonts
from kaokey.ui.styling.widget_styles import style_unicode_text


def test_bundled_noto_fonts_are_registered_and_preferred(qapp: QApplication) -> None:
    del qapp
    families, by_file = unicode_fonts.bundled_font_families()
    assert by_file["NotoSans-Regular.ttf"]
    assert by_file["NotoSansCanadianAboriginal-Regular.ttf"]
    assert by_file["NotoSansSymbols2-Regular.ttf"]
    assert by_file["NotoSansCJK-Regular.ttc"]
    assert families[0] in by_file["NotoSans-Regular.ttf"]

    font = unicode_fonts.font_with_unicode_fallbacks(QFont("Arial"))
    assert font.families()[0] in by_file["NotoSans-Regular.ttf"]
    assert font.families().index("Arial") > 0
    assert len(font.families()) < 20


def test_canadian_syllabic_uses_shipped_font(qapp: QApplication) -> None:
    del qapp
    _, by_file = unicode_fonts.bundled_font_families()
    font = unicode_fonts.font_for_text(QFont("Arial"), "ᗝ")
    assert font.family() in by_file["NotoSansCanadianAboriginal-Regular.ttf"]
    metrics = QFontMetrics(font)
    assert metrics.inFontUcs4(ord("ᗝ"))


def test_mixed_text_keeps_bundled_fonts_ahead_of_system(qapp: QApplication) -> None:
    del qapp
    _, by_file = unicode_fonts.bundled_font_families()
    font = unicode_fonts.font_with_unicode_fallbacks(
        QFont("Arial"), "NotoSansCanadianAboriginal-Regular.ttf"
    )
    assert font.families()[0] in by_file["NotoSansCanadianAboriginal-Regular.ttf"]
    assert font.families().index("Arial") > font.families().index(
        by_file["NotoSans-Regular.ttf"][0]
    )
    metrics = QFontMetrics(font)
    assert metrics.inFontUcs4(ord("ᗝ"))
    assert metrics.inFontUcs4(ord("中"))
    assert metrics.inFontUcs4(ord("😀"))


def test_uncommon_script_adds_only_its_bundled_family(qapp: QApplication) -> None:
    del qapp
    _, by_file = unicode_fonts.bundled_font_families()
    font = unicode_fonts.font_for_text(QFont("Arial"), "A𐤀")
    assert by_file["NotoSansPhoenician-Regular.ttf"][0] in font.families()
    assert font.families().index("Arial") > font.families().index(
        by_file["NotoSansPhoenician-Regular.ttf"][0]
    )
    assert len(font.families()) < 20


def test_editable_text_updates_to_bundled_script_font(qapp: QApplication) -> None:
    del qapp
    editor = QPlainTextEdit()
    style_unicode_text(editor)
    editor.setPlainText("ᗝ")
    _, by_file = unicode_fonts.bundled_font_families()
    assert editor.font().family() in by_file["NotoSansCanadianAboriginal-Regular.ttf"]
    editor.deleteLater()


def test_missing_bundled_fonts_fall_back_to_system(
    qapp: QApplication, monkeypatch
) -> None:
    del qapp
    monkeypatch.setattr(unicode_fonts, "bundled_font_families", lambda: ((), {}))
    font = unicode_fonts.font_for_text(QFont("Arial"), "ᗝ")
    assert font.families()[0] == "Arial"
    assert "Segoe UI Symbol" in font.families()
