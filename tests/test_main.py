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


import importlib.metadata

import pytest

import spyc.__main__ as entry
from spyc.__main__ import main
from spyc.location import Location


class RecordingApp:
    created = []
    coverage_files = []

    def __init__(self, root, start=None, coverage_files=()):
        RecordingApp.created.append((root, start))
        RecordingApp.coverage_files = list(coverage_files)

    def run(self):
        pass


@pytest.fixture
def recorded(monkeypatch):
    RecordingApp.created = []
    monkeypatch.setattr(entry, "SpycApp", RecordingApp, raising=False)
    return RecordingApp.created


def test_a_subdirectory_opens_the_project_with_that_directory_revealed(git_repo, recorded):
    assert entry.main([str(git_repo / "src")]) == 0
    assert recorded == [(git_repo.resolve(), Location("src", None))]


def test_a_file_with_a_line_opens_at_that_line(git_repo, recorded):
    entry.main([f"{git_repo}/src/app/main.py:2"])
    assert recorded == [(git_repo.resolve(), Location("src/app/main.py", 2))]


def test_the_project_root_itself_needs_no_start_location(git_repo, recorded):
    entry.main([str(git_repo)])
    assert recorded == [(git_repo.resolve(), None)]


def test_no_argument_means_the_current_directory(git_repo, recorded, monkeypatch):
    monkeypatch.chdir(git_repo / "src")
    entry.main([])
    assert recorded == [(git_repo.resolve(), Location("src", None))]


def test_a_project_without_git_uses_its_build_marker(tmp_path, recorded):
    (tmp_path / "service" / "src").mkdir(parents=True)
    (tmp_path / "service" / "pom.xml").write_text("<project/>")
    entry.main([str(tmp_path / "service" / "src")])
    assert recorded == [((tmp_path / "service").resolve(), Location("src", None))]


def test_a_missing_path_is_an_error_and_starts_nothing(tmp_path, recorded, capsys):
    assert entry.main([str(tmp_path / "nope")]) == 2
    assert "no such file or directory" in capsys.readouterr().err and recorded == []


def test_coverage_reports_can_be_named_and_are_passed_on_as_absolute_paths(git_repo, recorded, monkeypatch):
    (git_repo / "one.info").write_text("x")
    (git_repo / "two.xml").write_text("x")
    monkeypatch.chdir(git_repo)
    assert entry.main([str(git_repo), "--coverage", "one.info", "--coverage", str(git_repo / "two.xml")]) == 0
    assert RecordingApp.coverage_files == [(git_repo / "one.info").resolve(), (git_repo / "two.xml").resolve()]


def test_a_coverage_report_that_is_not_a_file_is_an_error_and_starts_nothing(git_repo, recorded, capsys):
    assert entry.main([str(git_repo), "--coverage", str(git_repo / "nope.info")]) == 2
    assert "--coverage" in capsys.readouterr().err and recorded == []


def test_version_flag_prints_the_package_version(capsys):
    with pytest.raises(SystemExit) as exit_info:
        main(["--version"])
    assert exit_info.value.code == 0
    assert capsys.readouterr().out.strip() == f"spyc {importlib.metadata.version('spyc')}"
