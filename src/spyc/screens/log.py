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

from rich.text import Text
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Footer, Header, OptionList
from textual.widgets.option_list import Option

from spyc.diff_rows import rows_of
from spyc.git.log import Commit
from spyc.git.repository import CommitDetail, Git
from spyc.location import Location
from spyc.printable import printable
from spyc.screens.prompt import Prompt
from spyc.timeago import age
from spyc.widgets.diff_view import DiffView

PAGE_SIZE = 200
LOAD_AHEAD = 5
DETAIL_DELAY = 0.1
CACHED_DETAILS = 30


def _label(commit: Commit, now: float) -> Text:
    label = Text(no_wrap=True, overflow="ellipsis")
    label.append(f"{commit.short} ", style="yellow")
    label.append(f"{age(now - commit.timestamp):>3} ", style="dim")
    label.append(f"{printable(commit.author)[:14]:<14} ", style="cyan")
    label.append(printable(commit.subject))
    if commit.refs:
        label.append(f"  ({printable(commit.refs)})", style="green")
    return label


# The commits of the repository, or of one file, newest first, with the
# highlighted commit's message and diff beside them. Enter on a line of the
# diff closes the log and gives the file and line to open.
class LogScreen(Screen[Location | None]):
    DEFAULT_CSS = """
    LogScreen Horizontal { height: 1fr; }
    LogScreen OptionList { width: 50%; border: none; border-right: solid $primary; }
    LogScreen DiffView { width: 50%; }
    """
    BINDINGS = [
        Binding("escape,q", "close", "Back"),
        Binding("slash", "filter", "Filter"),
    ]

    def __init__(self, git: Git, path: str | None = None, focus: str | None = None) -> None:
        super().__init__()
        self._git, self._path, self._wanted = git, path, focus
        self._commits: list[Commit] = []
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
        self.sub_title = "Log" if self._path is None else f"Log of {printable(self._path)}"
        self.query_one(OptionList).focus()
        self._restart()

    def _restart(self) -> None:
        self._generation += 1
        self._commits, self._loading, self._exhausted = [], False, False
        self.query_one(OptionList).clear_options()
        self.query_one(DiffView).show_rows([])
        self._load_page()

    def _load_page(self) -> None:
        if not self._loading and not self._exhausted:
            self._loading = True
            self._read_page(self._generation, len(self._commits), self._grep)

    @work(thread=True, group="log-page", exit_on_error=False)
    def _read_page(self, generation: int, skip: int, grep: str) -> None:
        commits = self._git.log(PAGE_SIZE, skip, self._path, grep or None)
        self.app.call_from_thread(self._page_ready, generation, commits)

    def _page_ready(self, generation: int, commits: list[Commit] | None) -> None:
        if generation != self._generation:
            return
        self._loading = False
        if commits is None:
            self._exhausted = True
            self.notify("Could not read the log", severity="error")
            return
        first = not self._commits
        self._commits.extend(commits)
        self._exhausted = len(commits) < PAGE_SIZE
        options = self.query_one(OptionList)
        now = time.time()
        options.add_options([Option(_label(commit, now)) for commit in commits])
        if self._wanted is not None:
            self._look_for_wanted_commit()
        elif first and commits:
            options.highlighted = 0

    # A commit that was asked for may be on a later page, so pages are read
    # until it turns up or there are no more.
    def _look_for_wanted_commit(self) -> None:
        options = self.query_one(OptionList)
        found = next((index for index, commit in enumerate(self._commits) if commit.hash == self._wanted), None)
        if found is not None:
            options.highlighted, self._wanted = found, None
        elif self._exhausted:
            options.highlighted, self._wanted = 0 if self._commits else None, None
        else:
            self._load_page()

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        index = event.option_index
        if index >= len(self._commits) - 1 - LOAD_AHEAD:
            self._load_page()
        if self._detail_timer is not None:
            self._detail_timer.stop()
        self._detail_timer = self.set_timer(DETAIL_DELAY, lambda: self._show_detail(index))

    def _show_detail(self, index: int) -> None:
        if not 0 <= index < len(self._commits):
            return
        commit = self._commits[index]
        if commit.hash in self._details:
            self._display(self._details[commit.hash])
        else:
            self._read_detail(commit.hash)

    @work(thread=True, group="log-detail", exit_on_error=False)
    def _read_detail(self, commit: str) -> None:
        self.app.call_from_thread(self._detail_ready, commit, self._git.commit_detail(commit))

    def _detail_ready(self, commit: str, detail: CommitDetail | None) -> None:
        if detail is None:
            return
        if len(self._details) >= CACHED_DETAILS:
            self._details.pop(next(iter(self._details)))
        self._details[commit] = detail
        highlighted = self.query_one(OptionList).highlighted
        if highlighted is not None and highlighted < len(self._commits) and self._commits[highlighted].hash == commit:
            self._display(detail)

    def _display(self, detail: CommitDetail) -> None:
        self.query_one(DiffView).show_rows(rows_of(detail.message, detail.diff))

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.query_one(DiffView).focus()

    def on_diff_view_open_location(self, message: DiffView.OpenLocation) -> None:
        message.stop()
        self.dismiss(Location(message.path, message.line))

    def action_filter(self) -> None:
        self.app.push_screen(Prompt("Filter commits by message", self._grep), self._filtered)

    def _filtered(self, value: str | None) -> None:
        if value is not None:
            self._grep, self._wanted = value.strip(), None
            self._restart()

    def action_close(self) -> None:
        self.dismiss(None)
