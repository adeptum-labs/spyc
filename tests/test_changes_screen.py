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

from repos import git, write_files
from spyc.core.location import Location
from spyc.git.repository import Git
from spyc.screens.changes import ChangesScreen
from spyc.widgets.diff_view import DiffView


class ChangesApp(App):
    def __init__(self, repo, untracked=(), load=None, title="Changes"):
        super().__init__()
        self.git, self.untracked, self.result = Git(repo), list(untracked), "unset"
        self._load, self._title = load, title

    async def on_mount(self):
        load = self._load or (lambda: self.git.working_diff(self.untracked))
        await self.push_screen(ChangesScreen(load, self._title), self.done)

    def done(self, result):
        self.result = result


async def settle(pilot):
    for _ in range(2):
        await pilot.app.workers.wait_for_complete()
        await pilot.pause(0.3)


def rows(pilot):
    return pilot.app.screen.query_one(DiffView).rows


async def test_staged_unstaged_and_untracked_changes_are_all_listed(git_repo):
    (git_repo / "README.md").write_text("# Project\n\nchanged\n")
    write_files(git_repo, {"new.py": "x = 1\n", "staged.py": "y = 2\n"})
    git(git_repo, "add", "staged.py")
    async with ChangesApp(git_repo, ["new.py"]).run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        titles = sorted(row.text.split("  ")[0] for row in rows(pilot) if row.kind == "file")
        assert titles == ["added new.py", "added staged.py", "modified README.md"]


async def test_a_clean_tree_says_so(git_repo):
    async with ChangesApp(git_repo).run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        assert [row.text for row in rows(pilot)] == ["No changes"]


async def test_enter_opens_the_line_under_the_cursor(git_repo):
    (git_repo / "README.md").write_text("# Project\n\nA test project.\nMore\n")
    app = ChangesApp(git_repo)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        add = next(index for index, row in enumerate(rows(pilot)) if row.kind == "add")
        await pilot.press(*["down"] * add, "enter")
        await pilot.pause()
    assert app.result == Location("README.md", 4)


async def test_escape_closes_and_r_reads_the_changes_again(git_repo):
    app = ChangesApp(git_repo)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        (git_repo / "README.md").write_text("# Project\n\nchanged\n")
        await pilot.press("R")
        await settle(pilot)
        assert any(row.kind == "file" for row in rows(pilot))
        await pilot.press("escape")
        await pilot.pause()
    assert app.result is None


async def test_any_diff_can_be_shown_with_its_own_title(git_repo):
    git(git_repo, "checkout", "-q", "-b", "feature")
    write_files(git_repo, {"added.py": "x = 1\n"})
    git(git_repo, "add", ".")
    git(git_repo, "commit", "-q", "-m", "Add a file")
    base = git(git_repo, "rev-parse", "HEAD~1").strip()
    app = ChangesApp(git_repo, load=lambda: Git(git_repo).branch_diff(base, "feature"), title="feature vs master")
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        assert any("added.py" in row.text for row in rows(pilot) if row.kind == "file")
        assert pilot.app.screen.sub_title.startswith("feature vs master: 1 files")


async def test_outside_a_repository_the_screen_says_so(tmp_path):
    async with ChangesApp(tmp_path).run_test(size=(120, 40)) as pilot:
        await settle(pilot)
        assert [row.text for row in rows(pilot)] == ["Not a git repository"]
