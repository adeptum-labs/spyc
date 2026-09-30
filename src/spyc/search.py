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


import base64
import json
import os
import re
import shutil
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from spyc.core.cancellation import Cancellation
from spyc.core.file_index import SKIPPED_DIRECTORIES
from spyc.core.fileio import read_limited

MAX_HITS = 2000
MAX_LINE = 500
MAX_FILE_BYTES = 2 * 1024 * 1024
BINARY_PROBE = 8192
NEEDS_RIPGREP = "Pattern search needs ripgrep"


@dataclass(frozen=True)
class Hit:
    path: str
    line: int
    column: int
    text: str


@dataclass
class SearchResult:
    hits: list[Hit] = field(default_factory=list)
    truncated: bool = False
    error: str | None = None


# The query is literal and case is ignored unless it holds a capital letter,
# which is what ripgrep's smart case does too. ripgrep does the work when it is
# installed; without it the files of the project index are read here, and a
# pattern is refused because Python's re cannot be interrupted and one bad
# pattern would freeze the program.
def search_text(root: Path, paths: Sequence[str], query: str, *, regex: bool = False, whole_word: bool = False,
                limit: int = MAX_HITS, ripgrep: bool | None = None,
                cancellation: Cancellation | None = None) -> SearchResult:
    cancellation = cancellation or Cancellation()
    if not query or "\0" in query or cancellation.cancelled:
        return SearchResult()
    if shutil.which("rg") is not None if ripgrep is None else ripgrep:
        return _ripgrep(root, query, regex, whole_word, limit, cancellation)
    if regex:
        return SearchResult(error=NEEDS_RIPGREP)
    return _scan(root, paths, query, whole_word, limit, cancellation)


def _short(text: str) -> str:
    return text.rstrip("\r\n")[:MAX_LINE]


def _ripgrep(root: Path, query: str, regex: bool, whole_word: bool, limit: int,
             cancellation: Cancellation) -> SearchResult:
    command = ["rg", "--json", "--no-config", "--no-messages", "--smart-case", "--hidden", "--glob", "!.git"]
    if not regex:
        command.append("--fixed-strings")
    if whole_word:
        command.append("--word-regexp")
    if not (root / ".git").exists():
        command += [argument for name in sorted(SKIPPED_DIRECTORIES) for argument in ("--glob", f"!{name}")]
    command += ["-e", query]
    result = SearchResult()
    try:
        process = subprocess.Popen(command, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError as error:
        return SearchResult(error=f"Search failed: {error}")
    cancellation.on_cancel(process.kill)
    for raw in process.stdout:
        hit = _hit_of(raw)
        if hit is None:
            continue
        if len(result.hits) >= limit:
            result.truncated = True
            process.kill()
            break
        result.hits.append(hit)
    error = process.stderr.read().decode("utf-8", errors="replace").strip()
    process.stdout.close()
    process.stderr.close()
    status = process.wait()
    if cancellation.cancelled:
        return SearchResult()
    if status == 2 and not result.hits and error:
        result.error = f"{'Bad pattern' if regex else 'Search failed'}: {error.splitlines()[0]}"
    result.hits.sort(key=lambda hit: (hit.path, hit.line))
    return result


# ripgrep sends what is not valid UTF-8 as base64 "bytes" instead of "text".
def _raw(payload: dict) -> bytes:
    return base64.b64decode(payload["bytes"]) if "bytes" in payload else payload["text"].encode("utf-8")


def _hit_of(raw: bytes) -> Hit | None:
    try:
        event = json.loads(raw)
    except ValueError:
        return None
    if event.get("type") != "match":
        return None
    data = event["data"]
    if not data["submatches"]:
        return None
    lines = _raw(data["lines"])
    column = len(lines[:data["submatches"][0]["start"]].decode("utf-8", errors="replace"))
    return Hit(os.fsdecode(_raw(data["path"])), data["line_number"], column, _short(lines.decode("utf-8", errors="replace")))


def _scan(root: Path, paths: Sequence[str], query: str, whole_word: bool, limit: int,
          cancellation: Cancellation) -> SearchResult:
    body = re.escape(query)
    flags = 0 if any(char.isupper() for char in query) else re.IGNORECASE
    pattern = re.compile(rf"\b(?:{body})\b" if whole_word else body, flags)
    result = SearchResult()
    for path in sorted(paths):
        if cancellation.cancelled:
            return SearchResult()
        for number, line in _lines_of(root / path):
            if match := pattern.search(line):
                if len(result.hits) >= limit:
                    result.truncated = True
                    return result
                result.hits.append(Hit(path, number, match.start(), _short(line)))
    return result


def _lines_of(path: Path):
    data = read_limited(path, MAX_FILE_BYTES)
    if data is None or b"\0" in data[:BINARY_PROBE]:
        return
    yield from enumerate(data.decode("utf-8", errors="replace").split("\n"), 1)
