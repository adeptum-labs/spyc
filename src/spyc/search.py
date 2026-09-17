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
import re
import shutil
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from spyc.file_index import SKIPPED_DIRECTORIES

MAX_HITS = 2000
MAX_LINE = 500
MAX_FILE_BYTES = 2 * 1024 * 1024
BINARY_PROBE = 8192


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
# installed; without it the files of the project index are read here.
def search_text(root: Path, paths: Sequence[str], query: str, *, regex: bool = False, whole_word: bool = False,
                limit: int = MAX_HITS, ripgrep: bool | None = None) -> SearchResult:
    if not query:
        return SearchResult()
    use_ripgrep = shutil.which("rg") is not None if ripgrep is None else ripgrep
    if use_ripgrep:
        return _ripgrep(root, query, regex, whole_word, limit)
    return _scan(root, paths, query, regex, whole_word, limit)


def _short(text: str) -> str:
    return text.rstrip("\r\n")[:MAX_LINE]


def _ripgrep(root: Path, query: str, regex: bool, whole_word: bool, limit: int) -> SearchResult:
    command = ["rg", "--json", "--no-messages", "--smart-case", "--sort", "path", "--hidden", "--glob", "!.git"]
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
        return SearchResult(error=str(error))
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
    if process.wait() == 2 and not result.hits and error:
        result.error = error.splitlines()[0]
    return result


def _hit_of(raw: bytes) -> Hit | None:
    try:
        event = json.loads(raw)
    except ValueError:
        return None
    if event.get("type") != "match":
        return None
    data = event["data"]
    path, lines = data["path"].get("text"), data["lines"].get("text")
    if path is None or lines is None or not data["submatches"]:
        return None
    column = len(lines.encode("utf-8")[:data["submatches"][0]["start"]].decode("utf-8", errors="ignore"))
    return Hit(path, data["line_number"], column, _short(lines))


def _scan(root: Path, paths: Sequence[str], query: str, regex: bool, whole_word: bool, limit: int) -> SearchResult:
    body = query if regex else re.escape(query)
    flags = 0 if any(char.isupper() for char in query) else re.IGNORECASE
    try:
        pattern = re.compile(rf"\b(?:{body})\b" if whole_word else body, flags)
    except re.error as error:
        return SearchResult(error=str(error))
    result = SearchResult()
    for path in sorted(paths):
        for number, line in _lines_of(root / path):
            if match := pattern.search(line):
                if len(result.hits) >= limit:
                    result.truncated = True
                    return result
                result.hits.append(Hit(path, number, match.start(), _short(line)))
    return result


def _lines_of(path: Path):
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            return
        data = path.read_bytes()
    except OSError:
        return
    if b"\0" in data[:BINARY_PROBE]:
        return
    yield from enumerate(data.decode("utf-8", errors="replace").split("\n"), 1)
