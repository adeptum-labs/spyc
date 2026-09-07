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


from pathlib import PurePosixPath

# From most to least significant: a directory shows the state of its child
# that matters most.
SIGNIFICANCE = "UMDAR?"


def _code(kind: str, states: str) -> str:
    if kind == "u":
        return "U"
    if kind == "2":
        return "R"
    if "D" in states:
        return "D"
    if states[0] == "A":
        return "A"
    return "M"


def parse_status(output: str) -> dict[str, str]:
    status: dict[str, str] = {}
    fields = iter(output.split("\0"))
    for entry in fields:
        kind = entry[:1]
        if kind == "?":
            status[entry[2:]] = "?"
        elif kind in ("1", "2", "u"):
            parts = entry.split(" ", {"1": 8, "2": 9, "u": 10}[kind])
            status[parts[-1]] = _code(kind, parts[1])
            if kind == "2":
                next(fields, None)
    return status


def rollup(status: dict[str, str]) -> dict[str, str]:
    directories: dict[str, str] = {}
    for path, code in status.items():
        for parent in PurePosixPath(path).parents:
            name = parent.as_posix()
            if name == "." or (name in directories and SIGNIFICANCE.index(directories[name]) <= SIGNIFICANCE.index(code)):
                continue
            directories[name] = code
    return directories
