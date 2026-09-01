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


from spyc.project import KeyFile, detect_build_systems, find_root, key_files


def test_root_is_the_git_toplevel_from_a_subdirectory(git_repo):
    assert find_root(git_repo / "src" / "app") == git_repo.resolve()


def test_root_of_a_file_starts_from_its_directory(git_repo):
    assert find_root(git_repo / "src" / "app" / "main.py") == git_repo.resolve()


def test_root_outside_git_is_the_nearest_build_marker(tmp_path):
    (tmp_path / "service" / "src").mkdir(parents=True)
    (tmp_path / "service" / "pom.xml").write_text("<project/>")
    assert find_root(tmp_path / "service" / "src") == (tmp_path / "service").resolve()


def test_root_without_markers_is_the_start_directory(tmp_path):
    (tmp_path / "loose").mkdir()
    assert find_root(tmp_path / "loose") == (tmp_path / "loose").resolve()


def test_build_systems_come_from_the_root_and_one_level_down():
    paths = ["pom.xml", "frontend/package.json", "a/b/Cargo.toml", "README.md"]
    assert detect_build_systems(paths) == ["Maven", "npm"]


def test_key_files_are_grouped_by_kind():
    paths = ["src/main.rs", "README.md", "LICENSE", "Cargo.toml", ".github/workflows/ci.yml",
             "docs/README.md", "tests/main.rs", "Dockerfile"]
    assert key_files(paths) == [
        KeyFile("Readme", "README.md"),
        KeyFile("License", "LICENSE"),
        KeyFile("Build", "Cargo.toml"),
        KeyFile("Container", "Dockerfile"),
        KeyFile("CI", ".github/workflows/ci.yml"),
        KeyFile("Entry point", "src/main.rs"),
    ]
