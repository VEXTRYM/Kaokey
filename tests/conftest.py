import os

import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    existing = QApplication.instance()
    if isinstance(existing, QApplication):
        return existing
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    return QApplication([])
