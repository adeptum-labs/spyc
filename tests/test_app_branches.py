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


import threading

import pytest
from textual.widgets import OptionList

from repos import git, make_repo, write_files
from spyc.app import SpycApp
from spyc.core.location import Location
from spyc.git.repository import Git
from spyc.screens.branches import BranchesScreen
from spyc.screens.log import LogScreen
from spyc.state import StateStore
from spyc.widgets.code_view import CodeView
from spyc.widgets.file_tree import FileTree
from waiting import until

SIZE = (140, 40)


@pytest.fixture
def repo(tmp_path):
    root = make_repo(tmp_path / "p", {"a.py": "def main():\n    return 1\n", "README.md": "# Demo\n"})
    git(root, "branch", "-m", "master")
    git(root, "checkout", "-q", "-b", "feature")
    write_files(root, {"a.py": "def main():\n    return 2\n", "only_here.py": "def only_here():\n    pass\n"})
    git(root, "add", ".")
    git(root, "commit", "-q", "-m", "Work on feature")
    git(root, "checkout", "-q", "master")
    return root


def make_app(root, tmp_path):
    return SpycApp(root, None, StateStore(tmp_path / "state.json"))


async def ready(pilot):
    await pilot.app.workers.wait_for_complete()
    await pilot.pause()


def top_level(app):
    return [str(node.label) for node in app.query_one(FileTree).root.children]


def choose(pilot, name):
    options = pilot.app.screen.query_one(OptionList)
    options.highlighted = next(index for index in range(options.option_count)
                               if name in options.get_option_at_index(index).prompt.plain)


async def view_feature(pilot, app):
    await pilot.press("B")
    await ready(pilot)
    choose(pilot, "feature")
    await pilot.press("v")
    await ready(pilot)
    await until(pilot, lambda: "only_here.py" in top_level(app))


async def test_B_opens_the_branches_and_v_shows_the_branch_without_switching(repo, tmp_path):
    app = make_app(repo, tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        await view_feature(pilot, app)
        assert "feature" in app.sub_title and "read-only" in app.sub_title
        assert git(repo, "branch", "--show-current").strip() == "master"
        assert not (repo / "only_here.py").exists()
        app.open_file("a.py")
        await pilot.pause()
        assert app.query_one(CodeView).document.lines[1] == "    return 2"


async def test_the_symbols_of_the_branch_are_used(repo, tmp_path):
    app = make_app(repo, tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        await view_feature(pilot, app)
        await until(pilot, lambda: app._symbols.total > 0 and app._symbols.done == app._symbols.total)
        assert [item.symbol.name for item in app._symbols.lookup("only_here")] == ["only_here"]


async def test_the_first_row_returns_to_the_working_tree(repo, tmp_path):
    app = make_app(repo, tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        await view_feature(pilot, app)
        app.open_file("a.py")
        await pilot.press("B")
        await ready(pilot)
        await pilot.press("v")
        await ready(pilot)
        await until(pilot, lambda: "only_here.py" not in top_level(app))
        assert "read-only" not in app.sub_title
        assert app.query_one(CodeView).document is None
        assert app.source.editable


async def test_what_needs_the_working_tree_is_refused(repo, tmp_path):
    app = make_app(repo, tmp_path)
    notes = []
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        await view_feature(pilot, app)
        app.open_file("a.py")
        await pilot.pause()
        app.notify = lambda message, **options: notes.append(message)
        for key in ("g", "e", "full_stop"):
            await pilot.press(key)
        assert len(notes) == 3 and all("branch" in note for note in notes)


async def test_the_log_of_the_view_starts_at_the_branch(repo, tmp_path):
    app = make_app(repo, tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        await view_feature(pilot, app)
        await pilot.press("l")
        await ready(pilot)
        assert isinstance(app.screen, LogScreen)
        options = app.screen.query_one(OptionList)
        await until(pilot, lambda: options.option_count > 0)
        assert "Work on feature" in options.get_option_at_index(0).prompt.plain


async def test_a_file_chosen_in_a_branch_diff_opens_in_the_branch(repo, tmp_path):
    app = make_app(repo, tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        await pilot.press("B")
        await ready(pilot)
        choose(pilot, "feature")
        await pilot.press("d")
        await ready(pilot)
        app.screen.dismiss(Location("only_here.py", 1))
        await ready(pilot)
        assert app.query_one(CodeView).document.lines[0] == "def only_here():"
        assert "read-only" in app.sub_title


async def test_choosing_the_working_tree_while_on_it_changes_nothing(repo, tmp_path):
    app = make_app(repo, tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        app.open_file("a.py")
        await pilot.press("B")
        await ready(pilot)
        await pilot.press("v")
        await ready(pilot)
        assert app.query_one(CodeView).display_path == "a.py"


async def test_the_overview_shows_no_git_line_of_the_working_tree_in_a_branch(repo, tmp_path):
    app = make_app(repo, tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        line = app._overview_pane.query_one("#git")
        await until(pilot, lambda: line.display)
        await view_feature(pilot, app)
        assert not line.display
        await pilot.press("B")
        await ready(pilot)
        await pilot.press("v")
        await until(pilot, lambda: line.display)


async def test_a_partial_clone_that_would_fetch_is_refused(repo, tmp_path, monkeypatch):
    monkeypatch.setattr(Git, "fetches_missing_blobs", lambda self: True)
    app = make_app(repo, tmp_path)
    notes = []
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        app.notify = lambda message, **options: notes.append(message)
        await pilot.press("B")
        await ready(pilot)
        choose(pilot, "feature")
        await pilot.press("v")
        await ready(pilot)
        assert app.source.editable and any("partial clone" in note for note in notes)


async def test_the_files_of_a_branch_are_listed_off_the_interface_thread(repo, tmp_path, monkeypatch):
    on_interface_thread = []
    real = Git.run

    def spy(self, *arguments):
        if arguments and arguments[0] == "ls-tree":
            on_interface_thread.append(threading.current_thread() is threading.main_thread())
        return real(self, *arguments)

    monkeypatch.setattr(Git, "run", spy)
    app = make_app(repo, tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        await pilot.press("B")
        await ready(pilot)
        choose(pilot, "feature")
        await pilot.press("d")
        await ready(pilot)
        app.screen.dismiss(Location("only_here.py", 1))
        await until(pilot, lambda: app.query_one(CodeView).document is not None)
        assert on_interface_thread and not any(on_interface_thread)


async def test_the_working_tree_is_never_touched(repo, tmp_path):
    def snapshot():
        return git(repo, "status", "--porcelain=v2", "--branch"), (repo / ".git" / "index").read_bytes()

    before = snapshot()
    app = make_app(repo, tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot)
        await view_feature(pilot, app)
        app.open_file("a.py")
        await pilot.pause()
    assert snapshot() == before
