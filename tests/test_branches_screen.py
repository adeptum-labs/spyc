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


import pytest
from textual.app import App
from textual.widgets import OptionList

from repos import git, make_repo, write_files
from spyc.core.location import Location
from spyc.git.repository import Git
from spyc.screens.branches import BranchesScreen
from spyc.screens.changes import ChangesScreen
from spyc.screens.log import LogScreen
from waiting import until


class BranchesApp(App):
    def __init__(self, repo):
        super().__init__()
        self.git, self.result = Git(repo), "unset"

    async def on_mount(self):
        await self.push_screen(BranchesScreen(self.git), self.done)

    def done(self, result):
        self.result = result


@pytest.fixture
def repo(tmp_path):
    root = make_repo(tmp_path / "p", {"a.py": "x = 1\n"})
    git(root, "branch", "-m", "master")
    git(root, "checkout", "-q", "-b", "feature/x")
    write_files(root, {"b.py": "y = 2\n"})
    git(root, "add", ".")
    git(root, "commit", "-q", "-m", "Add b")
    git(root, "checkout", "-q", "master")
    return root


def labels(pilot):
    options = pilot.app.screen.query_one(OptionList)
    return [options.get_option_at_index(i).prompt.plain for i in range(options.option_count)]


def row_of(pilot, name):
    return next(index for index, label in enumerate(labels(pilot)) if name in label)


def select(pilot, name):
    pilot.app.screen.query_one(OptionList).highlighted = row_of(pilot, name)


async def ready(pilot):
    await pilot.app.workers.wait_for_complete()
    await pilot.pause()


async def test_the_working_tree_comes_first_then_the_branches_with_counts_against_the_base(repo):
    async with BranchesApp(repo).run_test(size=(120, 30)) as pilot:
        await ready(pilot)
        await until(pilot, lambda: "↑1 ↓0" in labels(pilot)[row_of(pilot, "feature/x")])
        rows = labels(pilot)
        assert rows[0].startswith("working tree")
        assert "base" in rows[row_of(pilot, "master")] and "↑" not in rows[row_of(pilot, "master")]
        assert "Add b" in rows[row_of(pilot, "feature/x")]
        assert "compared with master" in pilot.app.screen.sub_title


async def test_v_chooses_a_branch_and_the_first_row_chooses_the_working_tree(repo):
    app = BranchesApp(repo)
    async with app.run_test(size=(120, 30)) as pilot:
        await ready(pilot)
        select(pilot, "feature/x")
        await pilot.press("v")
        await pilot.pause()
        assert app.result.branch.name == "feature/x" and app.result.location is None
        assert app.result.base.name == "master"
    app = BranchesApp(repo)
    async with app.run_test(size=(120, 30)) as pilot:
        await ready(pilot)
        await pilot.press("v")
        await pilot.pause()
        assert app.result.branch is None and app.result.location is None


async def test_enter_opens_the_log_of_the_branch(repo):
    async with BranchesApp(repo).run_test(size=(120, 30)) as pilot:
        await ready(pilot)
        select(pilot, "feature/x")
        await pilot.press("enter")
        await ready(pilot)
        assert isinstance(pilot.app.screen, LogScreen)
        assert pilot.app.screen.sub_title == "Log of feature/x compared with master"


async def test_the_log_of_the_base_is_not_compared_with_itself(repo):
    async with BranchesApp(repo).run_test(size=(120, 30)) as pilot:
        await ready(pilot)
        select(pilot, "master")
        await pilot.press("enter")
        await ready(pilot)
        assert pilot.app.screen.sub_title.startswith("Log from")


async def test_d_opens_the_diff_against_the_base_and_not_on_the_base_itself(repo):
    async with BranchesApp(repo).run_test(size=(120, 30)) as pilot:
        await ready(pilot)
        select(pilot, "master")
        await pilot.press("d")
        await pilot.pause()
        assert isinstance(pilot.app.screen, BranchesScreen)
        select(pilot, "feature/x")
        await pilot.press("d")
        await ready(pilot)
        assert isinstance(pilot.app.screen, ChangesScreen)
        assert pilot.app.screen.sub_title.startswith("feature/x vs master")


async def test_a_file_chosen_in_the_diff_comes_back_with_its_branch(repo):
    app = BranchesApp(repo)
    async with app.run_test(size=(120, 30)) as pilot:
        await ready(pilot)
        select(pilot, "feature/x")
        await pilot.press("d")
        await ready(pilot)
        pilot.app.screen.dismiss(Location("b.py", 1))
        await pilot.pause()
        assert app.result.branch.name == "feature/x" and app.result.location == Location("b.py", 1)


async def test_the_filter_keeps_the_working_tree_row_and_the_matching_branches(repo):
    async with BranchesApp(repo).run_test(size=(120, 30)) as pilot:
        await ready(pilot)
        pilot.app.screen._filtered("feat")
        await pilot.pause()
        rows = labels(pilot)
        assert len(rows) == 2 and rows[0].startswith("working tree") and "feature/x" in rows[1]


async def test_after_filtering_the_first_matching_branch_is_the_one_under_the_cursor(repo):
    async with BranchesApp(repo).run_test(size=(120, 30)) as pilot:
        await ready(pilot)
        options = pilot.app.screen.query_one(OptionList)
        pilot.app.screen._filtered("feat")
        await pilot.pause()
        assert options.highlighted == 1
        pilot.app.screen._filtered("nothing like it")
        await pilot.pause()
        assert options.highlighted == 0


async def test_a_repository_without_commits_says_so_and_only_offers_the_working_tree(tmp_path):
    root = tmp_path / "empty"
    root.mkdir()
    git(root, "init", "-q")
    app = BranchesApp(root)
    notes = []
    app.notify = lambda message, **options: notes.append(message)
    async with app.run_test(size=(120, 30)) as pilot:
        await ready(pilot)
        assert len(labels(pilot)) == 1 and labels(pilot)[0].startswith("working tree")
        assert notes == ["No branches yet: the repository has no commits"]


async def test_branch_names_are_shown_whole_up_to_a_generous_width(tmp_path):
    root = make_repo(tmp_path / "p", {"a.py": "x = 1\n"})
    first, second = "feature/" + "a" * 40 + "-one", "feature/" + "a" * 40 + "-two"
    for name in (first, second):
        git(root, "branch", name)
    async with BranchesApp(root).run_test(size=(160, 30)) as pilot:
        await ready(pilot)
        assert any(first in label for label in labels(pilot)) and any(second in label for label in labels(pilot))
