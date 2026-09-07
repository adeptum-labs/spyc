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


from repos import git, write_files
from spyc.git.repository import Git
from spyc.git.status import rollup


def test_a_clean_repository_has_no_status(git_repo):
    assert Git(git_repo).status() == {}


def test_each_kind_of_change_has_its_code(git_repo):
    (git_repo / "README.md").write_text("changed\n")
    write_files(git_repo, {"new.py": "x", "src/app/extra.py": "y"})
    git(git_repo, "add", "src/app/extra.py")
    (git_repo / "pyproject.toml").unlink()
    git(git_repo, "mv", ".gitignore", "ignore-renamed")
    assert Git(git_repo).status() == {
        "README.md": "M", "new.py": "?", "src/app/extra.py": "A", "pyproject.toml": "D", "ignore-renamed": "R"}


def test_ignored_files_have_no_status(git_repo):
    write_files(git_repo, {"build/out.o": ""})
    assert Git(git_repo).status() == {}


def test_a_merge_conflict_is_reported(git_repo):
    git(git_repo, "checkout", "-q", "-b", "other")
    (git_repo / "README.md").write_text("other\n")
    git(git_repo, "commit", "-qam", "Other")
    git(git_repo, "checkout", "-q", "-")
    (git_repo / "README.md").write_text("mine\n")
    git(git_repo, "commit", "-qam", "Mine")
    try:
        git(git_repo, "merge", "other")
    except Exception:
        pass
    assert Git(git_repo).status()["README.md"] == "U"


def test_paths_with_odd_characters_survive(git_repo):
    write_files(git_repo, {"with space ü.py": "x"})
    assert Git(git_repo).status() == {"with space ü.py": "?"}


def test_outside_a_repository_there_is_no_status(tmp_path):
    assert Git(tmp_path).status() is None


def test_directories_show_their_most_significant_child_state():
    status = {"src/a.py": "?", "src/b/c.py": "M", "docs/x.md": "A", "top.py": "D"}
    assert rollup(status) == {"src": "M", "src/b": "M", "docs": "A"}


def test_conflicts_outrank_everything_in_a_directory():
    assert rollup({"a/x": "M", "a/y": "U", "a/z": "D"}) == {"a": "U"}
