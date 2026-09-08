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
from pathlib import Path

from spyc.git.changes import LineChanges, parse_hunks
from spyc.git.status import parse_status

TIMEOUT_SECONDS = 30.0


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
        command = ["git", "--no-pager", "-C", str(self.root), "-c", "color.ui=never", *arguments]
        try:
            result = subprocess.run(command, capture_output=True, env=environment, timeout=TIMEOUT_SECONDS)
        except (OSError, subprocess.TimeoutExpired):
            return None
        return result.stdout.decode("utf-8", errors="replace") if result.returncode == 0 else None

    def status(self) -> dict[str, str] | None:
        output = self.run("status", "--porcelain=v2", "-z", "--untracked-files=all")
        return None if output is None else parse_status(output)

    # Before the first commit there is no HEAD to compare with, and the staged
    # lines are compared with nothing instead.
    def line_changes(self, path: str) -> LineChanges | None:
        options = ("diff", "-U0", "--no-ext-diff")
        output = self.run(*options, "HEAD", "--", path)
        if output is None:
            output = self.run(*options, "--cached", "--", path)
        return None if output is None else parse_hunks(output)
