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
import re
import stat
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from spyc.git.blame import BlameLine, parse_blame
from spyc.git.branches import BRANCH_FORMAT, Branch, parse_branches
from spyc.git.changes import LineChanges, parse_hunks
from spyc.git.diff import DIFF_LINE_LIMIT, Diff, FileDiff, diff_of_new_file, parse_diff
from spyc.git.log import LOG_FORMAT, Commit, parse_log
from spyc.git.status import parse_status
from spyc.git.summary import GitSummary

TIMEOUT_SECONDS = 30.0
UNTRACKED_FILE_LIMIT = 1024 * 1024
# What the user's own git settings would change in the output that is parsed.
NEUTRAL_SETTINGS = ("color.ui=never", "color.diff=false", "core.quotepath=false", "diff.noprefix=false",
                    "diff.mnemonicPrefix=false", "diff.suppressBlankEmpty=false", "log.showSignature=false")
DIFF_OPTIONS = ("--no-ext-diff", "--no-textconv")
NO_LAZY_FETCH_VERSION = (2, 44)


# Optional locks stay off so that polling never fights the user's own git
# commands for index.lock. Reading a branch is offline: git neither asks for a
# password on the terminal nor fetches the blobs a partial clone left out, as
# that would write into the repository and can take very long.
def git_environment(offline: bool = False) -> dict[str, str]:
    environment = {**os.environ, "GIT_OPTIONAL_LOCKS": "0"}
    if offline:
        environment.update(GIT_TERMINAL_PROMPT="0", GIT_NO_LAZY_FETCH="1")
    return environment


# GIT_NO_LAZY_FETCH, which stops that, is only understood from git 2.44.
def fetches_missing_blobs(version_text: str, partial_clone: bool) -> bool:
    found = re.match(r"git version (\d+)\.(\d+)", version_text)
    return partial_clone and (found is None or (int(found[1]), int(found[2])) < NO_LAZY_FETCH_VERSION)


@dataclass(frozen=True)
class CommitDetail:
    message: str
    diff: Diff


