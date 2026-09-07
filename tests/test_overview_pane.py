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


from textual.app import App
from textual.widgets import OptionList

from repos import write_files
from spyc.file_index import build_index
from spyc.overview import build_overview
from spyc.widgets.overview_pane import OverviewPane
from spyc.widgets.status_bar import StatusBar


class PaneApp(App):
    def __init__(self, overview):
        super().__init__()
        self.overview, self.chosen = overview, []

    def compose(self):
        yield OverviewPane()
        yield StatusBar()

    def on_mount(self):
        self.query_one(OverviewPane).show(self.overview)

    def on_file_tree_file_chosen(self, message):
        self.chosen.append(message.path)


def overview_of(root, files):
    write_files(root, files)
    return build_overview(build_index(root))


async def test_key_files_are_listed_and_enter_chooses_one(tmp_path):
    app = PaneApp(overview_of(tmp_path, {"README.md": "hi", "pom.xml": "<project/>"}))
    async with app.run_test(size=(100, 30)) as pilot:
        options = app.query_one(OptionList)
        assert options.option_count == 2
        options.focus()
        await pilot.press("enter")
        await pilot.pause()
    assert app.chosen == ["README.md"]


async def test_a_project_without_key_files_hides_the_list(tmp_path):
    app = PaneApp(overview_of(tmp_path, {"notes.txt": "hi"}))
    async with app.run_test(size=(100, 30)):
        assert not app.query_one(OptionList).display


async def test_the_status_bar_keeps_what_it_shows(tmp_path):
    app = PaneApp(overview_of(tmp_path, {"a.py": "x"}))
    async with app.run_test(size=(100, 30)):
        bar = app.query_one(StatusBar)
        bar.show("a.py", "Python", 0, 0, 1)
        assert bar.text == "a.py · Python · 1:1 of 1"


async def test_the_status_bar_shows_brackets_in_a_path_as_they_are(tmp_path):
    app = PaneApp(overview_of(tmp_path, {"a.py": "x"}))
    async with app.run_test(size=(100, 30)) as pilot:
        bar = app.query_one(StatusBar)
        bar.show("app/[id]/page.tsx", "TSX", 0, 0, 1)
        await pilot.pause()
        assert bar.render().plain.startswith("app/[id]/page.tsx")
