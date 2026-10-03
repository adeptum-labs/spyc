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
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Footer, Header, OptionList
from textual.widgets.option_list import Option

from spyc.core.location import Location
from spyc.core.printable import printable
from spyc.core.timeago import age
from spyc.git.branches import Comparison
from spyc.git.diff_rows import DiffRow, rows_of
from spyc.git.log import Commit
from spyc.git.repository import CommitDetail, Git
from spyc.screens.prompt import Prompt
from spyc.widgets.diff_view import DiffView

PAGE_SIZE = 200
LOAD_AHEAD = 5
DETAIL_DELAY = 0.1
CACHED_DETAILS = 30
NO_MARKER, SHARED_MARKER = ("", ""), ("  ", "")
AHEAD_MARKER, BEHIND_MARKER = ("▌ ", "bold green"), ("▐ ", "bold magenta")
SHARED_TITLE = Text("── shared " + "─" * 30, style="dim")


# One stretch of the log, read page by page after the stretch before it.
@dataclass(frozen=True)
class Section:
    title: Text | None
    marker: tuple[str, str]
    revisions: tuple[str, ...]


def _side(name: str, arrow: str, count: int | None, marker: tuple[str, str], revision: str) -> list[Section]:
    if count == 0:
        return []
    title = Text(f"Only on {printable(name)}" + ("" if count is None else f" ({arrow}{count})"), style="bold")
    return [Section(title, marker, (revision,))]


def _label(commit: Commit, now: float, marker: tuple[str, str]) -> Text:
    label = Text(no_wrap=True, overflow="ellipsis")
    label.append(*marker)
    label.append(f"{commit.short} ", style="yellow")
    label.append(f"{age(now - commit.timestamp):>3} ", style="dim")
    label.append(f"{printable(commit.author)[:14]:<14} ", style="cyan")
    label.append(printable(commit.subject))
    if commit.refs:
        label.append(f"  ({printable(commit.refs)})", style="green")
    return label


