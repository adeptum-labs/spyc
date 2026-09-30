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
from spyc.core.file_index import build_index


def test_git_index_lists_tracked_and_untracked_but_not_ignored_files(git_repo):
    write_files(git_repo, {"src/app/new.py": "", "build/out.o": ""})
    index = build_index(git_repo)
    assert "src/app/main.py" in index.paths
    assert "src/app/new.py" in index.paths
    assert "build/out.o" not in index.paths


def test_git_index_omits_files_deleted_from_the_working_tree(git_repo):
    (git_repo / "README.md").unlink()
    assert "README.md" not in build_index(git_repo).paths


def test_show_ignored_adds_ignored_files_but_never_git_metadata(git_repo):
    write_files(git_repo, {"build/out.o": ""})
    paths = build_index(git_repo, show_ignored=True).paths
    assert "build/out.o" in paths
    assert not any(path.startswith(".git/") for path in paths)


def test_index_outside_git_skips_build_and_dependency_directories(tmp_path):
    write_files(tmp_path, {"a.py": "", "node_modules/x/index.js": "", "target/classes/A.class": "",
                           ".venv/lib/site.py": "", "src/b.py": ""})
    assert build_index(tmp_path).paths == ("a.py", "src/b.py")


def test_index_outside_git_does_not_follow_directory_symlinks(tmp_path):
    write_files(tmp_path / "project", {"a.py": ""})
    (tmp_path / "project" / "loop").symlink_to(tmp_path / "project", target_is_directory=True)
    assert build_index(tmp_path / "project").paths == ("a.py",)


def test_index_is_capped_and_says_so(tmp_path):
    write_files(tmp_path, {f"f{number}.txt": "" for number in range(5)})
    index = build_index(tmp_path, limit=3)
    assert len(index.paths) == 3
    assert index.truncated


def test_tracked_dangling_symlink_is_still_listed(git_repo):
    (git_repo / "dangling").symlink_to(git_repo / "missing")
    git(git_repo, "add", "dangling")
    assert "dangling" in build_index(git_repo).paths


def test_unusual_file_names_survive(git_repo):
    write_files(git_repo, {"with space ü.py": ""})
    assert "with space ü.py" in build_index(git_repo).paths


def test_submodules_nested_repositories_and_directory_links_are_not_files(git_repo):
    git(git_repo, "update-index", "--add", "--cacheinfo", "160000,1111111111111111111111111111111111111111,sub")
    (git_repo / "etc-link").symlink_to("/etc", target_is_directory=True)
    (git_repo / "file-link").symlink_to("README.md")
    git(git_repo, "add", "etc-link", "file-link")
    write_files(git_repo / "nested", {"x.py": ""})
    git(git_repo / "nested", "init", "-q")
    paths = build_index(git_repo).paths
    assert "file-link" in paths and "README.md" in paths
    assert not {"sub", "etc-link", "nested", "nested/"} & set(paths)
