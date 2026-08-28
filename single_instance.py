from PySide6.QtCore import (
    QObject,
    Signal,
)

from PySide6.QtNetwork import (
    QLocalServer,
    QLocalSocket,
)


LOCAL_CONNECTION_TIMEOUT_MS = 250


class SingleInstanceCoordinator(QObject):
    activation_requested = Signal()

    def __init__(
        self,
        server_name: str,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(
            parent
        )

        self.server_name = server_name

        self.server = QLocalServer(
            self
        )

        self.server.newConnection.connect(
            self.handle_new_connection
        )

    def claim_primary_instance(
        self,
    ) -> bool:
        """Return True only for the process that should keep running."""
        if self.notify_existing_instance():
            return False

        # If a previous process crashed, a stale local-server endpoint may
        # remain. Remove it only after we failed to connect to a live process.
        QLocalServer.removeServer(
            self.server_name
        )

        if self.server.listen(
            self.server_name
        ):
            return True

        # Another process may have won the race between our first connection
        # attempt and listen(). Try once more before giving up.
        if self.notify_existing_instance():
            return False

        raise RuntimeError(
            "Could not create Kaokey "
            "single-instance server."
        )

    def notify_existing_instance(
        self,
    ) -> bool:
        socket = QLocalSocket(
            self
        )

        socket.connectToServer(
            self.server_name
        )

        connected = socket.waitForConnected(
            LOCAL_CONNECTION_TIMEOUT_MS
        )

        if not connected:
            socket.abort()
            socket.deleteLater()
            return False

        # The connection itself is the activation request. No protocol is
        # necessary yet, which keeps this mechanism small and robust.
        socket.disconnectFromServer()
        socket.deleteLater()

        return True

    def handle_new_connection(
        self,
    ) -> None:
        while self.server.hasPendingConnections():
            socket = self.server.nextPendingConnection()

            if socket is None:
                continue

            socket.disconnectFromServer()
            socket.deleteLater()

            self.activation_requested.emit()
