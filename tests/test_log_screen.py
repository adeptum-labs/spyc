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

import spyc.screens.log
from repos import git, write_files
from spyc.git.repository import Git
from spyc.location import Location
from spyc.screens.log import LogScreen
from spyc.widgets.diff_view import DiffView


class LogApp(App):
    def __init__(self, repo, path=None, focus=None):
        super().__init__()
        self.git, self.path, self.focus, self.result = Git(repo), path, focus, "unset"

    async def on_mount(self):
        await self.push_screen(LogScreen(self.git, self.path, self.focus), self.done)

    def done(self, result):
        self.result = result


def commit(repo, name, content, message):
    write_files(repo, {name: content})
    git(repo, "add", name)
    git(repo, "commit", "-qm", message)


def history(repo):
    commit(repo, "a.txt", "one\ntwo\n", "Add a")
    commit(repo, "a.txt", "one\nTWO\n", "Change a")


async def settle(pilot):
    for _ in range(2):
        await pilot.app.workers.wait_for_complete()
        await pilot.pause(0.4)


def rows(pilot):
    options = pilot.app.screen.query_one(OptionList)
    return [str(options.get_option_at_index(index).prompt) for index in range(options.option_count)]


def detail(pilot):
    return pilot.app.screen.query_one(DiffView).rows


async def test_commits_are_listed_newest_first(git_repo):
    history(git_repo)
    async with LogApp(git_repo).run_test(size=(140, 40)) as pilot:
        await settle(pilot)
        listed = rows(pilot)
        assert [("Change a" in row, "Add a" in row, "Initial commit" in row) for row in listed] == [
            (True, False, False), (False, True, False), (False, False, True)]
        assert "HEAD" in listed[0]


async def test_the_highlighted_commit_is_shown_with_its_message_and_diff(git_repo):
    history(git_repo)
    async with LogApp(git_repo).run_test(size=(140, 40)) as pilot:
        await settle(pilot)
        assert [row.text for row in detail(pilot)[:1]] == ["Change a"]
        assert any(row.kind == "file" and row.text == "modified a.txt  +1 -1" for row in detail(pilot))
        await pilot.press("down")
        await settle(pilot)
        assert any(row.kind == "file" and row.text == "added a.txt  +2 -0" for row in detail(pilot))


async def test_a_filter_narrows_the_list_by_message(git_repo):
    history(git_repo)
    async with LogApp(git_repo).run_test(size=(140, 40)) as pilot:
        await settle(pilot)
        await pilot.press("slash")
        await pilot.pause()
        await pilot.press("A", "d", "d", "enter")
        await settle(pilot)
        assert len(rows(pilot)) == 1 and "Add a" in rows(pilot)[0]


async def test_the_log_of_one_file_leaves_out_other_commits(git_repo):
    history(git_repo)
    async with LogApp(git_repo, "a.txt").run_test(size=(140, 40)) as pilot:
        await settle(pilot)
        assert len(rows(pilot)) == 2


async def test_more_commits_are_read_when_the_end_of_the_list_is_reached(git_repo, monkeypatch):
    monkeypatch.setattr(spyc.screens.log, "PAGE_SIZE", 2)
    monkeypatch.setattr(spyc.screens.log, "LOAD_AHEAD", 0)
    history(git_repo)
    commit(git_repo, "b.txt", "b", "Add b")
    commit(git_repo, "c.txt", "c", "Add c")
    async with LogApp(git_repo).run_test(size=(140, 40)) as pilot:
        await settle(pilot)
        assert len(rows(pilot)) == 2
        await pilot.press("down")
        await settle(pilot)
        await pilot.press("down", "down")
        await settle(pilot)
        assert len(rows(pilot)) == 5


async def test_enter_in_the_diff_opens_the_line_under_the_cursor(git_repo):
    history(git_repo)
    app = LogApp(git_repo)
    async with app.run_test(size=(140, 40)) as pilot:
        await settle(pilot)
        await pilot.press("enter")
        await pilot.press(*["down"] * 6, "enter")
        await pilot.pause()
    assert app.result == Location("a.txt", 2)


async def test_escape_and_q_close_the_log(git_repo):
    history(git_repo)
    for key in ("escape", "q"):
        app = LogApp(git_repo)
        async with app.run_test(size=(140, 40)) as pilot:
            await settle(pilot)
            await pilot.press(key)
            await pilot.pause()
        assert app.result is None


async def test_the_log_can_start_at_a_named_commit(git_repo):
    history(git_repo)
    commit(git_repo, "b.txt", "b", "Add b")
    change = Git(git_repo).log()[1]
    async with LogApp(git_repo, focus=change.hash).run_test(size=(140, 40)) as pilot:
        await settle(pilot)
        listed = rows(pilot)
        assert len(listed) == 3 and change.short in listed[0] and "Change a" in listed[0]
        assert pilot.app.screen.sub_title == f"Log from {change.short}"
        assert any(row.kind == "file" and row.text == "modified a.txt  +1 -1" for row in detail(pilot))


async def test_a_commit_that_cannot_be_read_does_not_leave_the_previous_diff_on_screen(git_repo, monkeypatch):
    history(git_repo)
    unreadable = Git(git_repo).log()[1].hash
    real = Git.commit_detail
    monkeypatch.setattr(Git, "commit_detail", lambda self, commit: None if commit == unreadable else real(self, commit))
    async with LogApp(git_repo).run_test(size=(140, 40)) as pilot:
        await settle(pilot)
        assert any(row.kind == "file" for row in detail(pilot))
        await pilot.press("down")
        await settle(pilot)
        assert [row.text for row in detail(pilot)] == ["Could not read this commit"]
