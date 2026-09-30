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


import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

MAX_INDEXED_FILES = 200_000
SKIPPED_DIRECTORIES = frozenset({
    ".git", ".hg", ".svn", "node_modules", "target", "build", "dist", "out", "__pycache__",
    ".venv", "venv", ".tox", ".mypy_cache", ".pytest_cache", ".gradle", ".idea", ".next",
})
GIT_METADATA = frozenset({".git"})


@dataclass(frozen=True)
class FileIndex:
    root: Path
    paths: tuple[str, ...]
    truncated: bool


def build_index(root: Path, show_ignored: bool = False, limit: int = MAX_INDEXED_FILES) -> FileIndex:
    paths = None if show_ignored else _git_files(root)
    if paths is None:
        paths = _walk_files(root, limit + 1, GIT_METADATA if show_ignored else SKIPPED_DIRECTORIES)
    return FileIndex(root, tuple(sorted(paths[:limit])), truncated=len(paths) > limit)


def _git_lines(root: Path, *arguments: str) -> list[str] | None:
    try:
        result = subprocess.run(["git", "-C", str(root), *arguments], capture_output=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return None
    return [path for path in result.stdout.decode("utf-8", errors="replace").split("\0") if path]


GITLINK = "160000"
SYMLINK = "120000"


# `--cached` still lists files deleted from the working tree, and lists a
# conflicted file once per stage, so both are filtered out here. Submodules,
# nested repositories and links to directories are directories, not files.
def _git_files(root: Path) -> list[str] | None:
    listed = _git_lines(root, "ls-files", "-z", "--cached", "--others", "--exclude-standard")
    deleted = _git_lines(root, "ls-files", "-z", "--deleted")
    staged = _git_lines(root, "ls-files", "-z", "--stage")
    if listed is None or deleted is None or staged is None:
        return None
    gone = set(deleted)
    gone.update(path for path, mode in (_stage_entry(entry) for entry in staged) if _is_directory(root, path, mode))
    return [path for path in dict.fromkeys(listed) if path not in gone and not path.endswith("/")]


def _stage_entry(entry: str) -> tuple[str, str]:
    meta, _, path = entry.partition("\t")
    return path, meta.split(" ", 1)[0]


def _is_directory(root: Path, path: str, mode: str) -> bool:
    return mode == GITLINK or (mode == SYMLINK and (root / path).is_dir())


# Directory symlinks are never entered, so a link back to an ancestor cannot loop.
def _walk_files(root: Path, limit: int, skipped: frozenset[str]) -> list[str]:
    found: list[str] = []
    for directory, subdirectories, files in os.walk(root):
        subdirectories[:] = [name for name in subdirectories
                             if name not in skipped and not os.path.islink(os.path.join(directory, name))]
        relative = Path(directory).relative_to(root)
        found.extend((relative / name).as_posix() for name in files)
        if len(found) >= limit:
            break
    return found
