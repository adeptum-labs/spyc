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


import hashlib
import json
import logging
import os
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from spyc.languages import Language, detect_language
from spyc.symbols import Symbol, symbols_of

log = logging.getLogger(__name__)
MAX_SYMBOL_FILE = 1024 * 1024
BINARY_PROBE = 8192
CACHE_VERSION = 1


@dataclass(frozen=True)
class Located:
    path: str
    symbol: Symbol


def default_cache_path(root: Path) -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "spyc" / f"symbols-{hashlib.sha1(str(root).encode()).hexdigest()[:12]}.json"


def _is_heading(symbol: Symbol) -> bool:
    return len(symbol.kind) == 2 and symbol.kind[0] == "h" and symbol.kind[1].isdigit()


def _indexable(path: str) -> Language | None:
    language = detect_language(path)
    return language if language is not None and (language.tags or language.id == "markdown") else None


# The definitions of every file of the project. It is filled from a worker
# thread while the interface reads it, and remembers each file by its size and
# modification time, on disk too, so that only files that changed are parsed
# again the next time.
class SymbolIndex:
    def __init__(self, root: Path, cache_path: Path | None = None) -> None:
        self._root, self._cache_path = root, cache_path
        self._lock = threading.Lock()
        self._files: dict[str, list[Symbol]] = {}
        self._stamps: dict[str, list[int]] = {}
        self.done = self.total = 0
        self._load_cache()

    def update(self, paths: Sequence[str], stop: Callable[[], bool] = lambda: False) -> None:
        candidates = [(path, language) for path in paths if (language := _indexable(path)) is not None]
        with self._lock:
            wanted = {path for path, _ in candidates}
            self._files = {path: symbols for path, symbols in self._files.items() if path in wanted}
            self._stamps = {path: stamp for path, stamp in self._stamps.items() if path in wanted}
            self.done, self.total = 0, len(candidates)
        for path, language in candidates:
            if stop():
                return
            self._refresh(path, language)
            with self._lock:
                self.done += 1
        self._save_cache()

    def all(self) -> list[Located]:
        with self._lock:
            files = list(self._files.items())
        return [Located(path, symbol) for path, symbols in files for symbol in symbols]

    def lookup(self, name: str) -> list[Located]:
        return [item for item in self.all() if item.symbol.name == name and not _is_heading(item.symbol)]

    def in_file(self, path: str) -> list[Symbol]:
        with self._lock:
            return list(self._files.get(path, []))

    def _refresh(self, path: str, language: Language) -> None:
        try:
            status = (self._root / path).stat()
        except OSError:
            return
        stamp = [status.st_mtime_ns, status.st_size]
        with self._lock:
            if self._stamps.get(path) == stamp and path in self._files:
                return
        symbols = self._read(self._root / path, status.st_size, language)
        with self._lock:
            self._files[path], self._stamps[path] = symbols, stamp

    @staticmethod
    def _read(file: Path, size: int, language: Language) -> list[Symbol]:
        if size > MAX_SYMBOL_FILE:
            return []
        try:
            data = file.read_bytes()
        except OSError:
            return []
        if b"\0" in data[:BINARY_PROBE]:
            return []
        return symbols_of(data.decode("utf-8", errors="replace"), language)

    def _load_cache(self) -> None:
        if self._cache_path is None:
            return
        try:
            cached = json.loads(self._cache_path.read_text(encoding="utf-8"))
            if cached["version"] != CACHE_VERSION:
                return
            for path, entry in cached["files"].items():
                self._files[path] = [Symbol(*fields) for fields in entry["symbols"]]
                self._stamps[path] = list(entry["stamp"])
        except (OSError, ValueError, KeyError, TypeError):
            self._files, self._stamps = {}, {}

    def _save_cache(self) -> None:
        if self._cache_path is None:
            return
        with self._lock:
            files = {path: {"stamp": self._stamps[path],
                            "symbols": [[s.name, s.kind, s.line, s.column] for s in symbols]}
                     for path, symbols in self._files.items() if path in self._stamps}
        temporary = self._cache_path.with_suffix(".tmp")
        try:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            temporary.write_text(json.dumps({"version": CACHE_VERSION, "files": files}), encoding="utf-8")
            os.replace(temporary, self._cache_path)
        except OSError as error:
            log.warning("Could not save the symbol index to %s: %s", self._cache_path, error)
