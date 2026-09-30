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

from spyc.core.tree_model import TreeModel
from spyc.widgets.file_tree import FileTree

PATHS = ["README.md", "src/main/java/A.java", "src/main/java/B.java", "src/test/T.java", "docs/guide.md", "Zed.txt"]


class TreeApp(App):
    def __init__(self):
        super().__init__()
        self.chosen: list[str] = []

    def compose(self):
        yield FileTree()

    def on_mount(self):
        self.query_one(FileTree).load(TreeModel(PATHS))

    def on_file_tree_file_chosen(self, message):
        self.chosen.append(message.path)


def labels(nodes):
    return [str(node.label) for node in nodes]


async def test_top_level_entries_are_listed_and_the_cursor_starts_on_the_first():
    async with TreeApp().run_test() as pilot:
        tree = pilot.app.query_one(FileTree)
        assert labels(tree.root.children) == ["docs", "src", "README.md", "Zed.txt"]
        assert tree.cursor_node.data.path == "docs"


async def test_directories_fill_in_when_they_are_opened():
    async with TreeApp().run_test() as pilot:
        tree = pilot.app.query_one(FileTree)
        await pilot.press("j", "right")
        node = tree.cursor_node
        assert node.is_expanded and labels(node.children) == ["main/java", "test"]


async def test_left_closes_a_directory_then_steps_out_of_it():
    async with TreeApp().run_test() as pilot:
        tree = pilot.app.query_one(FileTree)
        await pilot.press("j", "right", "j", "right", "j")
        assert tree.cursor_node.data.path == "src/main/java/A.java"
        await pilot.press("left")
        assert tree.cursor_node.data.path == "src/main/java"
        await pilot.press("left")
        assert not tree.cursor_node.is_expanded
        await pilot.press("left")
        assert tree.cursor_node.data.path == "src"


async def test_right_on_an_open_directory_steps_into_it():
    async with TreeApp().run_test() as pilot:
        tree = pilot.app.query_one(FileTree)
        await pilot.press("j", "right", "right")
        assert tree.cursor_node.data.path == "src/main/java"


async def test_enter_on_a_file_chooses_it():
    app = TreeApp()
    async with app.run_test() as pilot:
        await pilot.press("j", "j", "enter")
        await pilot.pause()
        assert app.chosen == ["README.md"]


async def test_enter_on_a_directory_only_toggles_it():
    app = TreeApp()
    async with app.run_test() as pilot:
        await pilot.press("enter")
        await pilot.pause()
        assert app.chosen == [] and pilot.app.query_one(FileTree).cursor_node.is_expanded


async def test_reveal_opens_the_directories_above_a_file_and_selects_it():
    async with TreeApp().run_test() as pilot:
        tree = pilot.app.query_one(FileTree)
        tree.reveal("src/main/java/B.java")
        await pilot.pause()
        assert tree.cursor_node.data.path == "src/main/java/B.java"


async def test_reveal_opens_a_directory_too():
    async with TreeApp().run_test() as pilot:
        tree = pilot.app.query_one(FileTree)
        tree.reveal("docs")
        await pilot.pause()
        assert tree.cursor_node.data.path == "docs" and tree.cursor_node.is_expanded


async def test_revealing_a_path_that_is_not_listed_changes_nothing():
    async with TreeApp().run_test() as pilot:
        tree = pilot.app.query_one(FileTree)
        tree.reveal("nope/x.py")
        assert tree.cursor_node.data.path == "docs"


async def test_loading_again_replaces_the_tree():
    async with TreeApp().run_test() as pilot:
        tree = pilot.app.query_one(FileTree)
        tree.load(TreeModel(["a.txt"]))
        assert labels(tree.root.children) == ["a.txt"]


async def test_status_marks_files_and_the_directories_above_them():
    async with TreeApp().run_test() as pilot:
        tree = pilot.app.query_one(FileTree)
        tree.set_status({"docs/guide.md": "M", "src/test/T.java": "?", "Zed.txt": "A"})
        assert labels(tree.root.children) == ["docs M", "src ?", "README.md", "Zed.txt A"]


async def test_status_reaches_nodes_opened_later_and_can_be_cleared():
    async with TreeApp().run_test() as pilot:
        tree = pilot.app.query_one(FileTree)
        tree.set_status({"src/main/java/A.java": "D"})
        await pilot.press("j", "right")
        assert labels(tree.cursor_node.children) == ["main/java D", "test"]
        tree.set_status({})
        assert labels(tree.cursor_node.children) == ["main/java", "test"]
        assert labels(tree.root.children)[1] == "src"


async def test_directory_marks_that_were_worked_out_elsewhere_are_used_as_given():
    async with TreeApp().run_test() as pilot:
        tree = pilot.app.query_one(FileTree)
        tree.set_status({}, {"docs": "M"})
        assert labels(tree.root.children)[0] == "docs M"


async def test_coverage_shares_follow_the_names_of_files_and_directories_and_can_be_cleared():
    async with TreeApp().run_test() as pilot:
        tree = pilot.app.query_one(FileTree)
        tree.set_coverage({"README.md": 83.4, "src/main/java/A.java": 10.0}, {"src": 50.0})
        assert labels(tree.root.children) == ["docs", "src 50%", "README.md 83%", "Zed.txt"]
        await pilot.press("j", "right", "right", "right")
        assert labels(tree.cursor_node.children) == ["A.java 10%", "B.java"]
        tree.set_coverage({}, {})
        assert labels(tree.root.children) == ["docs", "src", "README.md", "Zed.txt"]
        assert labels(tree.cursor_node.children) == ["A.java", "B.java"]
