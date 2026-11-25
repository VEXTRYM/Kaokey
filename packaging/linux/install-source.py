#!/usr/bin/env python3
"""Install this checkout's desktop launcher using its virtual environment."""

import os
from pathlib import Path
import subprocess
import sys


APPLICATION_ID = "io.github.VEXTRYM.Kaokey"


def quote_exec_token(value: str) -> str:
    # Exec quoting is processed after Desktop Entry string unescaping.
    value = value.replace("%", "%%")
    for character in ('\\', '"', '`', '$'):
        value = value.replace(character, '\\' + character)
    return '"' + value.replace('\\', '\\\\') + '"'


def install() -> Path:
    root = Path(__file__).resolve().parents[2]
    interpreter = root / ".venv/bin/python"
    if not interpreter.is_file():
        raise SystemExit("Create .venv and run .venv/bin/pip install -e . first.")
    subprocess.run(
        [str(interpreter), "-c", "import kaokey.main"], check=True,
    )
    data_home = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share")
    destination = data_home / "applications" / f"{APPLICATION_ID}.desktop"
    destination.parent.mkdir(parents=True, exist_ok=True)
    template = (root / "packaging/linux" / f"{APPLICATION_ID}.desktop").read_text()
    command = f"{quote_exec_token(str(interpreter))} -m kaokey.main"
    destination.write_text(template.replace("Exec=kaokey\n", f"Exec={command}\n"))
    return destination


if __name__ == "__main__":
    if sys.platform != "linux":
        raise SystemExit("This installer is for Linux desktops.")
    print(f"Installed {install()}")
