from PySide6.QtWidgets import (
    QDialog, QFormLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QVBoxLayout,
)

from kaokey.application.web_api import WebApi


class WebConnectionDialog(QDialog):
    def __init__(self, api: WebApi, parent=None) -> None:
        super().__init__(parent)
        self.api = api
        self.setWindowTitle(self.tr("Website connection"))
        self.setMinimumWidth(540)
        layout = QVBoxLayout(self)
        description = QLabel(self.tr(
            "Connect a website to import and export lists on this device.\n"
            "Enter its address, then copy the connection details to that website.\n"
            "Only connect a website you trust with your lists."
        ))
        description.setWordWrap(True)
        layout.addWidget(description)
        form = QFormLayout()
        self.origin = QLineEdit(api.origin)
        self.origin.setPlaceholderText("https://example.com")
        form.addRow(self.tr("Website address"), self.origin)
        self.address = QLineEdit()
        self.address.setReadOnly(True)
        form.addRow(self.tr("Connection address"), self.address)
        self.token = QLineEdit()
        self.token.setReadOnly(True)
        form.addRow(self.tr("Connection token"), self.token)
        layout.addLayout(form)
        self.status = QLabel()
        layout.addWidget(self.status)
        self.toggle = QPushButton()
        self.toggle.clicked.connect(self.toggle_connection)
        layout.addWidget(self.toggle)
        close = QPushButton(self.tr("Close"))
        close.clicked.connect(self.close)
        layout.addWidget(close)
        self.refresh()

    def refresh(self) -> None:
        running = self.api.running
        self.origin.setEnabled(not running)
        self.address.setText(self.api.base_url if running else "")
        self.token.setText(self.api.token)
        self.toggle.setText(self.tr("Disconnect") if running else self.tr("Connect"))
        self.status.setText(self.tr(
            "Connected until you disconnect or quit Kaokey.\n"
            "The website may ask for permission to access this device."
        ) if running else self.tr("Disconnected. Each connection creates a new token."))

    def toggle_connection(self) -> None:
        if self.api.running:
            self.api.stop()
        else:
            try:
                self.api.start(self.origin.text())
                self.origin.setText(self.api.origin)
            except ValueError as error:
                QMessageBox.warning(self, self.tr("Connection failed"), str(error))
        self.refresh()