# Every method runs the git command line and gives None when git is missing,
# the directory is not a repository or the command fails, so a caller has one
# way to say "no git here" instead of a family of exceptions. The calls block,
# so the application makes them from worker threads.
class Git:
    def __init__(self, root: Path, offline: bool = False) -> None:
        self.root, self.offline = root, offline

    def run(self, *arguments: str) -> str | None:
        # Paths are literal: a file named [id].tsx is not a pattern.
        environment = git_environment(self.offline)
        options = [part for setting in NEUTRAL_SETTINGS for part in ("-c", setting)]
        command = ["git", "--no-pager", "--literal-pathspecs", "-C", str(self.root), *options, *arguments]
        try:
            result = subprocess.run(command, capture_output=True, env=environment, timeout=TIMEOUT_SECONDS)
        except (OSError, subprocess.TimeoutExpired):
            return None
        return result.stdout.decode("utf-8", errors="replace") if result.returncode == 0 else None

    def status(self) -> dict[str, str] | None:
        output = self.run("status", "--porcelain=v2", "-z", "--untracked-files=all")
        return None if output is None else parse_status(output)

    def log(self, limit: int = 200, skip: int = 0, path: str | None = None, grep: str | None = None,
            revision: str | None = None) -> list[Commit] | None:
        arguments = ["log", "-z", f"--format={LOG_FORMAT}", f"--max-count={limit}", f"--skip={skip}"]
        if grep:
            arguments += ["-i", "--fixed-strings", f"--grep={grep}"]
        if revision:
            arguments.append(revision)
        if path:
            arguments += ["--follow", "--", path]
        output = self.run(*arguments)
        return None if output is None else parse_log(output)

    def fetches_missing_blobs(self) -> bool:
        partial = bool(self.run("config", "--get", "extensions.partialclone"))
        return fetches_missing_blobs(self.run("--version") or "", partial)

    def branch(self) -> str | None:
        name = self.run("symbolic-ref", "--short", "-q", "HEAD")
        if name is not None:
            return name.strip()
        detached = self.run("rev-parse", "--short", "HEAD")
        return None if detached is None else f"(detached {detached.strip()})"

    def summary(self, status: dict[str, str]) -> GitSummary:
        commits = self.log(limit=1)
        return GitSummary(self.branch(), len(status), commits[0] if commits else None)

    def blame(self, path: str, revision: str | None = None) -> list[BlameLine] | None:
        base, target = ["blame", "--porcelain"], [*([revision] if revision else []), "--", path]
        output = self.run(*base, *target)
        if output is None:
            # A global blame.ignoreRevsFile that names a file this repository
            # does not have makes blame fail outright.
            output = self.run(*base, "--no-ignore-revs-file", *target)
        return None if output is None else parse_blame(output)

    def branches(self) -> list[Branch] | None:
        output = self.run("for-each-ref", "--sort=-committerdate", f"--format={BRANCH_FORMAT}", "refs/heads",
                          "refs/remotes")
        return None if output is None else parse_branches(output)

    def origin_head(self) -> str | None:
        name = self.run("symbolic-ref", "-q", "--short", "refs/remotes/origin/HEAD")
        return name.strip() if name else None

    def ahead_behind(self, base: str, commit: str) -> tuple[int, int] | None:
        output = self.run("rev-list", "--left-right", "--count", f"{base}...{commit}")
        try:
            behind, ahead = (int(part) for part in (output or "").split())
        except ValueError:
            return None
        return ahead, behind

    def branch_diff(self, base: str, commit: str) -> Diff | None:
        output = self.run("diff", "-M", *DIFF_OPTIONS, f"{base}...{commit}")
        return None if output is None else parse_diff(output)

    def commit_detail(self, commit: str) -> CommitDetail | None:
        message = self.run("show", "-s", "--format=%B", commit)
        patch = self.run("show", "--format=", "--patch", *DIFF_OPTIONS, "-M", "--diff-merges=first-parent", commit)
        return None if message is None or patch is None else CommitDetail(message.rstrip("\n"), parse_diff(patch))

    # Untracked files are not part of any git diff, so the caller names them
    # and they are shown as wholly added.
    def working_diff(self, untracked: Sequence[str]) -> Diff | None:
        options = ("diff", *DIFF_OPTIONS, "-M")
        output = self.run(*options, "HEAD")
        if output is None:
            output = self.run(*options, "--cached")
        if output is None:
            return None
        diff = parse_diff(output)
        shown = sum(len(file.lines) for file in diff.files)
        for path in untracked:
            if shown >= DIFF_LINE_LIMIT:
                diff.truncated = True
                break
            file = self._new_file_diff(path)
            if file is None:
                continue
            if shown + len(file.lines) > DIFF_LINE_LIMIT:
                file.lines = file.lines[:DIFF_LINE_LIMIT - shown]
                diff.truncated = True
            diff.files.append(file)
            shown += len(file.lines)
        return diff

    # Only plain files are read: a link would show the file it points to, which
    # may lie outside the project, and reading a pipe never ends.
    def _new_file_diff(self, path: str) -> FileDiff | None:
        target = self.root / path
        try:
            if not stat.S_ISREG(target.lstat().st_mode):
                return None
            with target.open("rb") as handle:
                return diff_of_new_file(path, handle.read(UNTRACKED_FILE_LIMIT))
        except OSError:
            return None

    # Before the first commit there is no HEAD to compare with, and the staged
    # lines are compared with nothing instead.
    def line_changes(self, path: str) -> LineChanges | None:
        options = ("diff", "-U0", *DIFF_OPTIONS)
        output = self.run(*options, "HEAD", "--", path)
        if output is None:
            output = self.run(*options, "--cached", "--", path)
        return None if output is None else parse_hunks(output)
