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


from collections.abc import Callable, Sequence

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Footer, Header

from spyc.core.location import Location
from spyc.git.diff import Diff
from spyc.git.diff_rows import DiffRow, rows_of
from spyc.git.repository import Git
from spyc.widgets.diff_view import DiffView


# Everything that differs from the last commit, staged or not, and the files
# git does not track yet, as one diff to read through.
class ChangesScreen(Screen[Location | None]):
    BINDINGS = [
        Binding("escape,q", "close", "Back"),
        Binding("R", "reload", "Reload"),
    ]

    def __init__(self, git: Git, untracked: Callable[[], Sequence[str]]) -> None:
        super().__init__()
        self._git, self._untracked = git, untracked

    def compose(self) -> ComposeResult:
        yield Header()
        yield DiffView()
        yield Footer()

    def on_mount(self) -> None:
        self.sub_title = "Changes"
        self.query_one(DiffView).focus()
        self.action_reload()

    def action_reload(self) -> None:
        self._read(list(self._untracked()))

    @work(thread=True, exclusive=True, group="changes", exit_on_error=False)
    def _read(self, untracked: list[str]) -> None:
        self.app.call_from_thread(self._ready, self._git.working_diff(untracked))

    def _ready(self, diff: Diff | None) -> None:
        if diff is None:
            rows = [DiffRow("info", "Not a git repository")]
        elif not diff.files:
            rows = [DiffRow("info", "No changes")]
        else:
            rows = rows_of(None, diff)
            self.sub_title = (f"Changes: {len(diff.files)} files, "
                              f"+{sum(file.additions for file in diff.files)} -{sum(file.deletions for file in diff.files)}")
        self.query_one(DiffView).show_rows(rows)

    def on_diff_view_open_location(self, message: DiffView.OpenLocation) -> None:
        message.stop()
        self.dismiss(Location(message.path, message.line))

    def action_close(self) -> None:
        self.dismiss(None)
