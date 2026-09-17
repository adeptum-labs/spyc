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


import logging
import os
import re
from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from spyc.coverage.cobertura import parse_cobertura
from spyc.coverage.gocover import parse_gocover
from spyc.coverage.jacoco import parse_jacoco
from spyc.coverage.lcov import parse_lcov
from spyc.coverage.model import Report, ReportError
from spyc.fileio import read_limited

log = logging.getLogger(__name__)
# A report is read whole and held as objects, several times its size in memory.
MAX_REPORT_BYTES = 32 * 1024 * 1024
MAX_DEPTH = 6
MAX_ENTRIES = 100_000
HEAD = 16 * 1024
XML_ROOT = re.compile(r"<(coverage|report)[\s>/]")
XML_PARSERS = {"coverage": parse_cobertura, "report": parse_jacoco}
REPORT_NAMES = frozenset({"lcov.info", "coverage.xml", "cobertura.xml", "cobertura-coverage.xml", "coverage.out",
                          "cover.out", "coverage.lcov", "coverage.txt", "cover.profile", "coverage.profile"})
REPORT_SUFFIXES = (".lcov", ".coverprofile", ".gocover", ".cobertura.xml")
# Where reports usually are, looked into before their siblings when the search has to give up early.
REPORT_DIRECTORIES = frozenset({"coverage", "reports", "report", "site", "jacoco", "cobertura", "lcov", "test-results"})
# Build output, where reports usually are, is searched; the trees of tools and dependencies are not.
NOT_SEARCHED = frozenset({".git", ".hg", ".svn", "node_modules", "__pycache__", ".venv", "venv", ".tox",
                          ".mypy_cache", ".pytest_cache", ".idea", ".next"})


# What a file is follows from its content: a report has no reliable name.
def parse_report(text: str) -> Report:
    head = text[:HEAD].lstrip("﻿ \t\r\n")
    if head.startswith("mode:"):
        return parse_gocover(text)
    if head.startswith(("TN:", "SF:")):
        return parse_lcov(text)
    root = XML_ROOT.search(head) if head.startswith("<") else None
    if root is None:
        raise ReportError("Not a coverage report")
    return XML_PARSERS[root[1]](text)


def load_report(path: Path) -> Report:
    data = read_limited(path, MAX_REPORT_BYTES)
    if data is None:
        raise ReportError(f"missing, not a regular file or over {MAX_REPORT_BYTES // 2**20} MB")
    return parse_report(data.decode("utf-8", errors="replace"))


@dataclass(frozen=True)
class LoadedReport:
    path: Path
    mtime: float
    report: Report


# The reports that could be read, and for each of the others what was wrong with it.
def load_reports(paths: Sequence[Path]) -> tuple[list[LoadedReport], list[str]]:
    loaded, errors = [], []
    for path in paths:
        try:
            loaded.append(LoadedReport(path, path.stat().st_mtime, load_report(path)))
        except (ReportError, OSError) as error:
            errors.append(f"{path.name}: {error}")
        except Exception as error:  # a parser that breaks must not hide the reports that are fine
            log.exception("Coverage report %s could not be read", path)
            errors.append(f"{path.name}: {error}")
    return loaded, errors


def _named_like_a_report(name: str) -> bool:
    name = name.lower()
    return (name in REPORT_NAMES or name.endswith(REPORT_SUFFIXES) or (name.startswith("lcov") and name.endswith(".info"))
            or (name.startswith("jacoco") and name.endswith(".xml")))


# The reports a project usually has, shallowest first. The walk goes by depth,
# is bounded in depth and in entries counted as they are listed, and does not
# follow links, so a huge tree, or one huge directory, costs little.
def find_reports(root: Path) -> list[Path]:
    found: list[Path] = []
    pending, seen = deque([(root, 0)]), 0
    while pending and seen < MAX_ENTRIES:
        directory, depth = pending.popleft()
        subdirectories: list[Path] = []
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    seen += 1
                    if seen > MAX_ENTRIES:
                        break
                    _sort_out(entry, depth, found, subdirectories)
        except OSError:
            continue
        pending.extend((path, depth + 1) for path in sorted(subdirectories, key=_by_likelihood))
    return sorted(found, key=lambda path: (len(path.relative_to(root).parts), path.relative_to(root).as_posix()))


def _by_likelihood(path: Path) -> tuple[bool, str]:
    return path.name not in REPORT_DIRECTORIES, path.name


def _sort_out(entry: os.DirEntry, depth: int, found: list[Path], subdirectories: list[Path]) -> None:
    try:
        if entry.is_dir(follow_symlinks=False):
            if depth < MAX_DEPTH and entry.name not in NOT_SEARCHED:
                subdirectories.append(Path(entry.path))
        elif _named_like_a_report(entry.name) and entry.is_file():
            found.append(Path(entry.path))
    except OSError:
        return
