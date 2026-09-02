# spyc is a terminal viewer for browsing code bases.
# Copyright © 2026 Adam Waldenberg, Adeptum AB, Org.nr 559494-1824.
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
# or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for
# more details.
#
# You should have received a copy of the GNU General Public License along
# with this program. If not, see <https://www.gnu.org/licenses/>.
#
# Website: https://www.adeptum.se
# Contact: info@adeptum.se


import json
import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)
MAX_RECENT = 30


def default_state_path() -> Path:
    base = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(base) / "spyc" / "state.json"


# Saved state is a convenience, so a broken or unwritable file costs the
# remembered values and nothing else.
class StateStore:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path or default_state_path()
        self._data = self._read()

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def set(self, key: str, value) -> None:
        self._data[key] = value
        self._write()

    def recent_files(self, root: Path) -> list[str]:
        return list(self._data.get("recent", {}).get(str(root), []))

    def add_recent_file(self, root: Path, path: str) -> None:
        recent = self._data.setdefault("recent", {})
        files = [path, *(name for name in recent.get(str(root), []) if name != path)]
        recent[str(root)] = files[:MAX_RECENT]
        self._write()

    def _read(self) -> dict:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def _write(self) -> None:
        temporary = self._path.with_suffix(".tmp")
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            temporary.write_text(json.dumps(self._data), encoding="utf-8")
            os.replace(temporary, self._path)
        except OSError as error:
            log.warning("Could not save state to %s: %s", self._path, error)


def configure_logging(path: Path | None = None) -> logging.Handler | None:
    path = path or default_state_path().with_name("spyc.log")
    root = logging.getLogger()
    for handler in root.handlers:
        if getattr(handler, "baseFilename", None) == str(path.absolute()):
            return handler
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(path, encoding="utf-8")
    except OSError:
        return None
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    handler.setLevel(logging.WARNING)
    root.addHandler(handler)
    root.setLevel(min(root.level or logging.WARNING, logging.WARNING))
    return handler
