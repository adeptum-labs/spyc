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
import threading
from dataclasses import asdict, dataclass
from pathlib import Path

from spyc.core.cache_files import write_atomically

log = logging.getLogger(__name__)
CACHE_VERSION = 1
MAX_ANSWERS = 200


@dataclass(frozen=True)
class Cached:
    content_hash: str
    model: str
    when: float
    text: str


# The answers of Claude take time and quota, so they are kept per project. Another spyc may write the same file, so
# every call reads it again; a file that cannot be read or written just means no memory.
class AnswerCache:
    def __init__(self, path: Path | None) -> None:
        self._path = path
        self._lock = threading.Lock()

    def get(self, identity: str) -> Cached | None:
        return self._read().get(identity)

    def put(self, identity: str, answer: Cached) -> None:
        if self._path is None:
            return
        with self._lock:
            answers = self._read()
            answers[identity] = answer
            newest = sorted(answers.items(), key=lambda entry: entry[1].when)[-MAX_ANSWERS:]
            content = json.dumps({"version": CACHE_VERSION, "answers": {key: asdict(value) for key, value in newest}})
            try:
                write_atomically(self._path, content)
            except OSError as error:
                log.warning("Could not save the answers to %s: %s", self._path, error)

    def _read(self) -> dict[str, Cached]:
        if self._path is None:
            return {}
        try:
            stored = json.loads(self._path.read_text(encoding="utf-8"))
            if stored["version"] != CACHE_VERSION:
                return {}
            return {identity: _entry(entry) for identity, entry in stored["answers"].items()}
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            return {}


def _entry(entry: dict) -> Cached:
    answer = Cached(entry["content_hash"], entry["model"], entry["when"], entry["text"])
    if not (isinstance(answer.content_hash, str) and isinstance(answer.model, str) and isinstance(answer.text, str)
            and isinstance(answer.when, int | float)):
        raise TypeError("Answer of the wrong shape")
    return answer
