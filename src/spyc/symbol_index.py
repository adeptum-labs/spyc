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


import functools
import hashlib
import importlib.metadata
import json
import logging
import os
import tempfile
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from spyc.analysis import Analysis, analyse
from spyc.deps.facts import FileFacts, facts_from_json, facts_to_json
from spyc.fileio import read_limited
from spyc.languages import Language, detect_language
from spyc.symbols import Symbol

log = logging.getLogger(__name__)
MAX_SYMBOL_FILE = 1024 * 1024
BINARY_PROBE = 8192
CACHE_VERSION = 3
SIGNED_DISTRIBUTIONS = ("spyc", "tree-sitter")


@dataclass(frozen=True)
class Located:
    path: str
    symbol: Symbol


def default_cache_path(root: Path) -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "spyc" / f"symbols-{hashlib.sha1(str(root).encode()).hexdigest()[:12]}.json"


# The definitions found depend on the tags queries and on the grammars that
# run them, so a cache made by other versions of them is not to be trusted.
@functools.cache
def _signature() -> str:
    versions = {}
    for distribution in importlib.metadata.distributions():
        name = distribution.metadata["Name"] or ""
        if name in SIGNED_DISTRIBUTIONS or name.startswith("tree-sitter-"):
            versions[name] = distribution.version
    return ", ".join(f"{name}={version}" for name, version in sorted(versions.items()))


def _is_heading(symbol: Symbol) -> bool:
    return len(symbol.kind) == 2 and symbol.kind[0] == "h" and symbol.kind[1].isdigit()


def _indexable(path: str) -> Language | None:
    language = detect_language(path)
    return language if language is not None and (language.tags or language.imports or language.id == "markdown") else None


# The definitions and the facts for the dependency graph of every file of the
# project, from one parse of each. It is filled from a worker thread while the
# interface reads it, and remembers each file by its size and modification
# time, on disk too, so that only files that changed are parsed again the next
# time. Nothing is read from disk until `update` runs.
class SymbolIndex:
    def __init__(self, root: Path, cache_path: Path | None = None) -> None:
        self._root, self._cache_path = root, cache_path
        self._lock = threading.Lock()
        self._files: dict[str, list[Symbol]] = {}
        self._facts: dict[str, FileFacts] = {}
        self._stamps: dict[str, list[int]] = {}
        self._flat: tuple[Located, ...] | None = None
        self._by_name: dict[str, list[Located]] = {}
        self._loaded = self._changed = False
        self.done = self.total = 0

    def update(self, paths: Sequence[str], stop: Callable[[], bool] = lambda: False) -> None:
        self._load_cache()
        candidates = [(path, language) for path in paths if (language := _indexable(path)) is not None]
        with self._lock:
            wanted = {path for path, _ in candidates}
            if not wanted.issuperset(self._files):
                self._files = {path: symbols for path, symbols in self._files.items() if path in wanted}
                self._facts = {path: facts for path, facts in self._facts.items() if path in wanted}
                self._stamps = {path: stamp for path, stamp in self._stamps.items() if path in wanted}
                self._changed, self._flat = True, None
            self.done, self.total = 0, len(candidates)
        for path, language in candidates:
            if stop():
                return
            self._refresh(path, language)
            with self._lock:
                self.done += 1
        self._save_cache()

    def all(self) -> tuple[Located, ...]:
        with self._lock:
            return self._flattened()

    def facts(self) -> dict[str, FileFacts]:
        with self._lock:
            return dict(self._facts)

    def lookup(self, name: str) -> list[Located]:
        with self._lock:
            self._flattened()
            return [item for item in self._by_name.get(name, []) if not _is_heading(item.symbol)]

    def _flattened(self) -> tuple[Located, ...]:
        if self._flat is None:
            self._flat = tuple(Located(path, symbol) for path, symbols in self._files.items() for symbol in symbols)
            self._by_name = {}
            for item in self._flat:
                self._by_name.setdefault(item.symbol.name, []).append(item)
        return self._flat

    def _refresh(self, path: str, language: Language) -> None:
        try:
            status = (self._root / path).stat()
        except OSError:
            return
        stamp = [status.st_mtime_ns, status.st_size]
        with self._lock:
            if self._stamps.get(path) == stamp and path in self._files:
                return
        analysis = self._read(self._root / path, language)
        with self._lock:
            self._files[path], self._stamps[path] = analysis.symbols, stamp
            if analysis.facts is not None:
                self._facts[path] = analysis.facts
            else:
                self._facts.pop(path, None)
            self._changed, self._flat = True, None

    @staticmethod
    def _read(file: Path, language: Language) -> Analysis:
        data = read_limited(file, MAX_SYMBOL_FILE)
        if data is None or b"\0" in data[:BINARY_PROBE]:
            return Analysis([], None)
        return analyse(data.decode("utf-8", errors="replace"), language)

    def _load_cache(self) -> None:
        if self._loaded or self._cache_path is None:
            return
        self._loaded = True
        try:
            cached = json.loads(self._cache_path.read_text(encoding="utf-8"))
            if cached["version"] != CACHE_VERSION or cached["signature"] != _signature():
                return
            files = {path: [Symbol(*fields) for fields in entry["symbols"]] for path, entry in cached["files"].items()}
            facts = {path: facts_from_json(entry["facts"]) for path, entry in cached["files"].items() if entry["facts"]}
            stamps = {path: list(entry["stamp"]) for path, entry in cached["files"].items()}
        except (OSError, ValueError, KeyError, TypeError):
            return
        with self._lock:
            self._files, self._facts, self._stamps, self._flat = files, facts, stamps, None

    def _save_cache(self) -> None:
        if self._cache_path is None:
            return
        with self._lock:
            if not self._changed:
                return
            files = {path: {"stamp": self._stamps[path],
                            "symbols": [[s.name, s.kind, s.line, s.column] for s in symbols],
                            "facts": facts_to_json(self._facts[path]) if path in self._facts else None}
                     for path, symbols in self._files.items() if path in self._stamps}
            self._changed = False
        try:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            self._write_atomically(json.dumps({"version": CACHE_VERSION, "signature": _signature(), "files": files}))
        except OSError as error:
            self._changed = True
            log.warning("Could not save the symbol index to %s: %s", self._cache_path, error)

    # Another spyc on the same project writes here too, so each write has a file of its own.
    def _write_atomically(self, content: str) -> None:
        handle, temporary = tempfile.mkstemp(dir=self._cache_path.parent, prefix=f"{self._cache_path.name}.", suffix=".tmp")
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                stream.write(content)
            os.replace(temporary, self._cache_path)
        except OSError:
            Path(temporary).unlink(missing_ok=True)
            raise
