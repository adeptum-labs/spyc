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


from dataclasses import dataclass

from spyc.git.log import FIELD_SEPARATOR

LOCAL_PREFIX, REMOTE_PREFIX = "refs/heads/", "refs/remotes/"
# The subject comes last so that a separator inside it stays in the subject.
BRANCH_FORMAT = "%1f".join(["%(refname)", "%(objectname)", "%(upstream:short)", "%(committerdate:unix)",
                            "%(authorname)", "%(HEAD)", "%(subject)"]) + "%00"
FALLBACKS = ("master", "main")
REMOTE_FALLBACKS = ("origin/master", "origin/main")


@dataclass(frozen=True)
class Branch:
    name: str
    ref: str
    remote: bool
    commit: str
    subject: str
    author: str
    timestamp: int
    upstream: str
    current: bool


def parse_branches(output: str) -> list[Branch]:
    branches = []
    for entry in filter(None, output.split("\0")):
        try:
            ref, commit, upstream, timestamp, author, head, subject = entry.strip("\n").split(FIELD_SEPARATOR, 6)
            remote = ref.startswith(REMOTE_PREFIX)
            name = ref.removeprefix(REMOTE_PREFIX if remote else LOCAL_PREFIX)
            if remote and name.endswith("/HEAD"):
                continue
            branches.append(Branch(name, ref, remote, commit, subject, author, int(timestamp), upstream, head.strip() == "*"))
        except ValueError:
            continue
    return branches


# What the others are compared with: the branch the remote calls its default,
# else master or main, the local one before the remote one, and when the
# repository has none of them the branch that is checked out.
def default_base(branches: list[Branch], origin_head: str | None) -> Branch | None:
    by_name = {branch.name: branch for branch in branches}
    named = origin_head.partition("/")[2] if origin_head else None
    candidates = [name for name in (named, *FALLBACKS, origin_head, *REMOTE_FALLBACKS) if name]
    found = next((by_name[name] for name in candidates if name in by_name), None)
    return found or next((branch for branch in branches if branch.current), None)
