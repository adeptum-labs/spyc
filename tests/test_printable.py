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

from textual.app import App

from repos import write_files
from spyc.core.document import load_document
from spyc.core.file_index import build_index
from spyc.core.file_picker import FilePickerSource
from spyc.core.fuzzy import PathMatcher
from spyc.core.overview import build_overview
from spyc.core.printable import printable
from spyc.core.status import status_line
from spyc.core.tree_model import TreeModel
from spyc.widgets.file_tree import FileTree
from views import ViewApp, open_file

ESCAPE = "\x1b]52;c;cm0gLXJmIH4K\x1b\\"


def test_control_characters_become_their_symbols():
    assert printable("a\x1b]52;c;xx\x1b\\b") == "a␛]52;c;xx␛\\b"
    assert printable("x\x7fy\x9bz") == "x␡y�z"


def test_tabs_are_kept_and_newlines_only_when_asked():
    assert printable("a\tb\nc") == "a\tb␊c"
    assert printable("a\tb\nc", keep_newlines=True) == "a\tb\nc"


def test_a_document_never_carries_control_characters(tmp_path):
    path = tmp_path / "a.log"
    path.write_bytes(b"a\x1b[2Jb\r\nc\rd\x0ce\n")
    assert load_document(path).lines == ("a␛[2Jb", "c␍d␌e")


async def test_the_code_view_never_writes_an_escape_sequence(tmp_path):
    async with ViewApp().run_test(size=(120, 24)) as pilot:
        view = await open_file(pilot, tmp_path, "a.log", f"x {ESCAPE} y\n".encode())
        assert "\x1b" not in view.render_line(0).text


async def test_file_names_in_the_tree_cannot_carry_escape_sequences():
    class TreeApp(App):
        def compose(self):
            yield FileTree()

        def on_mount(self):
            self.query_one(FileTree).load(TreeModel([f"evil{ESCAPE}.py"]))

    async with TreeApp().run_test() as pilot:
        labels = [str(node.label) for node in pilot.app.query_one(FileTree).root.children]
        assert labels and all("\x1b" not in label for label in labels)


def test_file_names_in_the_finder_cannot_carry_escape_sequences(tmp_path):
    paths = [f"evil{ESCAPE}.py"]
    item = FilePickerSource(tmp_path, PathMatcher(paths), lambda: []).search("evil")[0]
    assert "\x1b" not in item.label.plain


def test_the_readme_preview_and_the_status_line_are_clean(tmp_path):
    write_files(tmp_path, {"README.md": f"# Title\n{ESCAPE}\n"})
    overview = build_overview(build_index(tmp_path))
    assert "\x1b" not in overview.readme
    assert "\x1b" not in status_line(f"a{ESCAPE}.py", None, 0, 0, 1)


def test_bytes_that_are_not_text_in_a_file_name_are_shown_as_replacement_characters():
    assert printable("caf" + os.fsdecode(b"\xe9") + ".txt") == "caf�.txt"
