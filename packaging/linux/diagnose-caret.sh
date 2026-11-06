#!/bin/sh
# Run from the checked-out source with its existing virtual environment.
set -eu
kaokey_root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
kaokey_target=${1:-diagnostics}
case "$kaokey_target" in
    diagnostics) kaokey_log="$kaokey_root/caret-diagnostics.log" ;;
    firefox|chrome|mousepad) kaokey_log="$kaokey_root/caret-$kaokey_target.log" ;;
    *) printf 'Usage: %s [firefox|chrome|mousepad]\n' "$0" >&2; exit 2 ;;
esac
printf 'Focus a text field in the target application within 8 seconds.\n'
"$kaokey_root/.venv/bin/python" -m kaokey.platforms.linux.diagnostics --delay 8 \
    > "$kaokey_log" 2>&1
printf 'Done. Diagnostic log: %s\n' "$kaokey_log"
