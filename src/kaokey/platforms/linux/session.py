from typing import Literal

LinuxDisplayBackend = Literal[
    "x11",
    "wayland",
]


def display_backend_from_qt_platform(
    platform_name: str,
) -> LinuxDisplayBackend | None:
    """Map the active Qt QPA plugin to the Linux display backend."""
    normalized = platform_name.strip().casefold()

    if normalized == "xcb":
        return "x11"

    if normalized.startswith("wayland"):
        return "wayland"

    return None
