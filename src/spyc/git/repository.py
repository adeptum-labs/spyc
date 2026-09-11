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
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from spyc.git.blame import BlameLine, parse_blame
from spyc.git.changes import LineChanges, parse_hunks
from spyc.git.diff import Diff, diff_of_new_file, parse_diff
from spyc.git.log import LOG_FORMAT, Commit, parse_log
from spyc.git.status import parse_status

TIMEOUT_SECONDS = 30.0
UNTRACKED_FILE_LIMIT = 1024 * 1024


@dataclass(frozen=True)
class CommitDetail:
    message: str
    diff: Diff


# Every method runs the git command line and gives None when git is missing,
# the directory is not a repository or the command fails, so a caller has one
# way to say "no git here" instead of a family of exceptions. The calls block,
# so the application makes them from worker threads.
class Git:
    def __init__(self, root: Path) -> None:
        self.root = root

    def run(self, *arguments: str) -> str | None:
        # Optional locks stay off so that polling never fights the user's own
        # git commands for index.lock.
        environment = {**os.environ, "GIT_OPTIONAL_LOCKS": "0"}
        command = ["git", "--no-pager", "-C", str(self.root), "-c", "color.ui=never", "-c", "core.quotepath=false",
                   *arguments]
        try:
            result = subprocess.run(command, capture_output=True, env=environment, timeout=TIMEOUT_SECONDS)
        except (OSError, subprocess.TimeoutExpired):
            return None
        return result.stdout.decode("utf-8", errors="replace") if result.returncode == 0 else None

    def status(self) -> dict[str, str] | None:
        output = self.run("status", "--porcelain=v2", "-z", "--untracked-files=all")
        return None if output is None else parse_status(output)

    def log(self, limit: int = 200, skip: int = 0, path: str | None = None, grep: str | None = None
            ) -> list[Commit] | None:
        arguments = ["log", "-z", f"--format={LOG_FORMAT}", f"--max-count={limit}", f"--skip={skip}"]
        if grep:
            arguments += ["-i", "--fixed-strings", f"--grep={grep}"]
        if path:
            arguments += ["--follow", "--", path]
        output = self.run(*arguments)
        return None if output is None else parse_log(output)

    def blame(self, path: str) -> list[BlameLine] | None:
        output = self.run("blame", "--porcelain", "--", path)
        return None if output is None else parse_blame(output)

    def commit_detail(self, commit: str) -> CommitDetail | None:
        message = self.run("show", "-s", "--format=%B", commit)
        patch = self.run("show", "--format=", "--patch", "-M", "--diff-merges=first-parent", commit)
        return None if message is None or patch is None else CommitDetail(message.rstrip("\n"), parse_diff(patch))

    # Untracked files are not part of any git diff, so the caller names them
    # and they are shown as wholly added.
    def working_diff(self, untracked: Sequence[str]) -> Diff | None:
        options = ("diff", "--no-ext-diff", "-M")
        output = self.run(*options, "HEAD")
        if output is None:
            output = self.run(*options, "--cached")
        if output is None:
            return None
        diff = parse_diff(output)
        for path in untracked:
            try:
                with (self.root / path).open("rb") as handle:
                    diff.files.append(diff_of_new_file(path, handle.read(UNTRACKED_FILE_LIMIT)))
            except OSError:
                continue
        return diff

    # Before the first commit there is no HEAD to compare with, and the staged
    # lines are compared with nothing instead.
    def line_changes(self, path: str) -> LineChanges | None:
        options = ("diff", "-U0", "--no-ext-diff")
        output = self.run(*options, "HEAD", "--", path)
        if output is None:
            output = self.run(*options, "--cached", "--", path)
        return None if output is None else parse_hunks(output)
