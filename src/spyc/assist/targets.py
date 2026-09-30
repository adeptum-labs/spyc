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
from dataclasses import dataclass
from pathlib import Path

from spyc.core.printable import printable

MAX_LISTED_PATHS = 200
MAX_WHOLE_FILE = 1024 * 1024
UNIT_QUESTION = "what it is for, its main files, its key types, its entry points and how it relates to the rest of the project"
QUESTIONS = {
    "directory": UNIT_QUESTION,
    "package": UNIT_QUESTION,
    "file": "what it is for, its main definitions and what in the project uses it",
    "class": "its responsibility, its main methods and its collaborators",
}
RULES = ("Answer in Markdown with short sections. Cite code as `path:line`. "
         "Do not change anything, and do not suggest changes.")


# `kind` is directory, package, file or class. `paths` are the files of it, relative to the project root.
@dataclass(frozen=True)
class Target:
    kind: str
    key: str
    label: str
    paths: tuple[str, ...]
    line: int | None = None

    @property
    def identity(self) -> str:
        return f"{self.kind}:{self.key}"


# What spyc already knows from its symbols and its dependency graph, as short texts.
@dataclass(frozen=True)
class Facts:
    depends_on: tuple[str, ...] = ()
    used_by: tuple[str, ...] = ()
    external: tuple[str, ...] = ()
    cycles: tuple[str, ...] = ()
    definitions: tuple[str, ...] = ()


def prompt_of(target: Target, facts: Facts) -> str:
    label = printable(target.label)
    subject = f"{target.kind} `{label}`"
    if target.line is not None:
        subject += f", defined at `{printable(target.paths[0])}:{target.line}`"
    parts = [f"Describe the {subject} of the project in the current directory for a developer who has not seen it before. "
             f"Cover {QUESTIONS[target.kind]}. {RULES}"]
    if target.kind in ("directory", "package"):
        parts.append(_file_list(target.paths))
    if known := _facts_lines(facts):
        parts.append("What spyc's analysis found, which may be incomplete:\n" + "\n".join(known))
    return "\n\n".join(parts)


def _file_list(paths: tuple[str, ...]) -> str:
    listed = [f"- {printable(path)}" for path in paths[:MAX_LISTED_PATHS]]
    if len(paths) > MAX_LISTED_PATHS:
        listed.append(f"- … and {len(paths) - MAX_LISTED_PATHS} more")
    return "Its files:\n" + "\n".join(listed)


def _facts_lines(facts: Facts) -> list[str]:
    rows = [("Depends on", facts.depends_on), ("Used by", facts.used_by), ("Outside the project", facts.external),
            ("In a cycle with", facts.cycles), ("Defines", facts.definitions)]
    return [f"{name}: {', '.join(printable(item) for item in items)}" for name, items in rows if items]


# A file that is too big to read counts by its size, and one that cannot be read by its absence.
def content_hash(target: Target, root: Path) -> str:
    digest = hashlib.sha1()
    for path in sorted(target.paths):
        digest.update(f"{path}\0{_fingerprint(root / path)}\0".encode("utf-8", errors="replace"))
    return digest.hexdigest()


def _fingerprint(path: Path) -> str:
    try:
        size = path.stat().st_size
        if size > MAX_WHOLE_FILE:
            return f"size {size}"
        return hashlib.sha1(path.read_bytes()).hexdigest()
    except OSError:
        return "absent"
