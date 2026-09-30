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
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Label, OptionList, Static
from textual.widgets.option_list import Option

from spyc.core.overview import Overview, summary_text
from spyc.core.printable import printable
from spyc.coverage.index import Coverage
from spyc.coverage.text import summary_text as coverage_summary
from spyc.git.summary import GitSummary
from spyc.git.summary import summary_text as git_summary_text
from spyc.widgets.file_tree import FileTree


class OverviewPane(VerticalScroll):
    DEFAULT_CSS = """
    OverviewPane { padding: 1 2; }
    OverviewPane #coverage, OverviewPane #git { display: none; margin-top: 1; }
    OverviewPane .heading { margin-top: 1; text-style: bold; }
    OverviewPane OptionList { height: auto; max-height: 12; border: none; background: transparent; }
    OverviewPane #readme { margin-top: 1; color: $text-muted; }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._overview: Overview | None = None

    def compose(self) -> ComposeResult:
        yield Static(id="summary")
        yield Static(id="coverage")
        yield Static(id="git")
        yield Label("Key files", classes="heading", id="key-files-heading")
        yield OptionList(id="key-files")
        yield Static(id="readme")

    def show(self, overview: Overview) -> None:
        self._overview = overview
        self.query_one("#summary", Static).update(summary_text(overview))
        options = self.query_one("#key-files", OptionList)
        options.clear_options()
        options.add_options([Option(Text.assemble((f"{key.kind:<12}", "dim"), printable(key.path)))
                             for key in overview.key_files])
        options.highlighted = 0 if overview.key_files else None
        options.display = self.query_one("#key-files-heading").display = bool(overview.key_files)
        readme = self.query_one("#readme", Static)
        readme.display = overview.readme is not None
        readme.update(Text(overview.readme or ""))

    def show_coverage(self, coverage: Coverage | None) -> None:
        line = self.query_one("#coverage", Static)
        line.display = coverage is not None
        if coverage is not None:
            line.update(coverage_summary(coverage))

    def show_git(self, summary: GitSummary | None) -> None:
        line = self.query_one("#git", Static)
        line.display = summary is not None
        if summary is not None:
            line.update(git_summary_text(summary, time.time()))

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        event.stop()
        if self._overview is not None:
            self.post_message(FileTree.FileChosen(self._overview.key_files[event.option_index].path))