# The commits of the repository, or of one file, newest first, with the
# highlighted commit's message and diff beside them. Enter on a line of the
# diff closes the log and gives the file and line to open. The log of a branch
# compared with its base lists what only the branch has, then what only the
# base has, then the history they share.
class LogScreen(Screen[Location | None]):
    DEFAULT_CSS = """
    LogScreen Horizontal { height: 1fr; }
    LogScreen OptionList { width: 50%; border: none; border-right: solid $primary; text-wrap: nowrap;
                           text-overflow: ellipsis; }
    LogScreen DiffView { width: 50%; }
    """
    BINDINGS = [
        Binding("escape,q", "close", "Back"),
        Binding("slash", "filter", "Filter"),
    ]

    def __init__(self, git: Git, path: str | None = None, focus: str | None = None,
                 comparison: Comparison | None = None) -> None:
        super().__init__()
        self._git, self._path, self._comparison = git, path, comparison
        self._revision = comparison.branch.commit if comparison else focus
        self._sections = None if comparison else [Section(None, NO_MARKER, (self._revision,) if self._revision else ())]
        self._rows: list[Commit | None] = []
        self._section = self._skip = 0
        self._grep = ""
        self._generation = 0
        self._loading = False
        self._exhausted = False
        self._details: dict[str, CommitDetail] = {}
        self._detail_timer = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            yield OptionList()
            yield DiffView()
        yield Footer()

    def on_mount(self) -> None:
        if self._comparison:
            self.sub_title = (f"Log of {printable(self._comparison.branch.name)} "
                              f"compared with {printable(self._comparison.base.name)}")
        else:
            self.sub_title = "Log" if self._path is None else f"Log of {printable(self._path)}"
        self.query_one(OptionList).focus()
        self._restart()

    def _restart(self) -> None:
        self._generation += 1
        self._rows, self._section, self._skip, self._loading, self._exhausted = [], 0, 0, False, False
        self.query_one(OptionList).clear_options()
        self.query_one(DiffView).show_rows([])
        self._load_page()

    def _load_page(self) -> None:
        if not self._loading and not self._exhausted:
            self._loading = True
            self._read_page(self._generation, self._section, self._skip, self._grep)

    @work(thread=True, group="log-page", exit_on_error=False)
    def _read_page(self, generation: int, section: int, skip: int, grep: str) -> None:
        sections = self._sections or self._compared()
        commits = self._git.log(PAGE_SIZE, skip, self._path, grep or None, sections[section].revisions) \
            if section < len(sections) else []
        self.app.call_from_thread(self._page_ready, generation, sections, commits)

    # Commit hashes only, never branch names, so that no name is read as an option.
    def _compared(self) -> list[Section]:
        branch, base = self._comparison.branch, self._comparison.base
        ahead, behind = self._git.ahead_behind(base.commit, branch.commit) or (None, None)
        merge_bases = self._git.merge_bases(base.commit, branch.commit)
        return [*_side(branch.name, "↑", ahead, AHEAD_MARKER, f"{base.commit}..{branch.commit}"),
                *_side(base.name, "↓", behind, BEHIND_MARKER, f"{branch.commit}..{base.commit}"),
                *([Section(SHARED_TITLE, SHARED_MARKER, tuple(merge_bases))] if merge_bases else [])]

    # A title comes with the first commit of its section, so a section the
    # filter empties leaves none behind. A section that ends reads the next at
    # once: the cursor may never reach the end of a short one.
    def _page_ready(self, generation: int, sections: list[Section], commits: list[Commit] | None) -> None:
        if generation != self._generation:
            return
        self._sections, self._loading = sections, False
        if commits is None:
            self._exhausted = True
            self.notify("Could not read the log", severity="error")
            return
        options = self.query_one(OptionList)
        first = not self._rows
        if commits:
            section = sections[self._section]
            if self._skip == 0 and section.title:
                options.add_option(Option(section.title, disabled=True))
                self._rows.append(None)
            now = time.time()
            options.add_options([Option(_label(commit, now, section.marker)) for commit in commits])
            self._rows.extend(commits)
            self._skip += len(commits)
        if first and commits:
            options.highlighted = len(self._rows) - len(commits)
            if self._revision and not self._comparison:
                self.sub_title = f"Log from {commits[0].short}"
        if len(commits) < PAGE_SIZE:
            self._section, self._skip = self._section + 1, 0
            self._exhausted = self._section >= len(sections)
            self._load_page()

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        index = event.option_index
        if index >= len(self._rows) - 1 - LOAD_AHEAD:
            self._load_page()
        if self._detail_timer is not None:
            self._detail_timer.stop()
        self._detail_timer = self.set_timer(DETAIL_DELAY, lambda: self._show_detail(index))

    def _show_detail(self, index: int) -> None:
        commit = self._rows[index] if 0 <= index < len(self._rows) else None
        if commit is None:
            return
        if commit.hash in self._details:
            self._display(self._details[commit.hash])
        else:
            self._say("Loading...")
            self._read_detail(commit.hash)

    @work(thread=True, group="log-detail", exit_on_error=False)
    def _read_detail(self, commit: str) -> None:
        self.app.call_from_thread(self._detail_ready, commit, self._git.commit_detail(commit))

    # Whatever the outcome, the view never keeps the diff of another commit
    # beside the one that is highlighted: Enter would open the wrong lines.
    def _detail_ready(self, commit: str, detail: CommitDetail | None) -> None:
        if detail is not None:
            if len(self._details) >= CACHED_DETAILS:
                self._details.pop(next(iter(self._details)))
            self._details[commit] = detail
        if not self._is_highlighted(commit):
            return
        if detail is None:
            self._say("Could not read this commit")
        else:
            self._display(detail)

    def _is_highlighted(self, commit: str) -> bool:
        highlighted = self.query_one(OptionList).highlighted
        row = self._rows[highlighted] if highlighted is not None and highlighted < len(self._rows) else None
        return row is not None and row.hash == commit

    def _display(self, detail: CommitDetail) -> None:
        self.query_one(DiffView).show_rows(rows_of(detail.message, detail.diff))

    def _say(self, text: str) -> None:
        self.query_one(DiffView).show_rows([DiffRow("info", text)])

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.query_one(DiffView).focus()

    def on_diff_view_open_location(self, message: DiffView.OpenLocation) -> None:
        message.stop()
        self.dismiss(Location(message.path, message.line))

    def action_filter(self) -> None:
        self.app.push_screen(Prompt("Filter commits by message", self._grep), self._filtered)

    def _filtered(self, value: str | None) -> None:
        if value is not None:
            self._grep = value.strip()
            self._restart()

    def action_close(self) -> None:
        self.dismiss(None)
