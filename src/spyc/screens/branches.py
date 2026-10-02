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


import time
from dataclasses import dataclass

from rich.text import Text
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Footer, Header, OptionList
from textual.widgets.option_list import Option

from spyc.core.location import Location
from spyc.core.printable import printable
from spyc.core.timeago import age
from spyc.git.branches import Branch, default_base
from spyc.git.repository import Git
from spyc.screens.changes import ChangesScreen
from spyc.screens.log import LogScreen
from spyc.screens.prompt import Prompt

NAME_WIDTH = 30
COUNT_WIDTH = 9
PENDING = "…"


@dataclass(frozen=True)
class BranchPick:
    branch: Branch | None
    location: Location | None = None


# The branches of the repository, newest first, local ones before remote ones,
# each counted against the base they are compared with. Nothing here checks a
# branch out: the log, the diff and the files are read from git.
class BranchesScreen(Screen[BranchPick | None]):
    BINDINGS = [
        Binding("escape,q", "close", "Back"),
        Binding("d", "diff", "Diff vs base"),
        Binding("v", "view", "View files"),
        Binding("slash", "filter", "Filter"),
    ]

    def __init__(self, git: Git) -> None:
        super().__init__()
        self._git = git
        self._branches: list[Branch] = []
        self._base: Branch | None = None
        self._counts: dict[str, tuple[int, int] | None] = {}
        self._visible: list[Branch | None] = [None]
        self._filter = ""
        self._generation = 0

    def compose(self) -> ComposeResult:
        yield Header()
        yield OptionList()
        yield Footer()

    def on_mount(self) -> None:
        self.sub_title = "Branches"
        self.query_one(OptionList).focus()
        self._render_rows()
        self._load()

    @work(thread=True, exclusive=True, group="branches", exit_on_error=False)
    def _load(self) -> None:
        branches = self._git.branches()
        self.app.call_from_thread(self._loaded, branches, self._git.origin_head() if branches else None)

    def _loaded(self, branches: list[Branch] | None, origin_head: str | None) -> None:
        if branches is None:
            self.notify("Could not read the branches", severity="error")
            return
        self._branches, self._base = branches, default_base(branches, origin_head)
        if self._base is not None:
            self.sub_title = f"Branches, compared with {printable(self._base.name)}"
        self._render_rows()
        self._count()

    def _count(self) -> None:
        self._generation += 1
        if self._base is not None:
            self._count_each(self._generation, self._base.commit, [b for b in self._branches if b != self._base])

    @work(thread=True, exclusive=True, group="branch-counts", exit_on_error=False)
    def _count_each(self, generation: int, base: str, branches: list[Branch]) -> None:
        for branch in branches:
            self.app.call_from_thread(self._counted, generation, branch, self._git.ahead_behind(base, branch.commit))

    def _counted(self, generation: int, branch: Branch, counts: tuple[int, int] | None) -> None:
        if generation != self._generation:
            return
        self._counts[branch.ref] = counts
        if branch in self._visible:
            index = self._visible.index(branch)
            self.query_one(OptionList).replace_option_prompt_at_index(index, self._label(branch, time.time()))

    def _render_rows(self) -> None:
        wanted = self._filter.lower()
        shown = [branch for branch in self._ordered() if wanted in branch.name.lower()]
        self._visible = [None, *shown]
        now = time.time()
        options = self.query_one(OptionList)
        options.clear_options()
        options.add_options([Option(Text("working tree", style="bold")), *(Option(self._label(b, now)) for b in shown)])
        options.highlighted = 0

    def _ordered(self) -> list[Branch]:
        return [*(b for b in self._branches if not b.remote), *(b for b in self._branches if b.remote)]

    def _label(self, branch: Branch, now: float) -> Text:
        label = Text(no_wrap=True, overflow="ellipsis")
        label.append("* " if branch.current else "  ", style="bold green")
        label.append(f"{printable(branch.name)[:NAME_WIDTH]:<{NAME_WIDTH}} ", style="cyan" if branch.remote else "green")
        label.append(f"{self._count_text(branch):<{COUNT_WIDTH}} ", style="yellow")
        label.append(f"{age(now - branch.timestamp):>3} ", style="dim")
        label.append(f"{printable(branch.author)[:14]:<14} ", style="cyan")
        label.append(printable(branch.subject))
        return label

    def _count_text(self, branch: Branch) -> str:
        if branch == self._base:
            return "base"
        if branch.ref not in self._counts:
            return PENDING
        counts = self._counts[branch.ref]
        return "" if counts is None else f"↑{counts[0]} ↓{counts[1]}"

    # The row under the cursor: None is the working tree, which is row 0.
    def _selected(self) -> Branch | None:
        index = self.query_one(OptionList).highlighted
        return self._visible[index or 0]

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        event.stop()
        branch = self._selected()
        if branch is None:
            self.dismiss(BranchPick(None))
        else:
            self.app.push_screen(LogScreen(self._git, focus=branch.commit), lambda place: self._opened(branch, place))

    def action_diff(self) -> None:
        branch, base = self._selected(), self._base
        if branch is None:
            return
        if base is None or branch == base:
            self.notify("This is the branch the others are compared with" if base else "No base branch to compare with")
            return
        diff = ChangesScreen(lambda: self._git.branch_diff(base.commit, branch.commit), f"{branch.name} vs {base.name}")
        self.app.push_screen(diff, lambda place: self._opened(branch, place))

    def _opened(self, branch: Branch, place: Location | None) -> None:
        if place is not None:
            self.dismiss(BranchPick(branch, place))

    def action_view(self) -> None:
        self.dismiss(BranchPick(self._selected()))

    def action_filter(self) -> None:
        self.app.push_screen(Prompt("Filter branches by name", self._filter), self._filtered)

    def _filtered(self, value: str | None) -> None:
        if value is not None:
            self._filter = value.strip()
            self._render_rows()

    def action_close(self) -> None:
        self.dismiss(None)
